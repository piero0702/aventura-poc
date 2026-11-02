"""Orquestación síncrona por pasos, con proveedores reemplazables y caché de 30 días."""
from __future__ import annotations
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from threading import Event, Lock
from time import monotonic, sleep
from typing import Callable
from uuid import uuid4
from motor.almacen import Almacen
from motor.costos import Precios, RegistroCostos, PresupuestoAgotado, LimiteProveedorExcedido
from motor.filtro import motivo_descarte
from motor.metricas import calcular_metricas
from motor.publicidad import es_publicidad, reels_a_revisar
from motor.modelos import (Audiencia, Clasificacion, Corrida, Opciones, Perfil, Post,
    ResultadoCorrida, ResultadoPerfil, Seguidor, normalizar_usuario)

from motor.proveedores import Proveedores, ProveedorError
from motor.proveedores.base import AudioSinPista, LimiteProveedor


def clave_cache(proveedor, parametros) -> str:
    identidad = getattr(proveedor, 'identidad', type(proveedor).__name__)
    contenido = json.dumps({'proveedor': identidad, 'parametros': parametros}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(contenido.encode('utf-8')).hexdigest()


# Con menos seguidores con edad estimada, la mayoría de la muestra no dice nada: decide la estimación por contenido.
MINIMO_EDAD_MUESTRA = 5


def agregar_audiencia(clasificacion: Clasificacion, seguidores: list[Seguidor]):
    """Agrega por usuario único. Desconocidos no cuentan como personas reales.

    Calidad = reales / total de usuarios recibidos. Edad/género mayoritarios sobre
    todas las cuentas salvo las marcadas como no personales (marca, negocio, bot),
    con inferencia disponible; empates se dejan sin dato.
    La muestra es de conveniencia y no demuestra demografía real de la audiencia.
    """
    por_usuario = {seguidor.usuario: seguidor for seguidor in seguidores}
    inferencias = {}
    for inferencia in clasificacion.seguidores:
        if inferencia.usuario not in por_usuario or inferencia.usuario in inferencias:
            raise ValueError('Clasificación de seguidores con usuario ajeno o duplicado')
        inferencias[inferencia.usuario] = inferencia
    if set(inferencias) != set(por_usuario):
        raise ValueError('Faltan usuarios de la muestra en la clasificación')
    if not por_usuario:
        return None, None
    personas = [i for i in inferencias.values() if i.persona_real is True]
    no_excluidas = [i for i in inferencias.values() if i.persona_real is not False]
    def mayoria(campo):
        conteos = Counter(getattr(i, campo) for i in no_excluidas if getattr(i, campo) not in (None, '', 'Unknown'))
        if campo == 'edad' and sum(conteos.values()) < MINIMO_EDAD_MUESTRA:
            return None
        orden = conteos.most_common()
        return orden[0][0] if orden and (len(orden) == 1 or orden[0][1] > orden[1][1]) else None
    return Audiencia(edad=mayoria('edad'), genero=mayoria('genero')), len(personas) / len(por_usuario)


# Tramo del avance global (0-100) que ocupa cada fase de la corrida.
TRAMOS = {'seguidos': (0, 5), 'perfiles': (5, 15), 'reels': (15, 30), 'analisis': (30, 97)}
# Fracción de un perfil ya recorrida al empezar cada paso de su análisis.
PESO_PASO = {'perfiles': 0, 'filtro': .05, 'reels': .1, 'transcripcion': .2, 'seguidores': .45, 'clasificacion': .7}
ACTIVIDADES = {'perfiles': 'Leyendo perfiles', 'filtro': 'Revisando criterios', 'reels': 'Revisando reels',
               'transcripcion': 'Transcribiendo reels', 'seguidores': 'Estimando la audiencia',
               'clasificacion': 'Clasificando y buscando marcas'}


class Motor:
    def __init__(self, proveedores: Proveedores, almacen: Almacen | None = None, precios: Precios | None = None,
                 simulado=False, metricas_agregacion='promedio', simulado_retraso_s=0, paralelo=1):
        self.simulado = simulado
        self.paralelo = paralelo
        self._bloqueo_audio = Lock()
        if metricas_agregacion not in {'promedio', 'mediana'}:
            raise ValueError('METRICAS_AGREGACION debe ser promedio o mediana')
        self.metricas_agregacion = metricas_agregacion
        self.simulado_retraso_s = simulado_retraso_s
        self.proveedores = proveedores
        self.almacen = almacen or Almacen()
        self.precios = precios or Precios()

    def _llamada(self, registro, usuario, paso, unidades, funcion, reales=None):
        reserva = registro.reservar(usuario, paso, unidades)
        if paso in {'perfil', 'reels', 'followers', 'following'}:
            limitar = getattr(self.proveedores.instagram, 'set_limite_costo', None)
            if limitar:
                limitar(float(reserva[1]))
        # Sin reintentos automáticos: una respuesta perdida puede ser facturable.
        try:
            resultado = funcion()
        except (AudioSinPista, LimiteProveedor):
            # El proveedor rechaza la petición antes de procesarla: no hay cobro que reservar.
            registro.confirmar(reserva, paso, 0)
            raise
        registro.confirmar(reserva, paso, reales(resultado) if reales else unidades)
        return resultado

    def _relaciones(self, usuario, modo, limite, registro):
        if not 1 <= limite <= 500000:
            raise ValueError('El límite de relaciones debe estar entre 1 y 500000')
        proveedor = self.proveedores.instagram
        clave = clave_cache(proveedor, {'modo': modo, 'limite': limite})
        previo = self.almacen.obtener(usuario, modo, clave)
        if previo is not None:
            return [Seguidor.model_validate(s) for s in previo]
        seguidores = self._llamada(registro, usuario, modo, max(25, limite),
            lambda: proveedor.relaciones(usuario, modo, limite),
            lambda s: getattr(proveedor, 'ultimas_unidades', len(s)))
        seguidores = list({s.usuario: s for s in seguidores}.values())[:limite]
        self.almacen.guardar(usuario, modo, [s.model_dump() for s in seguidores], clave)
        return seguidores

    def ejecutar(self, usuarios: list[str] | None, opciones: Opciones, referencia: str | None = None,
                 corrida_id: str | None = None,
                 al_avanzar: Callable[[str, int, int, int], None] | None = None) -> ResultadoCorrida:
        """Notifica inicio y fin de cada paso realizado, también cuando usa caché.

        Los contadores son perfiles completados en ese paso; la tubería recorre
        los pasos por perfil. Excel se notifica en el llamador al exportarlo.
        """
        if (usuarios is None) == (referencia is None):
            raise ValueError('Indica usuarios o una referencia')
        if opciones.brief.followers_max is not None and opciones.brief.followers_max < opciones.brief.followers_min:
            raise ValueError('Rango de followers inválido')
        inicio = monotonic()
        identificador = corrida_id or str(uuid4())
        corrida = Corrida(id=identificador, fecha=datetime.now(timezone.utc).isoformat(), ejecucion_simulada=self.simulado,
                          parametros={**opciones.model_dump(), 'referencia': referencia,
                                      'metricas_agregacion': self.metricas_agregacion})
        registro = RegistroCostos(self.almacen, self.precios, identificador, opciones.presupuesto_usd)
        bloqueo = Lock()
        avance = {'porcentaje': 0.0, 'listos': 0, 'descartados': 0, 'en_curso': {},
                  'total': len(usuarios) if usuarios is not None else (opciones.limite or 200)}

        def publicar(fase, fraccion, actividad):
            """Avance de toda la lista; solo sube. Se llama con el bloqueo tomado."""
            desde, hasta = TRAMOS[fase]
            avance['porcentaje'] = max(avance['porcentaje'], desde + (hasta - desde) * min(1.0, fraccion))
            if al_avanzar:
                al_avanzar(fase, avance['listos'], avance['total'], avance['descartados'],
                           porcentaje=round(avance['porcentaje'], 1), en_curso=len(avance['en_curso']),
                           actividad=actividad)

        def fraccion_analisis():
            total = avance['total'] or 1
            return (avance['listos'] + sum(avance['en_curso'].values())) / total

        def avanzar_de(usuario):
            def avanzar(paso, terminado=False):
                with bloqueo:
                    if not terminado:
                        avance['en_curso'][usuario] = max(avance['en_curso'].get(usuario, 0), PESO_PASO.get(paso, 0))
                    en_curso = len(avance['en_curso'])
                    publicar('analisis', fraccion_analisis(),
                             f'{ACTIVIDADES.get(paso, "Analizando")} · {en_curso} '
                             f'{"perfil" if en_curso == 1 else "perfiles"} en curso')
                if self.simulado and self.simulado_retraso_s and not terminado:
                    sleep(self.simulado_retraso_s)
            return avanzar

        def terminar(usuario, descartado):
            with bloqueo:
                avance['en_curso'].pop(usuario, None)
                avance['listos'] += 1
                avance['descartados'] += int(descartado)
                publicar('analisis', fraccion_analisis(), f'{avance["listos"]} de {avance["total"]} perfiles listos')

        if referencia is not None:
            referencia = normalizar_usuario(referencia)
            try:
                with bloqueo:
                    publicar('seguidos', 0, 'Buscando los perfiles que sigue la cuenta de referencia')
                if self.simulado and self.simulado_retraso_s:
                    sleep(self.simulado_retraso_s)
                usuarios = [s.usuario for s in self._relaciones(referencia, 'following', opciones.limite or 200, registro)]
                with bloqueo:
                    publicar('seguidos', 1, f'{len(usuarios)} perfiles encontrados')
                corrida.notas.append('Los seguidos públicos pueden ser parciales; límite por defecto: 200')
            except PresupuestoAgotado as exc:
                usuarios = []
                corrida.estado = 'limite_proveedor_excedido' if isinstance(exc, LimiteProveedorExcedido) else 'presupuesto_agotado'
                corrida.notas.append('Presupuesto insuficiente antes de consultar los seguidos')
            except Exception:
                usuarios = []
                corrida.estado = 'completa_con_errores'
                corrida.notas.append('Falló el proveedor de seguidos; reserva de costo conservada si se envió la petición')
        usuarios = list(dict.fromkeys(normalizar_usuario(u) for u in usuarios))
        if opciones.limite:
            usuarios = usuarios[:opciones.limite]
        corrida.perfiles_solicitados = len(usuarios)
        if referencia is None:
            corrida.parametros['usuarios'] = usuarios
        avance['total'] = len(usuarios)
        resultados = [ResultadoPerfil(perfil=Perfil(usuario=usuario), perfil_obtenido=False) for usuario in usuarios]

        # Lotes: perfiles y reels de toda la lista en una corrida de Apify cada uno. Dejan la caché
        # lista; si un lote falla, cada perfil se pide después por separado como antes.
        self._precargar_perfiles(usuarios, registro, corrida, bloqueo, publicar)
        self._precargar_reels(usuarios, opciones, registro, corrida, bloqueo, publicar)

        detener = Event()

        def trabajar(indice, usuario):
            resultado = resultados[indice]
            if detener.is_set():
                resultado.notas.append('No procesado: presupuesto agotado')
                terminar(usuario, False)
                return
            try:
                self._procesar(resultado, opciones, registro, avanzar_de(usuario))
                with bloqueo:
                    corrida.perfiles_procesados += 1
            except PresupuestoAgotado as exc:
                detener.set()
                with bloqueo:
                    corrida.estado = 'limite_proveedor_excedido' if isinstance(exc, LimiteProveedorExcedido) else 'presupuesto_agotado'
                resultado.notas.append('Procesamiento detenido: unidades del proveedor superiores al máximo reservado' if isinstance(exc, LimiteProveedorExcedido) else 'Procesamiento incompleto: presupuesto agotado antes de la siguiente llamada')
            except Exception as exc:
                with bloqueo:
                    if corrida.estado == 'completa':
                        corrida.estado = 'completa_con_errores'
                # Los mensajes de ProveedorError ya vienen saneados; de otros errores solo se muestra el tipo.
                detalle = f'{type(exc).__name__}: {exc}' if isinstance(exc, ProveedorError) else type(exc).__name__
                resultado.notas.append(f'Error de proveedor o datos ({detalle}): procesamiento incompleto; '
                                       'la reserva de una llamada fallida se conserva')
            terminar(usuario, resultado.descartado)

        if self.paralelo > 1 and len(usuarios) > 1:
            with ThreadPoolExecutor(max_workers=self.paralelo) as grupo:
                list(grupo.map(lambda par: trabajar(*par), enumerate(usuarios)))
        else:
            for indice, usuario in enumerate(usuarios):
                trabajar(indice, usuario)
        costos = self.almacen.costos(identificador)
        costo_referencia = sum(c['costo_usd'] for c in costos if c['paso'] == 'following')
        for resultado in resultados:
            resultado.costo_usd = sum(c['costo_usd'] for c in costos
                if c['usuario'] == resultado.perfil.usuario and c['paso'] != 'following')
            resultado.costo_usd += costo_referencia / len(resultados) if resultados else 0
        corrida.duracion_segundos = monotonic() - inicio
        corrida.costo_total_usd = float(registro.total)
        corrida.costo_por_perfil_usd = corrida.costo_total_usd / corrida.perfiles_procesados if corrida.perfiles_procesados else 0
        for costo in costos:
            paso = costo['paso']
            corrida.costos_por_paso[paso] = corrida.costos_por_paso.get(paso, 0) + costo['costo_usd']
        corrida.costos_confirmados = all(c['estado'] == 'confirmado' for c in costos)
        if corrida.perfiles_procesados == 0 and corrida.costo_total_usd:
            corrida.notas.append('Hay costo registrado sin perfiles terminados; costo por perfil no evaluable')
        if not corrida.costos_confirmados:
            corrida.notas.append('Costo conservador: incluye reservas de llamadas sin confirmación; conciliar con factura de proveedor')
        self.almacen.guardar_corrida(identificador, corrida.model_dump())
        return ResultadoCorrida(perfiles=resultados, corrida=corrida)

    def _reservar_lote(self, usuarios, paso, unidades, registro):
        """Reserva perfil por perfil hasta donde alcance el presupuesto."""
        reservas = {}
        for usuario in usuarios:
            try:
                reservas[usuario] = registro.reservar(usuario, paso, unidades)
            except PresupuestoAgotado:
                break
        limitar = getattr(self.proveedores.instagram, 'set_limite_costo', None)
        if limitar and reservas:
            limitar(float(sum(reserva[1] for reserva in reservas.values())))
        return reservas

    def _precargar_perfiles(self, usuarios, registro, corrida, bloqueo, publicar):
        instagram = self.proveedores.instagram
        lote = getattr(instagram, 'obtener_perfiles', None)
        clave = clave_cache(instagram, {'posts': 12})
        pendientes = [u for u in usuarios if self.almacen.obtener(u, 'perfil', clave) is None]
        if lote is None or len(pendientes) < 2:
            return
        with bloqueo:
            publicar('perfiles', 0, f'Leyendo {len(pendientes)} perfiles en un solo lote')
        reservas = self._reservar_lote(pendientes, 'perfil', 1, registro)
        if not reservas:
            return
        try:
            perfiles = lote(list(reservas))
        except Exception:
            corrida.notas.append('Falló el lote de perfiles; se pidieron uno por uno (la reserva del lote se conserva)')
            return
        for usuario, reserva in reservas.items():
            perfil = perfiles.get(usuario)
            registro.confirmar(reserva, 'perfil', 1 if perfil else 0)
            if perfil is not None:
                self.almacen.guardar(usuario, 'perfil', perfil.model_dump(), clave)
        with bloqueo:
            publicar('perfiles', 1, f'{len(perfiles)} perfiles leídos')

    def _precargar_reels(self, usuarios, opciones, registro, corrida, bloqueo, publicar):
        instagram = self.proveedores.instagram
        lote = getattr(instagram, 'obtener_reels_lote', None)
        revisar = reels_a_revisar(opciones)
        if not revisar or lote is None:
            return
        clave_perfil = clave_cache(instagram, {'posts': 12})
        clave_reels = clave_cache(instagram, {'limite': revisar})
        pendientes = []
        for usuario in usuarios:
            datos = self.almacen.obtener(usuario, 'perfil', clave_perfil)
            if datos is None or self.almacen.obtener(usuario, 'reels', clave_reels) is not None:
                continue
            perfil = Perfil.model_validate(datos)
            if motivo_descarte(perfil, opciones.brief):
                continue
            # Misma condición que _procesar: solo si los posts no traen todos los reels a revisar.
            if sum(p.es_reel for p in perfil.posts) < revisar:
                pendientes.append(usuario)
        if len(pendientes) < 2:
            return
        with bloqueo:
            publicar('reels', 0, f'Buscando los reels de {len(pendientes)} perfiles en un solo lote')
        reservas = self._reservar_lote(pendientes, 'reels', revisar, registro)
        if not reservas:
            return
        try:
            reels = lote(list(reservas), revisar)
        except Exception:
            corrida.notas.append('Falló el lote de reels; se pidieron uno por uno (la reserva del lote se conserva)')
            return
        if not any(reels.values()):
            # Sin ningún reel asociado a su dueño no se puede distinguir de un fallo: se piden uno por uno.
            for reserva in reservas.values():
                registro.confirmar(reserva, 'reels', 0)
            return
        for usuario, reserva in reservas.items():
            lista = reels.get(usuario, [])
            registro.confirmar(reserva, 'reels', len(lista))
            self.almacen.guardar(usuario, 'reels', [p.model_dump() for p in lista], clave_reels)
        with bloqueo:
            publicar('reels', 1, 'Reels listos')

    def _transcribir(self, audio, contenido, post):
        # Whisper local usa un solo modelo en memoria: no admite varias transcripciones a la vez.
        if str(getattr(audio, 'identidad', '')).startswith('local:'):
            with self._bloqueo_audio:
                return audio.transcribir(contenido, post)
        return audio.transcribir(contenido, post)

    def _procesar(self, resultado, opciones, registro, avanzar):
        instagram, audio, clasificador = self.proveedores.instagram, self.proveedores.audio, self.proveedores.clasificador
        usuario = resultado.perfil.usuario
        avanzar('perfiles')
        clave = clave_cache(instagram, {'posts': 12})
        previo = self.almacen.obtener(usuario, 'perfil', clave)
        if previo is None:
            perfil = self._llamada(registro, usuario, 'perfil', 1, lambda: instagram.obtener_perfil(usuario))
            self.almacen.guardar(usuario, 'perfil', perfil.model_dump(), clave)
        else:
            perfil = Perfil.model_validate(previo)
        if perfil.usuario != usuario:
            raise ValueError('El proveedor devolvió otro usuario')
        resultado.perfil = perfil
        resultado.perfil_obtenido = True
        resultado.metricas = calcular_metricas(perfil.posts, perfil.followers, self.metricas_agregacion)
        avanzar('perfiles', True)
        avanzar('filtro')
        descarte = motivo_descarte(perfil, opciones.brief)
        if descarte:
            resultado.descartado = True
            resultado.notas.append(descarte)
            avanzar('filtro', True)
            return
        avanzar('filtro', True)
        transcripciones = {}
        posts_contexto = list(perfil.posts)
        revisar = reels_a_revisar(opciones)
        if revisar:
            avanzar('reels')
            posts = [p for p in perfil.posts if p.es_reel]
            if len(posts) < revisar:
                clave_reels = clave_cache(instagram, {'limite': revisar})
                anteriores = self.almacen.obtener(usuario, 'reels', clave_reels)
                if anteriores is None:
                    adicionales = self._llamada(registro, usuario, 'reels', revisar,
                        lambda: instagram.obtener_reels(usuario, revisar), lambda p: len(p))
                    self.almacen.guardar(usuario, 'reels', [p.model_dump() for p in adicionales], clave_reels)
                else:
                    adicionales = [Post.model_validate(p) for p in anteriores]
                por_id = {p.url or p.id: i for i, p in enumerate(posts)}
                for post in adicionales:
                    if not post.es_reel:
                        continue
                    identidad = post.url or post.id
                    if identidad in por_id:
                        # El actor de reels puede completar duración/audio ausentes
                        # en latestPosts sin perder el caption del perfil.
                        original = posts[por_id[identidad]]
                        datos = original.model_dump()
                        for campo, valor in post.model_dump().items():
                            if valor is not None and valor != '' and valor != []:
                                datos[campo] = valor
                        datos['patrocinado'] = original.patrocinado or post.patrocinado
                        datos['likes_ocultos'] = original.likes_ocultos or post.likes_ocultos
                        enriquecido = Post.model_validate(datos)
                        posts[por_id[identidad]] = enriquecido
                        posts_contexto = [enriquecido if (p.url or p.id) == identidad else p for p in posts_contexto]
                    else:
                        por_id[identidad] = len(posts)
                        posts.append(post)
                        posts_contexto.append(post)
            if not perfil.posts and posts:
                # A veces Apify devuelve el perfil sin latestPosts; los reels bastan para medir.
                resultado.metricas = calcular_metricas(posts, perfil.followers, self.metricas_agregacion)
                resultado.notas.append('Métricas calculadas con los reels: Apify no devolvió los posts del perfil')
            # Solo se transcriben los reels de publicidad, del más reciente al más antiguo: ahí se nombra
            # a la marca aunque el caption diga solo «#publi».
            publicidad = sorted((p for p in posts if es_publicidad(p)), key=lambda p: p.fecha or '', reverse=True)
            resultado.notas.append(f'{len(publicidad)} reels de publicidad entre {len(posts)} revisados; '
                                   f'se transcriben hasta {opciones.reels}')
            elegibles = []
            for post in publicidad:
                if post.duracion_segundos is None or post.duracion_segundos <= 0:
                    resultado.notas.append(f'Reel omitido: duración desconocida ({post.url or post.id})')
                elif post.duracion_segundos > 180:
                    resultado.notas.append(f'Reel omitido: supera 3 minutos ({post.url or post.id})')
                elif not post.audio_url:
                    resultado.notas.append(f'Reel omitido: sin URL de audio público ({post.url or post.id})')
                else:
                    elegibles.append(post)
            avanzar('reels', True)
            if elegibles:
                avanzar('transcripcion')
            for post in elegibles[:opciones.reels]:
                clave_audio = clave_cache(audio, {'url': post.url or post.id, 'modelo': getattr(audio, 'modelo', 'whisper-large-v3-turbo')})
                texto = self.almacen.obtener(usuario, 'transcripcion', clave_audio)
                if texto is None:
                    # La descarga es gratuita; se valida antes de reservar transcripción.
                    try:
                        contenido = audio.descargar_audio(post)
                    except Exception as exc:
                        if type(exc).__name__ == 'AudioDemasiadoGrande':
                            resultado.notas.append(f'Audio omitido: supera 25 MB ({post.url or post.id})')
                            continue
                        raise
                    if len(contenido) > 25_000_000:
                        resultado.notas.append(f'Audio omitido: supera 25 MB ({post.url or post.id})')
                        continue
                    minimo = self.precios.tarifa(getattr(audio, 'tarifa_minimo', 'groq_minimo_segundos'))
                    segundos = max(post.duracion_segundos, float(minimo))
                    try:
                        texto = self._llamada(registro, usuario, getattr(audio, 'paso_costo', 'transcripcion'), segundos,
                            lambda: self._transcribir(audio, contenido, post))
                    except AudioSinPista:
                        resultado.notas.append(f'Reel sin pista de audio; se omite ({post.url or post.id})')
                        continue
                    except LimiteProveedor as exc:
                        # Sin transcripción el perfil igual tiene métricas, audiencia y marcas de los posts.
                        resultado.notas.append(f'Transcripción omitida: {exc} El perfil sigue sin los reels restantes.')
                        break
                    self.almacen.guardar(usuario, 'transcripcion', texto, clave_audio)
                transcripciones[post.url or post.id] = texto
            if elegibles:
                avanzar('transcripcion', True)
        # La ficha conserva también los posts enriquecidos usados como evidencia.
        resultado.perfil.posts = posts_contexto
        if not posts_contexto:
            resultado.notas.append('Apify no devolvió publicaciones: sin métricas de interacción ni marcas')
        if opciones.muestra_seguidores:
            avanzar('seguidores')
        seguidores = self._relaciones(usuario, 'followers', opciones.muestra_seguidores, registro) if opciones.muestra_seguidores else []
        if opciones.muestra_seguidores:
            avanzar('seguidores', True)
        resultado.seguidores_muestra = len(seguidores)
        if opciones.muestra_seguidores:
            resultado.notas.append(f'Seguidores obtenidos: {len(seguidores)} de {opciones.muestra_seguidores} solicitados; muestra de conveniencia')
        datos_perfil = perfil.model_dump()
        datos_perfil['posts'] = [p.model_dump() for p in posts_contexto]
        contexto = {'perfil': datos_perfil, 'transcripciones': transcripciones,
                    'seguidores': [s.model_dump() for s in seguidores], 'brief': opciones.brief.model_dump()}
        avanzar('clasificacion')
        clave_llm = clave_cache(clasificador, contexto)
        anterior = self.almacen.obtener(usuario, 'clasificacion', clave_llm)
        if anterior is None:
            nombre = getattr(clasificador, 'nombre', 'jev')
            tokens = clasificador.estimar_tokens(contexto)
            paso = 'jev' if nombre == 'jev' else 'openrouter_entrada'
            reserva = registro.reservar(usuario, paso, tokens)
            reserva_salida = None
            if nombre == 'openrouter':
                try:
                    reserva_salida = registro.reservar(usuario, 'openrouter_salida', clasificador.max_tokens_salida)
                except PresupuestoAgotado:
                    registro.confirmar(reserva, paso, 0)  # Todavía no se envió ninguna llamada.
                    raise
            respuesta = clasificador.clasificar(contexto)
            registro.confirmar(reserva, paso, respuesta.tokens_entrada)
            if reserva_salida:
                registro.confirmar(reserva_salida, 'openrouter_salida', respuesta.tokens_salida)
            clasificacion = respuesta.datos
            audiencia_b, calidad = agregar_audiencia(clasificacion, seguidores)
            evidencias = {p.url or p.id for p in posts_contexto if p.url or p.id}
            if any(m.post_evidencia not in evidencias for m in clasificacion.marcas):
                raise ValueError('Marca con evidencia de un post desconocido')
            self.almacen.guardar(usuario, 'clasificacion', clasificacion.model_dump(), clave_llm)
        else:
            clasificacion = Clasificacion.model_validate(anterior)
            audiencia_b, calidad = agregar_audiencia(clasificacion, seguidores)
        resultado.clasificacion = clasificacion
        resultado.audiencia_b = audiencia_b
        resultado.calidad_audiencia = calidad
        desconocidos = sum(s.persona_real is None for s in clasificacion.seguidores)
        if desconocidos:
            resultado.notas.append(f'Personas reales sin determinar: {desconocidos}; no suman al porcentaje de calidad')
        avanzar('clasificacion', True)
