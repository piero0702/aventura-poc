"""Comparación por usuario contra Modash, con coberturas y líneas base."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook

from motor.modelos import normalizar_usuario


def _leer(ruta: str | Path) -> tuple[dict[str, dict], dict]:
    libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        hoja = libro['Perfiles'] if 'Perfiles' in libro.sheetnames else libro.active
        filas = hoja.iter_rows(values_only=True)
        cabecera = next(filas, ())
        if '@username' not in cabecera:
            raise ValueError('El Excel debe tener la columna @username')
        perfiles = {}
        for fila in filas:
            registro = dict(zip(cabecera, fila))
            if not registro.get('@username'):
                continue
            usuario = normalizar_usuario(registro['@username'])
            if usuario in perfiles:
                raise ValueError('Usuario duplicado en el Excel: @' + usuario)
            perfiles[usuario] = registro
        metadatos = {}
        if 'Corrida' in libro.sheetnames:
            for fila in libro['Corrida'].iter_rows(min_row=2, values_only=True):
                if len(fila) >= 2 and fila[0]:
                    metadatos[str(fila[0])] = fila[1]
        return perfiles, metadatos
    finally:
        libro.close()


def _texto(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto.casefold() in {'unknown', 'desconocido', 'n/a', 'null', 'none', '-', 'sin dato'}:
        return None
    return ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold()) if not unicodedata.combining(c))


def _edad(valor) -> str | None:
    texto = _texto(valor)
    return re.sub(r'\s+', '', texto.replace('–', '-').replace('—', '-')) if texto else None


def _genero(valor) -> str | None:
    texto = _texto(valor)
    return {'female': 'Female', 'femenino': 'Female', 'mujer': 'Female', 'male': 'Male', 'masculino': 'Male', 'hombre': 'Male'}.get(texto)


def _numero(valor) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (ValueError, TypeError):
        return None
    return numero if math.isfinite(numero) and numero >= 0 else None


def _audiencia(registro: dict, variante: str) -> dict:
    valor = registro.get(f'Audiencia {variante} (' + ('contenido)' if variante == 'A' else 'seguidores)'))
    if not valor:
        return {}
    try:
        dato = json.loads(valor) if isinstance(valor, str) else valor
        return dato if isinstance(dato, dict) else {}
    except (ValueError, TypeError):
        return {}


def _porcentaje(valor: float | None) -> str:
    return f'{valor:.1%}' if valor is not None else 'Sin dato'


def _celda(valor) -> str:
    return str(valor).replace('|', '\\|').replace('\n', ' ')


def validar(modash: str | Path, salida: str | Path, informe: str | Path = 'validacion.md') -> dict:
    """Mide A y B por separado; un dato ausente del motor cuenta como desacierto.

    La línea base es la frecuencia de la etiqueta más común en Modash dentro
    del mismo conjunto elegible del criterio. Superarla exige acierto estricto
    mayor; empatarla no demuestra aporte. No se extrapola una corrida corta a 200.
    """
    referencia, _ = _leer(modash)
    # El Excel de la agencia no trae audiencias A/B ni metadatos: se lee el de auditoría que va al lado.
    auditoria = Path(salida).with_name(Path(salida).stem + '.auditoria.xlsx')
    resultados, corrida = _leer(auditoria if auditoria.exists() else salida)
    exclusiones: list[dict[str, str]] = []
    descartes_incluidos: list[dict[str, str]] = []
    elegibles = {}
    for usuario, real in referencia.items():
        predicho = resultados.get(usuario)
        if all(_texto(real.get(columna)) is None for columna in ('Followers', 'ER', 'Aud. Age', 'Aud. Gender', 'Audience City')):
            exclusiones.append({'usuario': usuario, 'motivo': 'Sin dato en Modash'})
            continue
        if predicho is None:
            exclusiones.append({'usuario': usuario, 'motivo': 'Sin resultado en la salida'})
            # No se elimina del denominador: la salida ausente es un fallo.
            elegibles[usuario] = (real, {})
            continue
        nota = _texto(predicho.get('Notas')) or ''
        if any(motivo in nota for motivo in ('privad', 'no existe', 'inexistente')):
            exclusiones.append({'usuario': usuario, 'motivo': str(predicho.get('Notas'))})
            continue
        elegibles[usuario] = (real, predicho)
        if any(motivo in nota for motivo in ('sin reels', 'fuera del rango', 'followers por debajo', 'followers por encima', 'perfil descartado')):
            descartes_incluidos.append({'usuario': usuario, 'motivo': str(predicho.get('Notas'))})

    criterios = []
    for columna in ('Followers', 'ER'):
        pares = [(usuario, _numero(real.get(columna)), _numero(predicho.get(columna))) for usuario, (real, predicho) in elegibles.items()]
        pares = [par for par in pares if par[1] is not None]
        aciertos = sum(predicho is not None and abs(predicho - real) <= abs(real) * .1 + 1e-12 for _, real, predicho in pares)
        errores = [abs(predicho - real) / abs(real) for _, real, predicho in pares if predicho is not None and real != 0]
        criterios.append({
            'criterio': columna + ' frente a Modash', 'meta': '≥ 80 % dentro de ±10 % de Modash',
            'evaluables': len(pares), 'aciertos': aciertos,
            'acierto': aciertos / len(pares) if pares else None,
            'linea_base': None, 'supera_linea_base': None,
            'cumple': aciertos / len(pares) >= .8 if pares else None,
            'error_relativo_medio': sum(errores) / len(errores) if errores else None,
        })
    for nombre, columna, clave, normalizar, meta in [
        ('Edad', 'Aud. Age', 'edad', _edad, .7),
        ('Género', 'Aud. Gender', 'genero', _genero, .7),
    ]:
        for variante in ('A', 'B'):
            pares = []
            for usuario, (real, predicho) in elegibles.items():
                verdad = normalizar(real.get(columna))
                if verdad is not None:
                    pares.append((usuario, verdad, normalizar(_audiencia(predicho, variante).get(clave))))
            etiquetas = Counter(real for _, real, _ in pares)
            mayoria = etiquetas.most_common(1)[0] if etiquetas else (None, 0)
            aciertos = sum(real == predicho for _, real, predicho in pares)
            tasa = aciertos / len(pares) if pares else None
            base = mayoria[1] / len(pares) if pares else None
            criterios.append({
                'criterio': f'{nombre} ' + ('mayoritario' if nombre == 'Género' else 'mayoritaria') + f' — variante {variante}', 'meta': '≥ 70 %',
                'evaluables': len(pares), 'aciertos': aciertos, 'acierto': tasa,
                'linea_base': base, 'etiqueta_base': mayoria[0],
                'supera_linea_base': tasa > base if tasa is not None else None,
                'cumple': tasa >= meta if tasa is not None else None,
            })
    pares_ciudad = [(real, _texto(predicho.get('Audience City'))) for real, predicho in elegibles.values() if _texto(real.get('Audience City')) is not None]
    ciudades = Counter(_texto(real.get('Audience City')) for real, _ in pares_ciudad)
    aciertos_ciudad = sum(_texto(real.get('Audience City')) == predicho for real, predicho in pares_ciudad)
    tasa_ciudad = aciertos_ciudad / len(pares_ciudad) if pares_ciudad else None
    base_ciudad = ciudades.most_common(1)[0][1] / len(pares_ciudad) if pares_ciudad else None
    criterios.append({
        'criterio': 'Ciudad igual a Modash', 'meta': '≥ 80 %', 'evaluables': len(pares_ciudad),
        'aciertos': aciertos_ciudad, 'acierto': tasa_ciudad, 'linea_base': base_ciudad,
        'supera_linea_base': tasa_ciudad > base_ciudad if tasa_ciudad is not None else None,
        'cumple': tasa_ciudad >= .8 if tasa_ciudad is not None else None,
    })
    duracion = _numero(corrida.get('duracion_segundos'))
    cantidad = _numero(corrida.get('perfiles_solicitados'))
    procesados = _numero(corrida.get('perfiles_procesados'))
    costo = _numero(corrida.get('costo_por_perfil_usd'))
    if procesados is None or procesados == 0:
        costo = None
    completa = corrida.get('estado') == 'completa'
    costos_confirmados = str(corrida.get('costos_confirmados', True)).lower() not in {'false', '0', 'no'}
    simulada = str(corrida.get('ejecucion_simulada', False)).lower() in {'true', '1', 'si', 'sí'}
    criterios.append({
        'criterio': 'Tiempo de la corrida', 'meta': '< 30 min para 200 perfiles',
        'valor': duracion, 'evaluables': cantidad,
        'cumple': duracion < 1800 if duracion is not None and cantidad == 200 and procesados == 200 and completa and not simulada else None,
        'detalle': (f'{duracion / 60:.2f} min; {procesados:g}/{cantidad:g} perfiles procesados'
                    if duracion is not None and cantidad is not None and procesados is not None else 'Sin metadatos de corrida')
                   + ('; simulado, no acredita tiempo real' if simulada else
                      '; se requiere una corrida completa de 200 perfiles' if cantidad != 200 or procesados != 200 or not completa else ''),
    })
    detalle_costo = f'USD {costo:.6f}' if costo is not None else 'Sin metadatos de corrida'
    if not costos_confirmados:
        detalle_costo += '; reservas o uso pendientes de conciliación'
    if simulada:
        detalle_costo += '; simulado; no acredita gasto real'
    criterios.append({
        'criterio': 'Costo real por perfil', 'meta': '≤ USD 0.06', 'valor': costo,
        'cumple': costo <= .06 if costo is not None and costos_confirmados and not simulada else None,
        'detalle': detalle_costo,
    })

    faltantes = []
    for usuario, (real, _) in elegibles.items():
        sin_dato = [nombre for nombre in ('Followers', 'ER', 'Aud. Age', 'Aud. Gender', 'Audience City') if _texto(real.get(nombre)) is None]
        if sin_dato:
            faltantes.append({'usuario': usuario, 'campos': sin_dato})
    for usuario in resultados.keys() - referencia.keys():
        exclusiones.append({'usuario': usuario, 'motivo': 'Usuario ausente en Modash'})
    tiene_muestra = any((_numero(registro.get('Seguidores en la muestra')) or 0) > 0 for registro in resultados.values())
    filas = []
    motivos_exclusion = {dato['usuario']: dato['motivo'] for dato in exclusiones}
    for usuario, real in referencia.items():
        predicho = resultados.get(usuario, {})
        variante = 'B' if (_numero(predicho.get('Seguidores en la muestra')) or 0) > 0 else 'A'
        audiencia = _audiencia(predicho, variante)
        motor = {'followers': _numero(predicho.get('Followers')), 'er': _numero(predicho.get('ER')),
                 'edad': _edad(audiencia.get('edad')), 'genero': _genero(audiencia.get('genero')),
                 'ciudad': predicho.get('Audience City') if _texto(predicho.get('Audience City')) else None}
        datos_modash = {'followers': _numero(real.get('Followers')), 'er': _numero(real.get('ER')),
                        'edad': _edad(real.get('Aud. Age')), 'genero': _genero(real.get('Aud. Gender')),
                        'ciudad': real.get('Audience City') if _texto(real.get('Audience City')) else None}
        coincide = {}
        for campo in ('followers', 'er'):
            esperado, observado = datos_modash[campo], motor[campo]
            coincide[campo] = (esperado is not None and observado is not None
                               and abs(observado - esperado) <= abs(esperado) * .1 + 1e-12)
        for campo in ('edad', 'genero', 'ciudad'):
            esperado, observado = _texto(datos_modash[campo]), _texto(motor[campo])
            coincide[campo] = esperado is not None and observado is not None and esperado == observado
        notas = [motivos_exclusion.get(usuario, ''), predicho.get('Notas') or '']
        filas.append({'usuario': usuario, 'motor': motor, 'referencia': datos_modash, 'coincide': coincide,
                      'nota': '; '.join(dict.fromkeys(str(nota) for nota in notas if nota))})
    resumen = {'fecha': datetime.now(timezone.utc).isoformat(), 'criterios': criterios,
               'exclusiones': exclusiones, 'descartes_incluidos': descartes_incluidos,
               'sin_dato_por_campo': faltantes, 'perfiles_modash': len(referencia),
               'perfiles_salida': len(resultados), 'tiene_muestra': tiene_muestra, 'filas': filas}

    lineas = [
        '# Validación de la PoC de Aventura', '',
        f'Cruce por @username: {len(referencia)} perfiles en Modash, {len(resultados)} en la salida.', '',
        '| Criterio | Meta | Resultado | Con dato en Modash | Línea base | Supera base | Cumple meta |',
        '|---|---|---|---:|---|---|---|',
    ]
    for criterio in criterios:
        resultado = _porcentaje(criterio.get('acierto')) if 'acierto' in criterio else criterio['detalle']
        if 'aciertos' in criterio:
            resultado += f" ({criterio['aciertos']}/{criterio['evaluables']})"
        if criterio.get('error_relativo_medio') is not None:
            resultado += '; error relativo medio: ' + _porcentaje(criterio['error_relativo_medio'])
        base = _porcentaje(criterio.get('linea_base')) if criterio.get('linea_base') is not None else 'No aplica'
        if criterio.get('etiqueta_base'):
            base += ' (' + str(criterio['etiqueta_base']) + ')'
        supera = {True: 'Sí', False: 'No', None: 'No aplica'}[criterio.get('supera_linea_base')]
        cumple = {True: 'Sí', False: 'No', None: 'No evaluable'}[criterio['cumple']]
        cantidad_texto = str(criterio.get('evaluables', '—'))
        lineas.append('| ' + ' | '.join(_celda(valor) for valor in [criterio['criterio'], criterio['meta'], resultado, cantidad_texto, base, supera, cumple]) + ' |')
    lineas += [
        '', 'La línea base contesta siempre la etiqueta más común de Modash en el mismo conjunto evaluable. Empatarla no la supera, aunque se alcance la meta. Edad y género de A y B se miden por separado, sin sustituir B por A.',
        '', 'Los datos faltantes del motor cuentan como desaciertos cuando Modash tiene dato. Privados y perfiles inexistentes se excluyen. Los descartes por falta de reels o rango del brief siguen incluidos, para evitar inflar el acierto. Followers y ER pasan cuando al menos 80 % de perfiles quedan dentro de ±10 % de Modash; se informan esa proporción y el error relativo medio.',
        '', 'El tiempo solo se califica con una corrida real completa de 200 perfiles; una muestra pequeña o simulada no acredita esa meta. Un costo simulado o con reservas pendientes no acredita gasto real.',
        '', '## Perfiles excluidos o sin resultado', '', '| @username | Motivo |', '|---|---|',
    ]
    for exclusion in exclusiones:
        lineas.append(f"| @{_celda(exclusion['usuario'])} | {_celda(exclusion['motivo'])} |")
    if not exclusiones:
        lineas.append('| — | Ninguno |')
    lineas += ['', '## Descartes del motor que siguen incluidos en la evaluación', '', '| @username | Motivo |', '|---|---|']
    for descarte in descartes_incluidos:
        lineas.append(f"| @{_celda(descarte['usuario'])} | {_celda(descarte['motivo'])} |")
    if not descartes_incluidos:
        lineas.append('| — | Ninguno |')
    lineas += ['', '## Campos sin dato en Modash', '', '| @username | Campos excluidos de su criterio |', '|---|---|']
    for faltante in faltantes:
        lineas.append(f"| @{_celda(faltante['usuario'])} | {', '.join(faltante['campos'])} |")
    if not faltantes:
        lineas.append('| — | Ninguno |')
    informe = Path(informe)
    informe.parent.mkdir(parents=True, exist_ok=True)
    informe.write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    return resumen


def presentar_validacion(resumen: dict) -> dict:
    """Traduce el informe persistido a los siete criterios del contrato web."""
    por_nombre = {criterio['criterio']: criterio for criterio in resumen['criterios']}
    variante = 'B' if resumen.get('tiene_muestra') else 'A'
    otra = 'A' if variante == 'B' else 'B'
    criterios = []
    for identificador, nombre, clave, formato in [
        ('followers', 'Followers', 'Followers frente a Modash', 'porcentaje'),
        ('er', 'ER', 'ER frente a Modash', 'porcentaje'),
        ('edad', 'Edad mayoritaria', f'Edad mayoritaria — variante {variante}', 'porcentaje'),
        ('genero', 'Género mayoritario', f'Género mayoritario — variante {variante}', 'porcentaje'),
        ('ciudad', 'Ciudad', 'Ciudad igual a Modash', 'porcentaje'),
        ('tiempo', 'Lista de 200 sin tocarla', 'Tiempo de la corrida', 'minutos'),
        ('costo', 'Costo por perfil', 'Costo real por perfil', 'usd'),
    ]:
        criterio = por_nombre[clave]
        valor = criterio.get('acierto') if formato == 'porcentaje' else criterio.get('valor')
        if formato == 'minutos' and valor is not None:
            valor /= 60
        detalle = criterio.get('detalle', '')
        if formato == 'porcentaje':
            detalle = f"{criterio['aciertos']} de {criterio['evaluables']} perfiles evaluables"
            if identificador in {'followers', 'er'}:
                detalle += ' dentro de ±10 % de Modash; meta ≥ 80 %'
                detalle += '; error relativo medio: ' + _porcentaje(criterio.get('error_relativo_medio'))
            if identificador in {'edad', 'genero'}:
                alternativo = por_nombre[clave.rsplit(' ', 1)[0] + ' ' + otra]
                detalle += (f'; variante {variante}; variante {otra}: {_porcentaje(alternativo.get("acierto"))}'
                            f'; línea base {variante}: {_porcentaje(criterio.get("linea_base"))}'
                            f'; línea base {otra}: {_porcentaje(alternativo.get("linea_base"))}')
            elif criterio.get('linea_base') is not None:
                detalle += '; línea base: ' + _porcentaje(criterio['linea_base'])
        if criterio.get('cumple') is None:
            detalle += '; no evaluable: ' + ('sin perfiles con dato en Modash' if formato == 'porcentaje'
                                           else 'faltan condiciones para acreditar la meta real')
        criterios.append({'id': identificador, 'nombre': nombre, 'meta': criterio['meta'],
                          'resultado': valor, 'formato': formato, 'pasa': criterio.get('cumple') is True,
                          'detalle': detalle})
    return {'fecha': resumen['fecha'], 'perfiles': resumen['perfiles_modash'],
            'criterios': criterios, 'filas': resumen['filas']}
