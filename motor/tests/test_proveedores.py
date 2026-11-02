"""Pruebas de contratos HTTP con respuestas sintéticas guardadas; red bloqueada."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from motor.modelos import Post
from motor.proveedores.apify import ACTOR_PERFILES, ACTOR_RELACIONES, ACTOR_REELS, ApifyInstagram
from motor.proveedores.base import AudioDemasiadoGrande, AudioSinPista, ProveedorError, unidades_relaciones
from motor.proveedores.clasificacion import JevClasificador, OpenRouterClasificador
from motor.proveedores.falsos import AudioFalso, ClasificadorFalso, InstagramFalso
from motor.proveedores.groq import MAX_AUDIO_BYTES, GroqAudio

RUTA = Path(__file__).resolve().parents[1] / 'fixtures' / 'proveedores'


def fixture(nombre):
    return json.loads((RUTA / nombre).read_text(encoding='utf-8'))


def url_actor(actor):
    return f'https://api.apify.com/v2/acts/{actor.replace("/", "~")}/run-sync-get-dataset-items'


@respx.mock
def test_perfil_apify_normaliza_posts_likes_ocultos_y_comerciales():
    ruta = respx.post(url_actor(ACTOR_PERFILES)).mock(return_value=httpx.Response(200, json=fixture('apify_perfil.json')))
    proveedor = ApifyInstagram('secreto_sintetico', max_costo_usd_por_llamada=0.0026)
    perfil = proveedor.obtener_perfil('@cuenta.ficticia1')
    assert perfil.followers == 107200 and perfil.verificada
    assert perfil.posts[0].es_reel and perfil.posts[0].patrocinado
    assert perfil.posts[0].patrocinadores == ['marca.sintetica']
    assert perfil.posts[1].likes is None and perfil.posts[1].likes_ocultos
    solicitud = ruta.calls.last.request
    assert json.loads(solicitud.content) == {'usernames': ['cuenta.ficticia1']}
    assert solicitud.headers['Authorization'] == 'Bearer secreto_sintetico'
    assert 'secreto_sintetico' not in str(solicitud.url)
    assert float(solicitud.url.params['maxTotalChargeUsd']) == 0.0026
    proveedor.close()


@respx.mock
@pytest.mark.parametrize(('modo','valor'), [('followers','Followers'),('following','Followings')])
def test_relaciones_contrato_sin_cookies_menor_al_minimo_y_recorte(modo, valor):
    ruta = respx.post(url_actor(ACTOR_RELACIONES)).mock(return_value=httpx.Response(200, json=fixture('apify_relaciones.json')))
    proveedor = ApifyInstagram('clave_sintetica')
    seguidores = proveedor.relaciones('cuenta.ficticia1', modo, 1)
    assert len(seguidores) == 1 and seguidores[0].usuario == 'persona.uno'
    assert proveedor.ultimas_unidades == 3
    assert json.loads(ruta.calls.last.request.content) == {'Account':['cuenta.ficticia1'], 'dataToScrape':valor, 'resultsLimit':25}
    assert unidades_relaciones(1) == 25 and unidades_relaciones(30) == 30 and unidades_relaciones(0) == 0
    assert 'cookie' not in ruta.calls.last.request.headers
    assert proveedor.relaciones('cuenta.ficticia1', modo, 0) == []
    assert ruta.call_count == 1
    proveedor.close()


@respx.mock
def test_reels_completa_sin_extras_de_pago():
    ruta = respx.post(url_actor(ACTOR_REELS)).mock(return_value=httpx.Response(200, json=fixture('apify_reels.json')))
    proveedor = ApifyInstagram('clave_sintetica')
    reels = proveedor.obtener_reels('cuenta.ficticia1', 5)
    assert reels[0].duracion_segundos == 60 and reels[0].audio_url.endswith('audio1.mp4')
    assert json.loads(ruta.calls.last.request.content) == {
        'username':['cuenta.ficticia1'], 'resultsLimit':5, 'includeTranscript':False, 'includeDownloadedVideo':False}
    proveedor.close()


@respx.mock
def test_figue_tiene_su_propio_esquema_y_aliases():
    dato={'username':'cuenta.ficticia2','full_name':'Chef sintético','followersCount':54300,'is_verified':True,
          'category_name':'Chef','latestPosts':[{'id':'f','type':'Video','productType':'clips','video_url':'https://cdn.example.org/f.mp4',
          'video_view_count':100,'likesCount':20,'commentsCount':2,'like_and_view_counts_disabled':True}]}
    ruta = respx.post(url_actor('figue/instagram-profile-scraper')).mock(return_value=httpx.Response(200,json=[dato]))
    proveedor=ApifyInstagram('clave_sintetica',actor_perfiles='figue/instagram-profile-scraper')
    perfil=proveedor.obtener_perfil('cuenta.ficticia2')
    assert perfil.nombre=='Chef sintético' and perfil.categoria=='Chef'
    assert perfil.posts[0].likes_ocultos and perfil.posts[0].likes is None
    assert json.loads(ruta.calls.last.request.content)=={'profiles':['cuenta.ficticia2'],'includeRecentPosts':True}
    proveedor.close()


@respx.mock
def test_apify_errores_sanitizados_y_no_reintenta_un_cobro():
    ruta=respx.post(url_actor(ACTOR_PERFILES)).mock(return_value=httpx.Response(408,json={'error':'secreto_sintetico'}))
    proveedor=ApifyInstagram('secreto_sintetico')
    with pytest.raises(ProveedorError) as error:
        proveedor.obtener_perfil('cuenta.ficticia1')
    assert 'secreto_sintetico' not in str(error.value) and 'https' not in str(error.value)
    assert ruta.call_count==1
    proveedor.close()


@respx.mock
def test_apify_no_persiste_cuerpo_remoto_con_tokens_en_notas(tmp_path):
    from motor.almacen import Almacen
    from motor.modelos import Opciones
    from motor.tuberia import Motor, Proveedores
    ruta = respx.post(url_actor(ACTOR_PERFILES)).mock(return_value=httpx.Response(401, json={
        'error': {'type': 'clave_falsa_filtrada',
                  'message': 'https://proveedor.example/?token=clave_falsa_filtrada'},
    }))
    proveedor = ApifyInstagram('clave_falsa_filtrada')
    try:
        with pytest.raises(ProveedorError) as error:
            proveedor.obtener_perfil('cuenta.ficticia1')
        assert ACTOR_PERFILES in str(error.value) and 'HTTP 401' in str(error.value)
        assert 'clave_falsa_filtrada' not in str(error.value) and 'https://' not in str(error.value)
        motor = Motor(Proveedores(proveedor, AudioFalso(), ClasificadorFalso()),
                      Almacen(tmp_path / 'errores.sqlite'))
        resultado = motor.ejecutar(['cuenta.ficticia1'], Opciones())
        assert resultado.corrida.estado == 'completa_con_errores'
        assert resultado.perfiles[0].notas
        assert 'clave_falsa_filtrada' not in resultado.model_dump_json()
        assert 'https://' not in resultado.model_dump_json()
        assert ruta.call_count == 2  # Una llamada por ejecución; sin reintentos.
    finally:
        proveedor.close()


@respx.mock
@pytest.mark.parametrize(('datos','existe','privada'), [([],False,False),([{'error':'not_found'}],False,False),([{'error':'private'}],True,True)])
def test_perfiles_ausentes_y_privados(datos, existe, privada):
    respx.post(url_actor(ACTOR_PERFILES)).mock(return_value=httpx.Response(200,json=datos))
    proveedor=ApifyInstagram('clave_sintetica')
    perfil=proveedor.obtener_perfil('cuenta.ficticia1')
    assert perfil.existe is existe and perfil.privada is privada
    proveedor.close()


@respx.mock
def test_groq_descarga_publica_y_multipart_con_respuesta_guardada():
    respx.get('https://cdn.example.org/audio.mp4').mock(return_value=httpx.Response(200,content=b'audio_sintetico'))
    ruta=respx.post('https://api.groq.com/openai/v1/audio/transcriptions').mock(return_value=httpx.Response(200,json=fixture('groq_transcripcion.json')))
    proveedor=GroqAudio('clave_sintetica')
    post=Post(url='https://www.instagram.com/reel/PRUEBA/',tipo='reel',duracion_segundos=60,audio_url='https://cdn.example.org/audio.mp4')
    audio=proveedor.descargar_audio(post)
    assert proveedor.transcribir(audio,post).startswith('Este es un anuncio')
    solicitud=ruta.calls.last.request
    assert 'multipart/form-data' in solicitud.headers['content-type']
    assert b'whisper-large-v3-turbo' in solicitud.content and b'audio_sintetico' in solicitud.content
    assert solicitud.headers['authorization']=='Bearer clave_sintetica'
    proveedor.close()


@respx.mock
def test_apify_lotes_agrupan_perfiles_y_reels_por_usuario():
    perfiles = respx.post(url_actor(ACTOR_PERFILES)).mock(return_value=httpx.Response(200, json=[
        {'username': 'cuenta.uno', 'followersCount': 10, 'latestPosts': []},
        {'username': 'Cuenta.Dos', 'followersCount': 20, 'latestPosts': []},
        {'username': 'ajena', 'followersCount': 1},
    ]))
    reels = respx.post(url_actor(ACTOR_REELS)).mock(return_value=httpx.Response(200, json=[
        {'ownerUsername': 'cuenta.uno', 'url': 'https://www.instagram.com/reel/A/', 'videoDuration': 20},
        {'ownerUsername': 'cuenta.uno', 'url': 'https://www.instagram.com/reel/B/', 'videoDuration': 30},
        {'ownerUsername': 'cuenta.dos', 'url': 'https://www.instagram.com/reel/C/', 'videoDuration': 40},
    ]))
    proveedor = ApifyInstagram('clave_sintetica')
    salida = proveedor.obtener_perfiles(['cuenta.uno', 'cuenta.dos', 'cuenta.tres'])
    assert set(salida) == {'cuenta.uno', 'cuenta.dos'} and salida['cuenta.dos'].followers == 20
    assert json.loads(perfiles.calls.last.request.content)['usernames'] == ['cuenta.uno', 'cuenta.dos', 'cuenta.tres']
    por_usuario = proveedor.obtener_reels_lote(['cuenta.uno', 'cuenta.dos'], 1)
    assert [p.url for p in por_usuario['cuenta.uno']] == ['https://www.instagram.com/reel/A/']
    assert por_usuario['cuenta.dos'][0].duracion_segundos == 40
    assert 'maxItems=2' in str(reels.calls.last.request.url)
    proveedor.close()


def test_apify_tope_de_costo_es_por_hilo():
    import threading
    proveedor = ApifyInstagram('clave_sintetica')
    proveedor.set_limite_costo(0.5)
    visto = []
    hilo = threading.Thread(target=lambda: visto.append(proveedor.max_costo_usd_por_llamada))
    hilo.start(); hilo.join()
    assert proveedor.max_costo_usd_por_llamada == 0.5 and visto == [None]
    proveedor.close()


@respx.mock
def test_groq_reel_sin_pista_de_audio_y_error_con_motivo_sin_llave():
    ruta = respx.post('https://api.groq.com/openai/v1/audio/transcriptions')
    proveedor = GroqAudio('clave_sintetica')
    post = Post(url='https://www.instagram.com/reel/MUDO/', tipo='reel', duracion_segundos=20)
    ruta.mock(return_value=httpx.Response(400, json={'error': {'message': 'no audio track found in file'}}))
    with pytest.raises(AudioSinPista):
        proveedor.transcribir(b'video', post)
    ruta.mock(return_value=httpx.Response(500, json={'error': {'message': 'Fallo clave_sintetica https://x.example/y'}}))
    with pytest.raises(ProveedorError) as error:
        proveedor.transcribir(b'video', post)
    assert 'HTTP 500' in str(error.value) and 'Fallo' in str(error.value)
    assert 'clave_sintetica' not in str(error.value) and 'https://' not in str(error.value)
    proveedor.close()


@respx.mock
def test_groq_reintenta_429_corto_y_se_rinde_con_espera_larga():
    from motor.proveedores.base import LimiteProveedor
    esperas = []
    proveedor = GroqAudio('clave_sintetica', dormir=esperas.append)
    post = Post(url='https://www.instagram.com/reel/X/', tipo='reel', duracion_segundos=20)
    ruta = respx.post('https://api.groq.com/openai/v1/audio/transcriptions')
    ruta.side_effect = [httpx.Response(429, headers={'retry-after': '3'}), httpx.Response(200, json={'text': 'hola'})]
    assert proveedor.transcribir(b'video', post) == 'hola'
    assert esperas == [3.0]
    # Tope por hora o por día: no se espera minutos, se omite ese audio.
    ruta.side_effect = [httpx.Response(429, headers={'retry-after': '900'})]
    with pytest.raises(LimiteProveedor):
        proveedor.transcribir(b'video', post)
    proveedor.close()


def test_groq_respeta_solicitudes_por_minuto():
    ahora = [0.0]
    esperas = []
    def dormir(segundos):
        esperas.append(segundos)
        ahora[0] += segundos
    proveedor = GroqAudio('clave_sintetica', rpm=2, dormir=dormir, reloj=lambda: ahora[0])
    for _ in range(3):
        proveedor._turno()
    # La tercera espera a que salga la primera del último minuto.
    assert len(esperas) == 1 and esperas[0] == pytest.approx(60.05)
    proveedor.close()


@respx.mock
def test_groq_omite_archivo_de_mas_de_25_mb_antes_de_transcribir():
    respx.get('https://cdn.example.org/grande.mp4').mock(return_value=httpx.Response(200,headers={'Content-Length':str(MAX_AUDIO_BYTES+1)}))
    ruta=respx.post('https://api.groq.com/openai/v1/audio/transcriptions')
    proveedor=GroqAudio('clave_sintetica')
    with pytest.raises(AudioDemasiadoGrande):
        proveedor.descargar_audio(Post(audio_url='https://cdn.example.org/grande.mp4',duracion_segundos=60))
    assert not ruta.called
    proveedor.close()


@respx.mock
def test_groq_limite_se_aplica_tambien_sin_content_length():
    respx.get('https://cdn.example.org/grande.mp4').mock(return_value=httpx.Response(200,content=b'x'*(MAX_AUDIO_BYTES+1)))
    proveedor=GroqAudio('clave_sintetica')
    with pytest.raises(AudioDemasiadoGrande):
        proveedor.descargar_audio(Post(audio_url='https://cdn.example.org/grande.mp4',duracion_segundos=60))
    proveedor.close()


@respx.mock
@pytest.mark.parametrize('duracion',[None,0,181])
def test_groq_duracion_no_segura_no_llama(duracion):
    proveedor=GroqAudio('clave_sintetica')
    with pytest.raises(ProveedorError,match='duración'):
        proveedor.transcribir(b'audio',Post(duracion_segundos=duracion))
    proveedor.close()


@respx.mock
def test_jev_contrato_oficial_y_seguidores_identificados_por_usuario():
    ruta=respx.post('https://api.typesafe.ai/v1/systemone').mock(return_value=httpx.Response(200,json=fixture('jev_respuesta.json')))
    proveedor=JevClasificador('clave_sintetica')
    contexto=fixture('contexto_clasificacion.json')
    respuesta=proveedor.clasificar(contexto)
    # Dos peticiones (creador y seguidores); el mock devuelve 1234 en cada una.
    assert ruta.call_count==2 and respuesta.tokens_entrada==2468
    seguidores={s.usuario:s for s in respuesta.datos.seguidores}
    assert seguidores['persona.uno'].genero=='Female'
    assert seguidores['persona.dos'].edad=='35-44' and seguidores['persona.dos'].genero=='Male'
    assert seguidores['tienda.sintetica'].persona_real is False and seguidores['tienda.sintetica'].edad is None
    assert {m.tipo for m in respuesta.datos.marcas}=={'publicidad','amigo_fotografo'}
    # El tamaño se pregunta solo para marcas de posts de publicidad y se guarda solo en las comerciales.
    assert {m.nombre: m.tamano for m in respuesta.datos.marcas}=={'marca.sintetica':'grande','foto.sintetica':None}
    creador=json.loads(ruta.calls[0].request.content)
    entrada=json.loads(ruta.calls[1].request.content)
    assert entrada['model']=='jev-latest' and 'messages' not in entrada
    assert set(entrada['state'])=={'seguidores_por_usuario'} and 'seguidores_por_usuario' not in creador['state']
    assert not any(k.startswith('seguidor:') for k in creador['questions'])
    assert set(entrada['state']['seguidores_por_usuario'])==set(seguidores)
    for u in seguidores:
        instrucciones=entrada['questions'][f'seguidor:{u}:genero']['instructions']
        assert f'@{u}' in instrucciones and 'no adivines' not in instrucciones
    total=sum(len(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()) for x in (creador,entrada))
    assert proveedor.estimar_tokens(contexto)>=total
    proveedor.close()


@respx.mock
def test_jev_confianza_baja_no_se_disfraza_de_dato():
    datos=fixture('jev_respuesta.json')
    datos['answers']['audiencia_a_genero']['confidence']=0.1
    datos['answers']['audiencia_a_edad']['confidence']=0.1
    respx.post('https://api.typesafe.ai/v1/systemone').mock(return_value=httpx.Response(200,json=datos))
    proveedor=JevClasificador('clave_sintetica')
    audiencia = proveedor.clasificar(fixture('contexto_clasificacion.json')).datos.audiencia_a
    assert audiencia.genero is None
    # Edad y ciudad son estimaciones declaradas (como Modash): se toma la más probable aunque la confianza sea baja.
    assert audiencia.edad == '25-34'
    proveedor.close()


@respx.mock
def test_jev_rechaza_opciones_inventadas_sin_fallback_cobrado():
    datos=fixture('jev_respuesta.json')
    datos['answers']['audiencia_a_genero']['choice']='inventado'
    ruta=respx.post('https://api.typesafe.ai/v1/systemone').mock(return_value=httpx.Response(200,json=datos))
    proveedor=JevClasificador('secreto_sintetico')
    with pytest.raises(ProveedorError) as error:
        proveedor.clasificar(fixture('contexto_clasificacion.json'))
    # Se envían las dos partes y no hay una tercera llamada de respaldo.
    assert ruta.call_count==2 and 'secreto_sintetico' not in str(error.value)
    proveedor.close()


@respx.mock
def test_openrouter_respaldo_explicito_json_schema_y_usage():
    ruta=respx.post('https://openrouter.ai/api/v1/chat/completions').mock(return_value=httpx.Response(200,json=fixture('openrouter_respuesta.json')))
    proveedor=OpenRouterClasificador('clave_sintetica','modelo/sintetico')
    respuesta=proveedor.clasificar(fixture('contexto_clasificacion.json'))
    assert respuesta.tokens_entrada==1234 and respuesta.tokens_salida==456
    entrada=json.loads(ruta.calls.last.request.content)
    assert entrada['response_format']['type']=='json_schema'
    esquema=entrada['response_format']['json_schema']['schema']
    assert set(esquema['required'])==set(esquema['properties'])
    assert entrada['provider']['require_parameters'] is True
    assert respuesta.datos.seguidores[0].usuario=='persona.dos'
    proveedor.close()


@respx.mock
def test_falsos_reproducibles_sin_http():
    instagram=InstagramFalso()
    perfil=instagram.obtener_perfil('cuenta.ficticia1')
    seguidores=instagram.relaciones(perfil.usuario,'followers',30)
    audio=AudioFalso()
    texto=audio.transcribir(audio.descargar_audio(perfil.posts[0]),perfil.posts[0])
    clasificador=ClasificadorFalso()
    respuesta=clasificador.clasificar({'perfil':perfil.model_dump(),'seguidores':[s.model_dump() for s in seguidores],
                                     'transcripciones':{perfil.posts[0].url:texto},'brief':{}})
    assert respuesta.datos.categoria=='Salud & Nutrición'
    assert respuesta.datos.encaje is None
    assert {s.usuario for s in respuesta.datos.seguidores}=={s.usuario for s in seguidores}
    assert instagram.contadores['perfil']==1 and audio.transcripciones==1 and clasificador.contador==1


@respx.mock
def test_jev_recorta_textos_largos_en_vez_de_rechazar():
    proveedor = JevClasificador('clave_sintetica')
    contexto = fixture('contexto_clasificacion.json')
    contexto['perfil']['bio'] = 'bio extensa ' * 6000
    for post in contexto['perfil']['posts']:
        post['caption'] = 'caption largo de prueba ' * 800
        contexto.setdefault('transcripciones', {})[post['url']] = 'transcripción larga de un reel ' * 1300
    assert proveedor.estimar_tokens(contexto) <= 64000 * 2
    estado = proveedor.preparar(contexto)['state']
    assert len(estado['creador']['bio']) <= 501
    assert all(len(p['caption']) <= 1501 for p in estado['posts'])
    proveedor.close()


def test_jev_reparte_muchas_marcas_en_varias_peticiones():
    from motor.proveedores.clasificacion import LIMITE_PARTE, _json
    proveedor = JevClasificador('clave_sintetica')
    contexto = fixture('contexto_clasificacion.json')
    for indice, post in enumerate(contexto['perfil']['posts']):
        post['menciones'] = [f'marca{indice}x{i:02d}' for i in range(30)]
    entrada = proveedor.preparar(contexto)
    partes = proveedor._partes(entrada)
    assert len(partes) > 2
    assert all(len(_json(parte).encode('utf-8')) + 4096 <= LIMITE_PARTE for parte in partes)
    repartidas = [clave for parte in partes for clave in parte['questions']]
    assert sorted(repartidas) == sorted(entrada['questions'])
    proveedor.estimar_tokens(contexto)
    proveedor.close()


@respx.mock
def test_jev_contexto_excesivo_se_rechaza_antes_de_llamar():
    proveedor = JevClasificador('clave_sintetica')
    contexto = fixture('contexto_clasificacion.json')
    # Lo que no se recorta (menciones) puede seguir excediendo la cota.
    contexto['perfil']['posts'][0]['menciones'] = [f'cuenta{i:05d}' for i in range(6000)]
    with pytest.raises(ProveedorError, match='cota conservadora'):
        proveedor.estimar_tokens(contexto)
    with pytest.raises(ProveedorError, match='cota conservadora'):
        proveedor.clasificar(contexto)
    assert not respx.calls
    proveedor.close()


@respx.mock
def test_marca_sin_etiqueta_en_audio_tiene_evidencia_de_reel():
    contexto = fixture('contexto_marcas_audio.json')
    respx.post('https://api.typesafe.ai/v1/systemone').mock(return_value=httpx.Response(200, json=fixture('jev_marcas_audio.json')))
    proveedor = JevClasificador('clave_sintetica')
    respuesta = proveedor.clasificar(contexto)
    assert len(respuesta.datos.marcas) == 1
    marca = respuesta.datos.marcas[0]
    assert marca.nombre == 'Nike' and marca.tipo == 'colab'
    assert marca.post_evidencia == contexto['perfil']['posts'][0]['url']
    assert contexto['perfil']['posts'][0]['caption'] == ''
    proveedor.close()



def test_whisper_local_sin_costo_y_sin_llave():
    from motor.proveedores.groq import WhisperLocalAudio
    proveedor = WhisperLocalAudio('small')
    assert proveedor.paso_costo == 'transcripcion_local' and proveedor.identidad == 'local:whisper-small'
    proveedor.close()


def test_tarifa_local_y_estimacion_sin_transcripcion():
    from motor.costos import Precios, estimar_costo
    from motor.modelos import Opciones
    precios = Precios()
    assert precios.costo('transcripcion_local', 3600) == 0
    sin_audio = estimar_costo(2, Opciones(reels=0, muestra_seguidores=25), precios, paso_transcripcion=None)
    assert 'transcripcion' not in sin_audio['costos_por_paso']
    local = estimar_costo(1, Opciones(reels=1, muestra_seguidores=0), precios, paso_transcripcion='transcripcion_local')
    assert local['costos_por_paso']['transcripcion_local'] == 0


def test_descripcion_corta_al_estilo_de_la_agencia():
    from motor.proveedores.clasificacion import describir
    assert describir('presentadora', 'lifestyle', 'Female') == 'Presentadora / lifestyle'
    assert describir('presentadora', 'ninguno', 'Male') == 'Presentador'
    # El nicho no se repite si ya está en el rol.
    assert describir('lifestyle', 'lifestyle', None) == 'Lifestyle personal'
    assert describir(None, 'moda', 'Female') == ''
    assert describir('belleza', 'maternidad', 'Female') == 'Belleza / skincare'


@respx.mock
def test_jev_guarda_probabilidades_de_audiencia_y_la_ficha_las_reparte_por_genero():
    from motor.presentacion import estimacion_audiencia
    respx.post('https://api.typesafe.ai/v1/systemone').mock(return_value=httpx.Response(200, json=fixture('jev_respuesta.json')))
    proveedor = JevClasificador('clave_sintetica')
    probabilidades = proveedor.clasificar(fixture('contexto_clasificacion.json')).datos.probabilidades
    proveedor.close()
    assert set(probabilidades) == {'edad', 'genero', 'ciudad', 'segmento'}
    assert 'desconocido' not in probabilidades['genero'] and probabilidades['segmento']['Female 25-34'] == 0.7
    estimacion = estimacion_audiencia({**probabilidades, 'ciudad': {'Lima': 0.8, 'Bogotá': 0.15, 'Trujillo': 0.05}})
    # 25-34 tiene toda la probabilidad de edad; el segmento la parte 0.7 / 0.2 entre mujeres y hombres.
    assert estimacion['edad_genero']['25-34']['Female'] == pytest.approx(0.7 / 0.9)
    assert estimacion['edad_genero']['18-24'] == {'Female': 0, 'Male': 0}
    assert estimacion['pais'] == pytest.approx({'Perú': 0.85, 'Colombia': 0.15})
    assert list(estimacion['ciudad']) == ['Lima', 'Bogotá', 'Trujillo']
