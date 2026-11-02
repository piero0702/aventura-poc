"""Adaptador de los actores públicos sin sesión; contratos en docs/APIS.md."""
from __future__ import annotations

import re
import threading
from typing import Literal

import httpx

from motor.modelos import Perfil, Post, Seguidor, normalizar_usuario
from motor.proveedores.base import ProveedorError, unidades_relaciones

ACTOR_RELACIONES = 'scraping_solutions/instagram-scraper-followers-following-no-cookies'
ACTOR_PERFILES = 'apify/instagram-profile-scraper'
ACTOR_REELS = 'apify/instagram-reel-scraper'
ACTORES_PERFILES_SIN_SESION = {ACTOR_PERFILES, 'figue/instagram-profile-scraper'}


def _primero(dato: dict, *claves: str, defecto=None):
    return next((dato[c] for c in claves if dato.get(c) is not None), defecto)


def _entero(valor) -> int | None:
    if valor is None:
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None


def _usuarios(valor) -> list[str]:
    if not isinstance(valor, list):
        return []
    salida = []
    for item in valor:
        candidato = item.get('username', '') if isinstance(item, dict) else str(item)
        try:
            salida.append(normalizar_usuario(candidato))
        except ValueError:
            continue
    return list(dict.fromkeys(salida))


def normalizar_post(dato: dict, forzar_reel: bool = False) -> Post:
    """Normaliza ambos actores; likes negativos u ocultos nunca son cero."""
    url = str(dato.get('url') or '')
    tipo = str(dato.get('type') or '')
    producto = str(_primero(dato, 'productType', 'product_type', defecto='')).lower()
    es_reel = forzar_reel or producto == 'clips' or '/reel/' in url or tipo.lower() in {'reel', 'reels', 'clips'}
    likes = _entero(_primero(dato, 'likesCount', 'like_count', 'likeCount'))
    ocultos = bool(_primero(dato, 'likesHidden', 'likes_hidden', 'like_and_view_counts_disabled',
                            'hide_like_and_view_counts', defecto=False)) or (likes is not None and likes < 0)
    comentarios = _entero(_primero(dato, 'commentsCount', 'comment_count', 'commentCount'))
    vistas = _entero(_primero(dato, 'videoViewCount', 'video_view_count', 'videoPlayCount', 'playCount'))
    duracion = _primero(dato, 'videoDuration', 'video_duration', 'durationSeconds')
    try:
        duracion = max(0.0, float(duracion)) if duracion is not None else None
    except (ValueError, TypeError):
        duracion = None
    menciones = _usuarios(dato.get('mentions', []))
    menciones += re.findall(r'@([a-zA-Z0-9._]{1,30})', str(dato.get('caption') or ''))
    menciones += _usuarios(dato.get('sponsors', []))
    menciones += _usuarios(dato.get('taggedUsers', dato.get('tagged_users', [])))
    return Post(
        id=str(_primero(dato, 'id', 'shortCode', 'shortcode', defecto='')),
        url=url, tipo='reel' if es_reel else ('video_otra' if tipo.lower() == 'video' else 'imagen'),
        fijado=bool(_primero(dato, 'isPinned', 'is_pinned', 'pinned', defecto=False)),
        fecha=str(_primero(dato, 'timestamp', 'taken_at', defecto='')),
        likes=None if ocultos else likes,
        comentarios=comentarios if comentarios is None or comentarios >= 0 else None,
        vistas=vistas if vistas is None or vistas >= 0 else None,
        likes_ocultos=ocultos, caption=str(dato.get('caption') or ''),
        menciones=list(dict.fromkeys(m.lower() for m in menciones)),
        coautores=_usuarios(_primero(dato, 'coauthorProducers', 'coauthor_producers', 'coauthors', defecto=[])),
        patrocinado=bool(_primero(dato, 'paidPartnership', 'isPaidPartnership', defecto=False)),
        patrocinadores=_usuarios(dato.get('sponsors', [])),
        duracion_segundos=duracion,
        audio_url=_primero(dato, 'audioUrl', 'audio_url', 'videoUrl', 'video_url'),
    )


def normalizar_perfil(dato: dict, usuario: str) -> Perfil:
    error = str(_primero(dato, 'error', 'errorCode', defecto='')).lower()
    if error in {'not_found', 'notfound', 'user_not_found', 'empty_profile'}:
        return Perfil(usuario=usuario, existe=False)
    if error == 'private':
        return Perfil(usuario=usuario, privada=True)
    if error:
        raise ProveedorError('Apify no pudo obtener el perfil; revisar la corrida antes de reintentar.')
    return Perfil(
        usuario=dato.get('username') or usuario,
        nombre=str(_primero(dato, 'fullName', 'full_name', defecto='')),
        bio=str(dato.get('biography') or ''),
        categoria=str(_primero(dato, 'businessCategoryName', 'category_name', 'categoryName', defecto='')),
        followers=max(0, _entero(_primero(dato, 'followersCount', 'follower_count', defecto=0)) or 0),
        privada=bool(_primero(dato, 'private', 'is_private', 'isPrivate', defecto=False)),
        verificada=bool(_primero(dato, 'verified', 'is_verified', 'isVerified', defecto=False)),
        posts=[normalizar_post(p) for p in (dato.get('latestPosts') or [])[:12]],
    )


class ApifyInstagram:
    def __init__(self, token: str, actor_perfiles: str = ACTOR_PERFILES,
                 cliente: httpx.Client | None = None, max_costo_usd_por_llamada: float | None = None,
                 actor_relaciones: str = ACTOR_RELACIONES, actor_reels: str = ACTOR_REELS):
        if not token:
            raise ProveedorError('Falta APIFY_TOKEN en .env.')
        if actor_perfiles not in ACTORES_PERFILES_SIN_SESION:
            raise ProveedorError('Actor de perfiles no verificado sin sesión; usa apify o figue.')
        if actor_relaciones != ACTOR_RELACIONES or actor_reels != ACTOR_REELS:
            raise ProveedorError('Actor de relaciones o reels no verificado sin sesión.')
        self.actor_relaciones = actor_relaciones
        self.actor_reels = actor_reels
        self._token = token
        self.actor_perfiles = actor_perfiles
        self._cliente = cliente or httpx.Client(timeout=310.0, follow_redirects=False)
        self._propio = cliente is None
        # El tope y las unidades son por hilo: varios perfiles se procesan en paralelo
        # y cada llamada debe llevar su propio maxTotalChargeUsd.
        self._local = threading.local()
        self._tope_inicial = max_costo_usd_por_llamada

    @property
    def identidad(self) -> str:
        return f'apify:{self.actor_perfiles}:{self.actor_relaciones}:{self.actor_reels}'

    @property
    def max_costo_usd_por_llamada(self) -> float | None:
        return getattr(self._local, 'tope', self._tope_inicial)

    @property
    def ultimas_unidades(self) -> int:
        return getattr(self._local, 'unidades', 0)

    @ultimas_unidades.setter
    def ultimas_unidades(self, valor: int):
        self._local.unidades = valor

    def set_limite_costo(self, costo_usd: float):
        self._local.tope = costo_usd

    def _ejecutar(self, actor: str, entrada: dict, max_items: int) -> list[dict]:
        parametros = {'format': 'json', 'clean': 'true', 'maxItems': max_items, 'restartOnError': 'false'}
        if self.max_costo_usd_por_llamada is not None:
            parametros['maxTotalChargeUsd'] = self.max_costo_usd_por_llamada
        try:
            respuesta = self._cliente.post(
                f'https://api.apify.com/v2/acts/{actor.replace("/", "~")}/run-sync-get-dataset-items',
                headers={'Authorization': f'Bearer {self._token}'}, params=parametros, json=entrada,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
            if not isinstance(datos, list) or not all(isinstance(d, dict) for d in datos):
                raise ValueError('Formato inesperado')
            self.ultimas_unidades = len(datos)
            return datos
        except httpx.HTTPStatusError as exc:
            # El motivo de Apify ({"error": {"type", "message"}}) ayuda a depurar, pero un cuerpo remoto
            # podría repetir el token o URLs: se borran antes de guardarlo en las notas.
            try:
                error = exc.response.json().get('error', {})
                detalle = f"{error.get('type', '')}: {str(error.get('message', ''))[:200]}"
                detalle = re.sub(r'https?://\S+', '[url]', detalle.replace(self._token, '[token]'))
            except (ValueError, AttributeError):
                detalle = ''
            raise ProveedorError(f'Falló Apify ({actor}, HTTP {exc.response.status_code} {detalle}); revisar la corrida '
                                 'remota antes de reintentar para evitar un doble cobro.') from None
        except (httpx.HTTPError, ValueError, TypeError):
            raise ProveedorError('Falló Apify; revisar la corrida remota antes de reintentar para evitar un doble cobro.') from None

    def obtener_perfil(self, usuario: str) -> Perfil:
        usuario = normalizar_usuario(usuario)
        entrada = ({'profiles': [usuario], 'includeRecentPosts': True}
                   if self.actor_perfiles.startswith('figue/') else {'usernames': [usuario]})
        datos = self._ejecutar(self.actor_perfiles, entrada, 1)
        if not datos:
            return Perfil(usuario=usuario, existe=False)
        try:
            return normalizar_perfil(datos[0], usuario)
        except (ValueError, TypeError, KeyError):
            raise ProveedorError('La respuesta de perfil de Apify no cumple el esquema esperado.') from None

    def obtener_perfiles(self, usuarios: list[str]) -> dict[str, Perfil]:
        """Una sola corrida para varios perfiles; los que no vuelven se piden después uno por uno."""
        usuarios = [normalizar_usuario(u) for u in usuarios]
        if not usuarios:
            return {}
        entrada = ({'profiles': usuarios, 'includeRecentPosts': True}
                   if self.actor_perfiles.startswith('figue/') else {'usernames': usuarios})
        datos = self._ejecutar(self.actor_perfiles, entrada, len(usuarios))
        pedidos, salida = set(usuarios), {}
        for dato in datos:
            usuario = str(_primero(dato, 'username', 'inputUsername', defecto='')).lower().lstrip('@')
            if usuario not in pedidos or usuario in salida:
                continue
            try:
                salida[usuario] = normalizar_perfil(dato, usuario)
            except (ProveedorError, ValueError, TypeError, KeyError):
                continue
        return salida

    def obtener_reels_lote(self, usuarios: list[str], limite: int) -> dict[str, list[Post]]:
        """Una sola corrida de reels para varios perfiles, agrupados por su dueño."""
        usuarios = [normalizar_usuario(u) for u in usuarios]
        if limite <= 0 or not usuarios:
            return {}
        datos = self._ejecutar(self.actor_reels, {
            'username': usuarios, 'resultsLimit': limite,
            'includeTranscript': False, 'includeDownloadedVideo': False,
        }, limite * len(usuarios))
        salida = {usuario: [] for usuario in usuarios}
        for dato in datos:
            dueno = str(_primero(dato, 'ownerUsername', 'owner_username', defecto='')).lower()
            if dueno in salida and len(salida[dueno]) < limite:
                try:
                    salida[dueno].append(normalizar_post(dato, forzar_reel=True))
                except (ValueError, TypeError, KeyError):
                    raise ProveedorError('La respuesta de reels de Apify no cumple el esquema esperado.') from None
        return salida

    def relaciones(self, usuario: str, modo: Literal['followers', 'following'], limite: int) -> list[Seguidor]:
        usuario = normalizar_usuario(usuario)
        if modo not in {'followers', 'following'} or limite < 0 or limite > 500000:
            raise ValueError('Modo o límite de relaciones inválido.')
        if not limite:
            return []
        unidades = unidades_relaciones(limite)
        datos = self._ejecutar(self.actor_relaciones, {
            'Account': [usuario], 'resultsLimit': unidades,
            'dataToScrape': 'Followers' if modo == 'followers' else 'Followings',
        }, unidades)
        salida = {}
        for dato in datos:
            try:
                seguidor = Seguidor(
                    usuario=dato['username'], nombre=str(dato.get('full_name') or ''),
                    bio=str(dato.get('biography') or ''), privada=bool(dato.get('is_private', False)),
                    verificada=bool(dato.get('is_verified', False)),
                )
                salida.setdefault(seguidor.usuario, seguidor)
            except (ValueError, KeyError):
                raise ProveedorError('La respuesta de relaciones de Apify no cumple el esquema esperado.') from None
        return list(salida.values())[:limite]

    def obtener_reels(self, usuario: str, limite: int) -> list[Post]:
        if limite <= 0:
            return []
        datos = self._ejecutar(self.actor_reels, {
            'username': [normalizar_usuario(usuario)], 'resultsLimit': limite,
            'includeTranscript': False, 'includeDownloadedVideo': False,
        }, limite)
        try:
            return [normalizar_post(d, forzar_reel=True) for d in datos][:limite]
        except (ValueError, TypeError, KeyError):
            raise ProveedorError('La respuesta de reels de Apify no cumple el esquema esperado.') from None

    def close(self):
        if self._propio:
            self._cliente.close()
