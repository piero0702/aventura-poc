"""Pruebas de integración por etapas sin llamadas externas."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from copy import deepcopy
import pytest
from motor.almacen import Almacen
from motor.costos import Precios, RegistroCostos, PresupuestoAgotado, estimar_costo
from motor.modelos import (Perfil, Post, Seguidor, Clasificacion, Audiencia, AudienciaSeguidor,
                          RespuestaClasificacion, Opciones, Brief, Marca)
from motor.tuberia import Motor, Proveedores, agregar_audiencia


def reel(identificador='uno', vistas=100, duracion=30, caption='#publi con @marca.prueba', fecha=''):
    # Por defecto es un reel de publicidad: son los únicos que se transcriben.
    return Post(id=identificador, url=f'https://www.instagram.com/reel/{identificador}/', tipo='reel', fecha=fecha,
                likes=10, comentarios=2, vistas=vistas, duracion_segundos=duracion, caption=caption,
                audio_url='https://audio.example/prueba.mp4')


class InstagramPrueba:
    identidad = 'prueba'
    def __init__(self, perfiles=None, posts_adicionales=None, muestra=None):
        self.llamadas = Counter()
        self.perfiles = perfiles or {'creadora': Perfil(usuario='creadora', followers=1000, posts=[reel()])}
        self.posts_adicionales = posts_adicionales or []
        self.muestra = muestra or [Seguidor(usuario='seguidora')]
        self.ultimas_unidades = 0
    def obtener_perfil(self, usuario):
        self.llamadas['perfil'] += 1
        return deepcopy(self.perfiles[usuario])
    def obtener_reels(self, usuario, limite):
        self.llamadas['reels'] += 1
        return self.posts_adicionales[:limite]
    def relaciones(self, usuario, modo, limite):
        self.llamadas[modo] += 1
        self.ultimas_unidades = min(max(25, limite), len(self.muestra))
        return self.muestra[:limite]


class AudioPrueba:
    identidad = 'audio-prueba'
    def __init__(self):
        self.descargas = []
        self.transcripciones = []
        self.tamano = 10
    def descargar_audio(self, post):
        self.descargas.append(post.id)
        return b'a' * self.tamano
    def transcribir(self, contenido, post):
        self.transcripciones.append(post.id)
        return 'Contenido de bienestar para mujeres de Lima'


class ClasificadorPrueba:
    nombre = 'jev'
    identidad = 'clasificador-prueba'
    def __init__(self):
        self.contextos = []
    def estimar_tokens(self, contexto):
        return 10000
    def clasificar(self, contexto):
        self.contextos.append(contexto)
        return RespuestaClasificacion(datos=Clasificacion(categoria='Lifestyle',
            audiencia_a=Audiencia(edad='25-34', genero='Female', ciudad='Lima'),
            seguidores=[AudienciaSeguidor(usuario=s['usuario'], genero='Female', edad='25-34', persona_real=True)
                        for s in contexto['seguidores']], encaje=4, motivo_encaje='Afinidad con el brief'), tokens_entrada=500)


def preparar(tmp_path, instagram=None, audio=None, clasificador=None, reloj=None):
    proveedores = Proveedores(instagram or InstagramPrueba(), audio or AudioPrueba(), clasificador or ClasificadorPrueba())
    return Motor(proveedores, Almacen(tmp_path / 'datos.sqlite', reloj=reloj))


def test_tuberia_completa_y_cache_sin_pago_duplicado(tmp_path):
    motor = preparar(tmp_path)
    opciones = Opciones(reels=1)
    primera = motor.ejecutar(['@Creadora', 'creadora'], opciones)
    assert primera.corrida.estado == 'completa'
    assert primera.corrida.perfiles_solicitados == 1
    assert primera.perfiles[0].calidad_audiencia == 1
    assert primera.perfiles[0].audiencia_b.genero == 'Female'
    assert primera.corrida.costo_total_usd > 0
    assert primera.corrida.costos_por_paso['transcripcion'] == pytest.approx(30 / 3600 * .04)
    llamadas = dict(motor.proveedores.instagram.llamadas)
    segunda = motor.ejecutar(['creadora'], opciones)
    assert segunda.corrida.costo_total_usd == 0
    assert motor.proveedores.instagram.llamadas == llamadas
    assert len(motor.proveedores.clasificador.contextos) == 1
    assert motor.proveedores.audio.transcripciones == ['uno']
    registros = motor.almacen.costos(primera.corrida.id)
    assert all(r['estado'] == 'confirmado' for r in registros)
    assert sum(r['costo_usd'] for r in registros) == pytest.approx(primera.corrida.costo_total_usd)


def registrar_eventos(eventos):
    def al_avanzar(paso, hechos, total, descartados, **extra):
        eventos.append(dict(paso=paso, hechos=hechos, total=total, descartados=descartados, **extra))
    return al_avanzar


def test_progreso_es_de_toda_la_lista_y_solo_sube(tmp_path):
    instagram = InstagramPrueba(muestra=[Seguidor(usuario='creadora')])
    motor = preparar(tmp_path, instagram)
    eventos = []
    resultado = motor.ejecutar(None, Opciones(limite=1, reels=1), referencia='agencia',
                              al_avanzar=registrar_eventos(eventos))
    porcentajes = [evento['porcentaje'] for evento in eventos]
    assert porcentajes == sorted(porcentajes) and porcentajes[-1] == 97
    assert eventos[0]['paso'] == 'seguidos' and eventos[-1]['paso'] == 'analisis'
    assert eventos[-1]['hechos'] == 1 and eventos[-1]['total'] == 1
    assert any('Transcribiendo' in evento['actividad'] for evento in eventos)
    assert resultado.corrida.estado == 'completa'


def test_progreso_en_paralelo_cuenta_perfiles_listos_sin_retroceder(tmp_path):
    usuarios = [f'creadora{i}' for i in range(6)]
    instagram = InstagramPrueba({u: Perfil(usuario=u, followers=1000, posts=[reel(u)]) for u in usuarios})
    motor = preparar(tmp_path, instagram)
    motor.paralelo = 3
    eventos = []
    resultado = motor.ejecutar(usuarios, Opciones(reels=1, muestra_seguidores=0), al_avanzar=registrar_eventos(eventos))
    porcentajes = [evento['porcentaje'] for evento in eventos]
    listos = [evento['hechos'] for evento in eventos]
    assert porcentajes == sorted(porcentajes) and listos == sorted(listos)
    assert listos[-1] == 6 and resultado.corrida.perfiles_procesados == 6
    assert [r.perfil.usuario for r in resultado.perfiles] == usuarios


def test_progreso_cuenta_descartados_sin_pasos_caros(tmp_path):
    instagram = InstagramPrueba({'privada': Perfil(usuario='privada', privada=True)})
    motor = preparar(tmp_path, instagram)
    eventos = []
    motor.ejecutar(['privada'], Opciones(), al_avanzar=registrar_eventos(eventos))
    assert eventos[-1]['hechos'] == 1 and eventos[-1]['descartados'] == 1
    assert eventos[-1]['porcentaje'] == 97
    assert not any('Transcribiendo' in evento['actividad'] for evento in eventos)


class InstagramLote(InstagramPrueba):
    """Proveedor con lotes: perfiles y reels de varios usuarios en una sola llamada."""
    def obtener_perfiles(self, usuarios):
        self.llamadas['perfiles_lote'] += 1
        return {u: deepcopy(self.perfiles[u]) for u in usuarios if u in self.perfiles}
    def obtener_reels_lote(self, usuarios, limite):
        self.llamadas['reels_lote'] += 1
        return {u: [reel(f'{u}-extra')] for u in usuarios}


def test_lotes_piden_perfiles_y_reels_una_sola_vez_para_toda_la_lista(tmp_path):
    usuarios = [f'creadora{i}' for i in range(4)]
    # Posts sin duración: obligan a pedir reels, como pasa con latestPosts reales.
    instagram = InstagramLote({u: Perfil(usuario=u, followers=1000, posts=[reel(u, duracion=None)]) for u in usuarios})
    motor = preparar(tmp_path, instagram)
    motor.paralelo = 2
    resultado = motor.ejecutar(usuarios, Opciones(reels=1, muestra_seguidores=0))
    assert instagram.llamadas['perfiles_lote'] == 1 and instagram.llamadas['perfil'] == 0
    assert instagram.llamadas['reels_lote'] == 1 and instagram.llamadas['reels'] == 0
    assert resultado.corrida.estado == 'completa' and resultado.corrida.perfiles_procesados == 4
    assert resultado.corrida.costos_confirmados
    assert resultado.corrida.costos_por_paso['perfil'] == pytest.approx(4 * float(motor.precios.costo('perfil', 1)))


def test_lote_que_falla_vuelve_a_pedir_perfil_por_perfil(tmp_path):
    class LoteRoto(InstagramLote):
        def obtener_perfiles(self, usuarios):
            raise RuntimeError('lote caído')
    usuarios = ['creadora0', 'creadora1']
    instagram = LoteRoto({u: Perfil(usuario=u, followers=1000, posts=[reel(u)]) for u in usuarios})
    resultado = preparar(tmp_path, instagram).ejecutar(usuarios, Opciones(reels=1, muestra_seguidores=0))
    assert instagram.llamadas['perfil'] == 2 and resultado.corrida.perfiles_procesados == 2
    assert any('lote de perfiles' in nota for nota in resultado.corrida.notas)


def test_retraso_artificial_solo_afecta_modo_simulado(tmp_path, monkeypatch):
    pausas = []
    monkeypatch.setattr('motor.tuberia.sleep', pausas.append)
    motor = preparar(tmp_path)
    motor.simulado_retraso_s = .25
    motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert pausas == []
    motor.simulado = True
    motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert pausas == [.25, .25, .25]


@pytest.mark.parametrize('agregacion,likes', [('promedio', 3340), ('mediana', 20)])
def test_motor_aplica_y_documenta_agregacion_excel(tmp_path, agregacion, likes):
    from openpyxl import load_workbook
    from motor.excel import exportar_excel
    posts = [reel(str(i)) for i in range(3)]
    for post, cantidad in zip(posts, (0, 20, 10000)):
        post.likes = cantidad
    motor = preparar(tmp_path, InstagramPrueba({'creadora': Perfil(usuario='creadora', followers=1000, posts=posts)}))
    motor.metricas_agregacion = agregacion
    resultado = motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert resultado.perfiles[0].metricas.likes == likes
    assert resultado.corrida.parametros['metricas_agregacion'] == agregacion
    salida = exportar_excel(resultado.perfiles, resultado.corrida, tmp_path / 'metricas.xlsx')
    libro = load_workbook(salida.with_name('metricas.auditoria.xlsx'), read_only=True)
    try:
        metadatos = dict(libro['Corrida'].iter_rows(min_row=2, values_only=True))
        assert metadatos['metricas_agregacion'] == agregacion
    finally:
        libro.close()


def test_reel_sin_pista_de_audio_no_tumba_el_perfil(tmp_path):
    from motor.proveedores.base import AudioSinPista
    motor = preparar(tmp_path)
    def sin_pista(contenido, post):
        raise AudioSinPista('Reel sin pista de audio.')
    motor.proveedores.audio.transcribir = sin_pista
    resultado = motor.ejecutar(['creadora'], Opciones(reels=1))
    assert resultado.corrida.estado == 'completa'
    assert resultado.perfiles[0].clasificacion is not None
    assert any('sin pista de audio' in nota for nota in resultado.perfiles[0].notas)
    assert resultado.corrida.costos_por_paso.get('transcripcion', 0) == 0
    assert resultado.corrida.costos_confirmados


def test_limite_de_transcripcion_no_tumba_el_perfil(tmp_path):
    from motor.proveedores.base import LimiteProveedor
    motor = preparar(tmp_path)
    def sin_cupo(contenido, post):
        raise LimiteProveedor('Groq alcanzó su límite de uso (pidió esperar 900 s).')
    motor.proveedores.audio.transcribir = sin_cupo
    resultado = motor.ejecutar(['creadora'], Opciones(reels=1))
    assert resultado.corrida.estado == 'completa'
    assert resultado.perfiles[0].clasificacion is not None
    assert any('Transcripción omitida' in nota for nota in resultado.perfiles[0].notas)
    assert resultado.corrida.costos_por_paso.get('transcripcion', 0) == 0


def test_filtro_no_consume_pasos_caros(tmp_path):
    perfiles = {
        'privada': Perfil(usuario='privada', privada=True, posts=[reel()]),
        'sinreels': Perfil(usuario='sinreels', posts=[Post(tipo='imagen')]),
        'pequena': Perfil(usuario='pequena', followers=20, posts=[reel()]),
        'inexistente': Perfil(usuario='inexistente', existe=False),
    }
    motor = preparar(tmp_path, InstagramPrueba(perfiles))
    resultado = motor.ejecutar(list(perfiles), Opciones(brief=Brief(followers_min=100)))
    assert resultado.corrida.estado == 'completa'
    assert all(r.descartado and r.notas for r in resultado.perfiles)
    assert motor.proveedores.instagram.llamadas == {'perfil': 4}
    assert not motor.proveedores.audio.descargas
    assert not motor.proveedores.clasificador.contextos


def test_presupuesto_se_reserva_antes_de_llamar_y_deja_notas(tmp_path):
    motor = preparar(tmp_path)
    resultado = motor.ejecutar(['creadora', 'otra'], Opciones(presupuesto_usd=.0026))
    assert resultado.corrida.estado == 'presupuesto_agotado'
    assert resultado.corrida.costo_total_usd == .0026
    assert motor.proveedores.instagram.llamadas == {'perfil': 1}
    assert not motor.proveedores.audio.descargas
    assert not motor.proveedores.clasificador.contextos
    assert 'presupuesto' in resultado.perfiles[-1].notas[0].lower()
    assert resultado.perfiles[0].perfil_obtenido is True
    assert resultado.perfiles[-1].perfil_obtenido is False


def test_presupuesto_cero_no_llama_ni_un_perfil(tmp_path):
    from openpyxl import load_workbook
    from motor.excel import exportar_excel
    motor = preparar(tmp_path)
    resultado = motor.ejecutar(['creadora'], Opciones(presupuesto_usd=0))
    assert resultado.corrida.estado == 'presupuesto_agotado'
    assert not motor.proveedores.instagram.llamadas
    assert resultado.corrida.costo_total_usd == 0
    assert resultado.perfiles[0].perfil_obtenido is False
    salida = exportar_excel(resultado.perfiles, resultado.corrida, tmp_path / 'sin-consulta.xlsx')
    libro = load_workbook(salida, read_only=True)
    try:
        assert libro['Perfiles'].cell(2, 6).value is None
    finally:
        libro.close()


def test_vencimiento_30_dias_y_cache_por_brief(tmp_path):
    ahora = [datetime(2026, 10, 27, tzinfo=timezone.utc)]
    motor = preparar(tmp_path, reloj=lambda: ahora[0])
    motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    otra = motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0, brief=Brief(marca='Distinta')))
    assert set(otra.corrida.costos_por_paso) == {'jev'}
    ahora[0] += timedelta(days=30)
    motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert motor.proveedores.instagram.llamadas['perfil'] == 2


def test_solo_reels_de_publicidad_del_mas_reciente_y_largo_omitido(tmp_path):
    posts = [reel('largo', 100000, 181, fecha='2026-10-20'), reel('bajo', 2, 5, fecha='2026-10-01'),
             reel('organico', 99999, 20, caption='Mi rutina de mañana', fecha='2026-10-25')]
    instagram = InstagramPrueba({'creadora': Perfil(usuario='creadora', followers=1000, posts=posts)},
                               posts_adicionales=[reel('nuevo', 1, 20, caption='Publicidad @tienda.prueba', fecha='2026-10-22'), posts[1]])
    motor = preparar(tmp_path, instagram)
    resultado = motor.ejecutar(['creadora'], Opciones(reels=3, muestra_seguidores=0))
    assert resultado.corrida.estado == 'completa'
    # El orgánico no se transcribe aunque sea el más visto; los de publicidad van por fecha, no por vistas.
    assert motor.proveedores.audio.transcripciones == ['nuevo', 'bajo']
    assert any('3 minutos' in n for n in resultado.perfiles[0].notas)
    assert any('3 reels de publicidad entre 4 revisados' in n for n in resultado.perfiles[0].notas)
    assert resultado.corrida.costos_por_paso['transcripcion'] == pytest.approx(30 * .04 / 3600)
    assert len(motor.proveedores.clasificador.contextos[0]['perfil']['posts']) == 4
    assert resultado.perfiles[0].metricas.likes == 10


def test_audio_grande_no_se_transcribe_ni_paga(tmp_path):
    audio = AudioPrueba()
    audio.tamano = 25_000_001
    motor = preparar(tmp_path, audio=audio)
    resultado = motor.ejecutar(['creadora'], Opciones(reels=1, muestra_seguidores=0))
    assert resultado.corrida.estado == 'completa'
    assert not audio.transcripciones
    assert 'transcripcion' not in resultado.corrida.costos_por_paso
    assert any('25 MB' in n for n in resultado.perfiles[0].notas)


def test_muestra_parcial_se_acepta_y_audiencia_a_sin_muestra(tmp_path):
    motor = preparar(tmp_path)
    resultado = motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=30))
    assert resultado.perfiles[0].seguidores_muestra == 1
    assert any('1 de 30' in n for n in resultado.perfiles[0].notas)
    otro = motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert otro.perfiles[0].audiencia_b is None
    assert otro.perfiles[0].calidad_audiencia is None
    assert otro.perfiles[0].clasificacion.audiencia_a.genero == 'Female'


def test_seguidos_referencia_y_reparto_de_costo(tmp_path):
    instagram = InstagramPrueba(muestra=[Seguidor(usuario='creadora')])
    motor = preparar(tmp_path, instagram)
    resultado = motor.ejecutar(None, Opciones(limite=1, reels=0, muestra_seguidores=0), referencia='@Agencia')
    assert resultado.corrida.estado == 'completa'
    assert instagram.llamadas['following'] == 1
    assert resultado.perfiles[0].perfil.usuario == 'creadora'
    assert sum(r.costo_usd for r in resultado.perfiles) == pytest.approx(resultado.corrida.costo_total_usd)
    segunda = motor.ejecutar(None, Opciones(limite=1, reels=0, muestra_seguidores=0), referencia='agencia')
    assert segunda.corrida.costo_total_usd == 0


def test_audiencia_por_usuario_nunca_por_posicion():
    seguidores = [Seguidor(usuario='ana'), Seguidor(usuario='luis')]
    datos = Clasificacion(seguidores=[
        AudienciaSeguidor(usuario='luis', edad='35-44', genero='Male', persona_real=False),
        AudienciaSeguidor(usuario='ana', edad='25-34', genero='Female', persona_real=True)])
    audiencia, calidad = agregar_audiencia(datos, seguidores)
    assert audiencia.genero == 'Female'
    # Una sola edad en la muestra no basta: decide la estimación por contenido.
    assert audiencia.edad is None
    assert calidad == .5
    datos.seguidores[0].usuario = 'intruso'
    with pytest.raises(ValueError):
        agregar_audiencia(datos, seguidores)
    with pytest.raises(ValueError):
        agregar_audiencia(Clasificacion(), seguidores)


def test_edad_de_la_muestra_exige_cinco_seguidores_con_dato():
    seguidores = [Seguidor(usuario=f's{i}') for i in range(6)]
    datos = Clasificacion(seguidores=[AudienciaSeguidor(usuario=f's{i}', edad='18-24' if i < 5 else None, persona_real=True)
                                      for i in range(6)])
    assert agregar_audiencia(datos, seguidores)[0].edad == '18-24'
    datos.seguidores[0].edad = None
    assert agregar_audiencia(datos, seguidores)[0].edad is None


def test_error_pagado_no_cachea_y_conserva_reserva(tmp_path):
    class Fallido(ClasificadorPrueba):
        def clasificar(self, contexto):
            raise RuntimeError('nunca debe salir este secreto')
    motor = preparar(tmp_path, clasificador=Fallido())
    resultado = motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert resultado.corrida.estado == 'completa_con_errores'
    assert 'secreto' not in resultado.model_dump_json()
    assert any(c['estado'] == 'reservado' for c in motor.almacen.costos(resultado.corrida.id))
    assert resultado.corrida.costo_total_usd == pytest.approx(.0026 + .00042)


def test_registro_decimales_limite_exacto(tmp_path):
    almacen = Almacen(tmp_path/'costos.sqlite')
    registro = RegistroCostos(almacen, Precios(), 'corrida', .0052)
    for _ in range(2):
        reserva = registro.reservar('usuario', 'perfil', 1)
        registro.confirmar(reserva, 'perfil', 1)
    assert registro.total == Decimal('.0052')
    with pytest.raises(PresupuestoAgotado):
        registro.reservar('usuario', 'perfil', 1)
    assert len(almacen.costos('corrida')) == 2


def test_estimacion_sin_red_y_tarifas_del_encargo():
    estimacion = estimar_costo(5, Opciones())
    # Valores por defecto: 5 perfiles × 10 reels revisados y × 50 seguidores; 5 reels de 3 min presupuestados.
    assert estimacion['costo_estimado_usd'] == pytest.approx(.3318)
    assert estimacion['costos_por_paso']['reels'] == pytest.approx(.05)
    assert estimacion['costos_por_paso']['perfil'] == .013
    assert estimacion['costos_por_paso']['followers'] == pytest.approx(.2125)


def test_fallback_completa_metadata_del_mismo_reel_sin_duplicar(tmp_path):
    incompleto = reel('mismo')
    incompleto.duracion_segundos = None
    incompleto.audio_url = None
    incompleto.caption = 'Caption original conservado #publicidad'
    enriquecido = reel('mismo', 900, 20, caption='')
    motor = preparar(tmp_path, InstagramPrueba({'creadora': Perfil(usuario='creadora', followers=1000, posts=[incompleto])},
                                             posts_adicionales=[enriquecido]))
    resultado = motor.ejecutar(['creadora'], Opciones(reels=1, muestra_seguidores=0))
    assert resultado.corrida.estado == 'completa'
    assert motor.proveedores.instagram.llamadas['reels'] == 1
    assert motor.proveedores.audio.transcripciones == ['mismo']
    posts = motor.proveedores.clasificador.contextos[0]['perfil']['posts']
    assert len(posts) == 1 and posts[0]['caption'] == 'Caption original conservado #publicidad'
    assert posts[0]['duracion_segundos'] == 20


def test_unidades_remotas_inconsistentes_registran_costo_y_detienen(tmp_path):
    class InstagramInconsistente(InstagramPrueba):
        def relaciones(self, usuario, modo, limite):
            resultado = super().relaciones(usuario, modo, limite)
            self.ultimas_unidades = 1000
            return resultado
    motor = preparar(tmp_path, InstagramInconsistente())
    resultado = motor.ejecutar(['creadora', 'otra'], Opciones(reels=0, presupuesto_usd=.06))
    assert resultado.corrida.estado == 'limite_proveedor_excedido'
    assert resultado.corrida.costos_confirmados is False
    assert resultado.corrida.costo_total_usd == pytest.approx(.8526)
    assert motor.proveedores.instagram.llamadas['perfil'] == 1
    assert not motor.proveedores.clasificador.contextos
    assert any(c['estado'] == 'uso_inconsistente' for c in motor.almacen.costos(resultado.corrida.id))


def test_marcas_con_evidencia_ajena_no_se_guardan(tmp_path):
    class Inventado(ClasificadorPrueba):
        def clasificar(self, contexto):
            respuesta = super().clasificar(contexto)
            respuesta.datos.marcas = [Marca(nombre='Marca', tipo='publicidad', post_evidencia='https://inventada.example/')]
            return respuesta
    motor = preparar(tmp_path, clasificador=Inventado())
    resultado = motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert resultado.corrida.estado == 'completa_con_errores'
    assert resultado.perfiles[0].clasificacion is None
    motor.ejecutar(['creadora'], Opciones(reels=0, muestra_seguidores=0))
    assert len(motor.proveedores.clasificador.contextos) == 2
