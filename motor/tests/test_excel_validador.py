"""Pruebas del contrato Excel y del informe contra la muestra sintética."""
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from motor.excel import COLUMNAS, COLUMNAS_BASE, exportar_excel, leer_usuarios, ruta_auditoria
from motor.modelos import Audiencia, Clasificacion, Corrida, Marca, Metricas, Perfil, ResultadoPerfil
from motor.validador import presentar_validacion, validar

MUESTRA = Path('fixtures/muestra-sintetica.xlsx')


def _corrida(**cambios):
    valores = dict(id='prueba', fecha='2026-10-27T12:00:00Z', parametros={'reels': 5}, duracion_segundos=60, perfiles_solicitados=5, perfiles_procesados=5, costo_total_usd=.1, costo_por_perfil_usd=.02, costos_por_paso={'perfil': .013, 'jev': .087})
    valores.update(cambios)
    return Corrida(**valores)


def _resultados_muestra():
    libro = load_workbook(MUESTRA, data_only=True)
    try:
        hoja = libro['Perfiles']
        cabecera = [celda.value for celda in hoja[1]]
        resultados = []
        for fila in hoja.iter_rows(min_row=2, values_only=True):
            datos = dict(zip(cabecera, fila))
            audiencia = Audiencia(edad=datos['Aud. Age'], genero=datos['Aud. Gender'], ciudad=datos['Audience City'])
            resultados.append(ResultadoPerfil(
                perfil=Perfil(usuario=datos['@username'], nombre=datos['Nombre / Marca'], bio=datos['Descripción'], followers=datos['Followers'] or 0),
                metricas=Metricas(er=datos['ER'], engagements=datos['Engagements'], likes=datos['Avg. Likes'], comentarios=datos['Avg. Comments'], reel_plays=datos['Avg. Reel Plays']),
                clasificacion=Clasificacion(categoria=datos['Categoría'], audiencia_a=audiencia, encaje=3, motivo_encaje='Ejemplo sintético'),
                audiencia_b=audiencia.model_copy(), seguidores_muestra=3, calidad_audiencia=2 / 3, costo_usd=.02,
            ))
        return resultados
    finally:
        libro.close()


def test_lectura_usuarios_y_normalizacion(tmp_path):
    assert leer_usuarios(MUESTRA) == [f'cuenta.ficticia{i}' for i in range(1, 6)]
    entrada = tmp_path / 'usuarios.txt'
    entrada.write_text('\ufeff@Una.Cuenta\nuna.cuenta\n\n# comentario\n@otra\n', encoding='utf-8')
    assert leer_usuarios(entrada) == ['una.cuenta', 'otra']
    entrada.write_text('../no-permitido', encoding='utf-8')
    with pytest.raises(ValueError, match='Usuario'):
        leer_usuarios(entrada)


def test_excel_columnas_exactas_formatos_y_auditorias(tmp_path):
    resultados = _resultados_muestra()
    resultados[0].perfil.bio = '=SUM(1,2)'
    resultados[0].clasificacion.marcas = [
        Marca(nombre='Marca Aliada', tipo='canje', post_evidencia='https://instagram.com/p/sintetico'),
        Marca(nombre='Fotógrafo', tipo='amigo_fotografo', post_evidencia='https://instagram.com/p/sintetico'),
    ]
    resultados[0].audiencia_b = Audiencia(edad='35-44', genero='Male')
    ruta = exportar_excel(resultados, _corrida(), tmp_path / 'salida.xlsx')
    cliente = load_workbook(ruta, data_only=False)
    try:
        # El de la agencia: solo sus 15 columnas y la hoja Notas vacía, con sus formatos.
        assert cliente.sheetnames == ['Perfiles', 'Notas']
        hoja = cliente['Perfiles']
        assert [celda.value for celda in hoja[1]] == COLUMNAS_BASE
        assert hoja.max_column == 15
        assert cliente['Notas'].max_row == 1 and cliente['Notas']['A1'].value is None
        assert hoja['B2'].value.startswith('@')
        assert hoja['G2'].value is None  # vacía como la deja la agencia
        assert hoja['H2'].value == pytest.approx(.009) and hoja['H2'].number_format == '0.00%'
        assert hoja['I2'].value == '35-44'
        assert hoja['J2'].value == 'Male'
        assert hoja['K2'].value == 'Lima'
        assert all(isinstance(hoja.cell(2, columna).value, (int, type(None))) for columna in range(12, 16))
        assert hoja['A1'].fill.fgColor.rgb.endswith('1F4E78') and hoja['F2'].fill.fgColor.rgb.endswith('FFF2CC')
    finally:
        cliente.close()
    libro = load_workbook(ruta_auditoria(ruta), data_only=False)
    referencia = load_workbook(MUESTRA)
    try:
        assert libro.sheetnames == ['Perfiles', 'Corrida']
        hoja = libro['Perfiles']
        assert [celda.value for celda in hoja[1]] == COLUMNAS
        assert COLUMNAS[:15] == COLUMNAS_BASE
        assert hoja['G2'].value == pytest.approx(2 / 3)
        assert hoja['H2'].value == pytest.approx(.009)
        assert hoja['I2'].value == '35-44'
        assert hoja['J2'].value == 'Male'
        assert hoja['K2'].value == 'Lima'
        assert hoja['D2'].data_type == 's'
        assert json.loads(hoja['P2'].value)[0]['tipo'] == 'canje'
        assert 'Fotógrafo' not in hoja['P2'].value
        assert 'Fotógrafo' in hoja['V2'].value
        assert json.loads(hoja['S2'].value)['genero'] == 'Female'
        assert json.loads(hoja['T2'].value)['genero'] == 'Male'
        assert [celda.number_format for celda in hoja[2][:15]] == [celda.number_format for celda in referencia['Perfiles'][2][:15]]
        metadatos = dict(libro['Corrida'].iter_rows(min_row=2, values_only=True))
        assert metadatos['duracion_segundos'] == 60
        assert json.loads(metadatos['costos_por_paso'])['jev'] == .087
    finally:
        referencia.close()
        libro.close()


def test_no_hay_muestra_usa_a_y_b_no_se_rellena_con_a(tmp_path):
    resultado = _resultados_muestra()[0]
    resultado.seguidores_muestra = 0
    resultado.audiencia_b = None
    ruta = exportar_excel([resultado], _corrida(), tmp_path / 'salida.xlsx')
    libro = load_workbook(ruta_auditoria(ruta))
    try:
        assert libro['Perfiles']['I2'].value == '25-34'
        assert libro['Perfiles']['J2'].value == 'Female'
        assert libro['Perfiles']['T2'].value is None
    finally:
        libro.close()


def test_validador_muestra_linea_base_y_variantes_separadas(tmp_path):
    resultados = _resultados_muestra()
    # A responde siempre lo más común: pasa 70 % en edad solo si se falseara
    # el denominador; aquí acierta 2/3 y no supera la línea base.
    resultados[2].clasificacion.audiencia_a = Audiencia(edad='25-34', genero='Female', ciudad='Lima')
    salida = exportar_excel(resultados, _corrida(), tmp_path / 'salida.xlsx')
    informe = tmp_path / 'validacion.md'
    resumen = validar(MUESTRA, salida, informe)
    criterios = {dato['criterio']: dato for dato in resumen['criterios']}
    edad_a = criterios['Edad mayoritaria — variante A']
    genero_a = criterios['Género mayoritario — variante A']
    edad_b = criterios['Edad mayoritaria — variante B']
    assert edad_a['evaluables'] == 3
    assert edad_a['acierto'] == pytest.approx(2 / 3)
    assert edad_a['linea_base'] == pytest.approx(2 / 3)
    assert edad_a['supera_linea_base'] is False
    assert genero_a['acierto'] == pytest.approx(2 / 3)
    assert edad_b['acierto'] == 1
    assert edad_b['supera_linea_base'] is True
    assert criterios['Followers frente a Modash']['aciertos'] == 4
    assert criterios['Tiempo de la corrida']['cumple'] is None
    assert criterios['Costo real por perfil']['cumple'] is True
    assert any(dato['usuario'] == 'cuenta.ficticia5' and dato['motivo'] == 'Sin dato en Modash' for dato in resumen['exclusiones'])
    assert any(dato['usuario'] == 'cuenta.ficticia4' for dato in resumen['sin_dato_por_campo'])
    assert 'Línea base' in informe.read_text()
    assert 'No evaluable' in informe.read_text()


def test_validador_perfiles_privados_inexistentes_y_sin_prediccion(tmp_path):
    resultados = _resultados_muestra()
    resultados[0].notas = ['Cuenta privada']
    resultados[1].notas = ['El perfil no existe']
    resultados = resultados[:2] + resultados[3:]
    salida = exportar_excel(resultados, _corrida(perfiles_solicitados=200, perfiles_procesados=200, duracion_segundos=1799), tmp_path / 'salida.xlsx')
    resumen = validar(MUESTRA, salida, tmp_path / 'validacion.md')
    criterios = {dato['criterio']: dato for dato in resumen['criterios']}
    assert criterios['Edad mayoritaria — variante B']['evaluables'] == 1
    assert criterios['Edad mayoritaria — variante B']['aciertos'] == 0
    assert criterios['Tiempo de la corrida']['cumple'] is True
    motivos = {dato['usuario']: dato['motivo'] for dato in resumen['exclusiones']}
    assert motivos['cuenta.ficticia1'] == 'Cuenta privada'
    assert motivos['cuenta.ficticia2'] == 'El perfil no existe'
    assert motivos['cuenta.ficticia3'] == 'Sin resultado en la salida'


def test_validador_tolerancia_diez_por_ciento_y_prediccion_ausente(tmp_path):
    resultados = _resultados_muestra()
    resultados[0].perfil.followers = 117_920  # Límite exacto +10 %.
    resultados[1].perfil.followers = 60_000  # Fuera del límite.
    resultados[2].metricas.er = None
    salida = exportar_excel(resultados, _corrida(), tmp_path / 'salida.xlsx')
    resumen = validar(MUESTRA, salida, tmp_path / 'validacion.md')
    criterios = {dato['criterio']: dato for dato in resumen['criterios']}
    assert criterios['Followers frente a Modash']['aciertos'] == 3
    assert criterios['Followers frente a Modash']['cumple'] is False
    assert criterios['ER frente a Modash']['aciertos'] == 3


def test_metricas_aprueban_con_cuatro_de_cinco_dentro_de_tolerancia(tmp_path):
    resultados = _resultados_muestra()
    for resultado in resultados:
        resultado.perfil.followers = 10_000
        resultado.metricas.er = .02
    referencia = exportar_excel(resultados, _corrida(), tmp_path / 'referencia.xlsx')
    resultados[0].perfil.followers = 12_000
    resultados[0].metricas.er = .04
    salida = exportar_excel(resultados, _corrida(), tmp_path / 'salida.xlsx')
    informe = tmp_path / 'informe.md'
    resumen = validar(referencia, salida, informe)
    for criterio in resumen['criterios'][:2]:
        assert criterio['acierto'] == .8
        assert criterio['aciertos'] == 4
        assert criterio['evaluables'] == 5
        assert criterio['cumple'] is True
        assert criterio['error_relativo_medio'] > 0
    assert 'error relativo medio' in informe.read_text()
    assert '80 %' in informe.read_text()


def test_presentacion_siete_criterios_y_filas_con_audiencia_del_excel(tmp_path):
    resultados = _resultados_muestra()
    resultados[0].clasificacion.audiencia_a = Audiencia(edad='45-54', genero='Male', ciudad='Lima')
    salida = exportar_excel(resultados, _corrida(ejecucion_simulada=True), tmp_path / 'salida.xlsx')
    resumen = validar(MUESTRA, salida, tmp_path / 'informe.md')
    datos = presentar_validacion(resumen)
    assert len(datos['criterios']) == 7
    assert [criterio['id'] for criterio in datos['criterios']] == ['followers', 'er', 'edad', 'genero', 'ciudad', 'tiempo', 'costo']
    assert len(datos['filas']) == 5
    assert datos['filas'][0]['motor']['edad'] == '25-34'
    assert datos['filas'][0]['coincide']['edad'] is True
    assert 'variante B' in datos['criterios'][2]['detalle']
    assert 'variante A' in datos['criterios'][2]['detalle']
    assert 'línea base' in datos['criterios'][2]['detalle']
    assert datos['criterios'][5]['resultado'] == 1
    assert datos['criterios'][5]['pasa'] is False
    assert 'no evaluable' in datos['criterios'][5]['detalle']
    assert datos['criterios'][6]['pasa'] is False


def test_sin_muestra_presenta_variante_a_y_no_inventa_resultado_sin_modash(tmp_path):
    resultados = _resultados_muestra()
    for resultado in resultados:
        resultado.seguidores_muestra = 0
        resultado.audiencia_b = None
    salida = exportar_excel(resultados, _corrida(), tmp_path / 'salida.xlsx')
    datos = presentar_validacion(validar(MUESTRA, salida, tmp_path / 'informe.md'))
    assert 'variante A' in datos['criterios'][2]['detalle']
    assert datos['filas'][-1]['referencia']['edad'] is None
    assert datos['filas'][-1]['coincide']['edad'] is False


def test_muestra_mixta_criterio_b_global_y_fila_a_sin_muestra(tmp_path):
    resultados = _resultados_muestra()
    resultados[0].seguidores_muestra = 0
    resultados[0].audiencia_b = None
    resultados[0].clasificacion.audiencia_a = Audiencia(edad='35-44', genero='Male', ciudad='Lima')
    salida = exportar_excel(resultados, _corrida(), tmp_path / 'salida.xlsx')
    resumen = validar(MUESTRA, salida, tmp_path / 'informe.md')
    datos = presentar_validacion(resumen)
    assert resumen['tiene_muestra'] is True
    assert 'variante B' in datos['criterios'][2]['detalle']
    assert datos['filas'][0]['motor']['edad'] == '35-44'
    assert datos['filas'][0]['motor']['genero'] == 'Male'
    assert datos['filas'][0]['coincide']['edad'] is False
    criterio_b = next(criterio for criterio in resumen['criterios'] if criterio['criterio'] == 'Edad mayoritaria — variante B')
    assert datos['criterios'][2]['resultado'] == criterio_b['acierto']


def test_presentacion_sin_datos_evaluables_conserva_null_y_explica(tmp_path):
    resultados = _resultados_muestra()
    salida = exportar_excel(resultados[-1:], _corrida(perfiles_procesados=0), tmp_path / 'salida.xlsx')
    referencia = exportar_excel(resultados[-1:], _corrida(), tmp_path / 'referencia.xlsx')
    libro = load_workbook(referencia)
    try:
        for columna in ('F', 'H', 'I', 'J', 'K'):
            libro['Perfiles'][columna + '2'] = None
        libro.save(referencia)
    finally:
        libro.close()
    datos = presentar_validacion(validar(referencia, salida, tmp_path / 'informe.md'))
    for criterio in datos['criterios'][:5]:
        assert criterio['resultado'] is None
        assert criterio['pasa'] is False
        assert 'no evaluable' in criterio['detalle']
    assert datos['criterios'][6]['resultado'] is None
    assert datos['criterios'][6]['pasa'] is False


def test_no_califica_tiempo_de_corrida_cortada_ni_costo_sin_perfiles(tmp_path):
    salida = exportar_excel([], _corrida(perfiles_solicitados=200, perfiles_procesados=0, estado='presupuesto'), tmp_path / 'salida.xlsx')
    resumen = validar(MUESTRA, salida, tmp_path / 'validacion.md')
    criterios = {dato['criterio']: dato for dato in resumen['criterios']}
    assert criterios['Tiempo de la corrida']['cumple'] is None
    assert criterios['Costo real por perfil']['cumple'] is None


def test_sin_dato_modash_se_detecta_aunque_no_haya_resultado(tmp_path):
    salida = exportar_excel(_resultados_muestra()[:4], _corrida(), tmp_path / 'salida.xlsx')
    resumen = validar(MUESTRA, salida, tmp_path / 'validacion.md')
    motivos = {dato['usuario']: dato['motivo'] for dato in resumen['exclusiones']}
    assert motivos['cuenta.ficticia5'] == 'Sin dato en Modash'


@pytest.mark.parametrize('motivo', ['Followers por debajo del mínimo del brief (100000).', 'Followers por encima del máximo del brief (10000).', 'Sin reels entre los posts disponibles.'])
def test_validador_lista_descartes_de_filtro_y_los_conserva_en_denominador(tmp_path, motivo):
    resultados = _resultados_muestra()
    resultados[0].descartado = True
    resultados[0].notas = [motivo]
    resultados[0].clasificacion = None
    resultados[0].audiencia_b = None
    salida = exportar_excel(resultados, _corrida(), tmp_path / 'salida.xlsx')
    resumen = validar(MUESTRA, salida, tmp_path / 'validacion.md')
    criterios = {dato['criterio']: dato for dato in resumen['criterios']}
    assert criterios['Followers frente a Modash']['evaluables'] == 4
    assert criterios['Edad mayoritaria — variante A']['evaluables'] == 3
    assert criterios['Edad mayoritaria — variante A']['aciertos'] == 2
    assert {'usuario': 'cuenta.ficticia1', 'motivo': motivo} in resumen['descartes_incluidos']


@pytest.mark.parametrize('campo,mensaje', [('costos_confirmados', 'pendientes de conciliación'), ('ejecucion_simulada', 'no acredita gasto real')])
def test_costo_simulado_o_con_reservas_no_acredita_meta_real(tmp_path, campo, mensaje):
    salida = exportar_excel(_resultados_muestra(), _corrida(), tmp_path / 'salida.xlsx')
    libro = load_workbook(ruta_auditoria(salida))
    # Agregar o reemplazar metadatos permite evaluar también archivos históricos.
    hoja = libro['Corrida']
    encontrado = False
    for fila in hoja.iter_rows(min_row=2):
        if fila[0].value == campo:
            fila[1].value = campo == 'ejecucion_simulada'
            encontrado = True
    if not encontrado:
        hoja.append([campo, campo == 'ejecucion_simulada'])
    libro.save(ruta_auditoria(salida))
    libro.close()
    resumen = validar(MUESTRA, salida, tmp_path / 'validacion.md')
    criterio = next(dato for dato in resumen['criterios'] if dato['criterio'] == 'Costo real por perfil')
    assert criterio['valor'] == .02
    assert criterio['cumple'] is None
    assert mensaje in criterio['detalle']


def test_nombre_como_lo_escribe_la_agencia():
    from motor.excel import limpiar_nombre
    assert limpiar_nombre('ALE BONELLI') == 'Ale Bonelli'
    assert limpiar_nombre('jimena shiroma g ★') == 'Jimena Shiroma G'
    assert limpiar_nombre('Dr. José Luis Pérez-Albela B') == 'Dr. José Luis Pérez-Albela B'
    assert limpiar_nombre('Maca | nutrición real & lifestyle') == 'Maca'
    assert limpiar_nombre('✨✨') is None
    import unicodedata
    assert limpiar_nombre(unicodedata.normalize('NFD', 'Ana Lucía Rodríguez')) == 'Ana Lucía Rodríguez'
    assert limpiar_nombre('ㅤㅤㅤjimena shiroma g ★') == 'Jimena Shiroma G'
