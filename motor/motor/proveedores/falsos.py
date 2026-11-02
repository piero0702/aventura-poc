"""Proveedores deterministas con fixtures sintéticos: nunca abren la red."""
from __future__ import annotations

import json
from pathlib import Path

from motor.modelos import Clasificacion, Perfil, Post, RespuestaClasificacion, Seguidor
from motor.proveedores.base import AudioDemasiadoGrande
from motor.proveedores.groq import MAX_AUDIO_BYTES

RUTA_DEMO = Path(__file__).resolve().parents[2] / 'fixtures' / 'proveedores' / 'demo.json'


def _demo(ruta: str | Path | None = None) -> dict:
    return json.loads(Path(ruta or RUTA_DEMO).read_text(encoding='utf-8'))


class InstagramFalso:
    identidad = 'instagram:falso:v1'

    def __init__(self, perfiles: dict | None = None, seguidores: dict | None = None,
                 seguidos: dict | None = None, reels: dict | None = None,
                 ruta_fixtures: str | Path | None = None):
        demo = _demo(ruta_fixtures) if any(x is None for x in (perfiles, seguidores, seguidos, reels)) else {}
        self.perfiles = perfiles if perfiles is not None else demo.get('perfiles', {})
        self.seguidores = seguidores if seguidores is not None else demo.get('seguidores', {})
        self.seguidos = seguidos if seguidos is not None else demo.get('seguidos', {})
        self.reels = reels if reels is not None else demo.get('reels', {})
        self.llamadas = []
        self.contadores = {'perfil': 0, 'followers': 0, 'following': 0, 'reels': 0}
        self.ultimas_unidades = 0

    def obtener_perfil(self, usuario: str) -> Perfil:
        self.llamadas.append(('perfil', usuario))
        self.contadores['perfil'] += 1
        self.ultimas_unidades = 1
        dato = self.perfiles.get(usuario, {'usuario': usuario, 'existe': False})
        return Perfil.model_validate(dato).model_copy(deep=True)

    def relaciones(self, usuario: str, modo: str, limite: int) -> list[Seguidor]:
        self.llamadas.append((modo, usuario, limite))
        self.contadores[modo] += 1
        datos = (self.seguidores if modo == 'followers' else self.seguidos).get(usuario, [])
        self.ultimas_unidades = min(len(datos), max(25, limite))
        return [Seguidor.model_validate(s).model_copy(deep=True) for s in datos[:limite]]

    def obtener_reels(self, usuario: str, limite: int) -> list[Post]:
        self.llamadas.append(('reels', usuario, limite))
        self.contadores['reels'] += 1
        datos = self.reels.get(usuario, [])[:limite]
        self.ultimas_unidades = len(datos)
        return [Post.model_validate(p).model_copy(deep=True) for p in datos]

    def close(self):
        pass


class AudioFalso:
    identidad = 'audio:falso:v1'

    def __init__(self, transcripciones: dict[str, str] | None = None, tamanos: dict[str, int] | None = None):
        self.textos = transcripciones or {}
        self.tamanos = tamanos or {}
        self.llamadas = []
        self.descargas = 0
        self.transcripciones = 0

    def descargar_audio(self, post: Post) -> bytes:
        self.llamadas.append(('descargar', post.url))
        self.descargas += 1
        tamano = self.tamanos.get(post.url, 16)
        if tamano > MAX_AUDIO_BYTES:
            raise AudioDemasiadoGrande('Audio omitido: supera 25 MB.')
        return b'a' * tamano

    def transcribir(self, audio: bytes, post: Post) -> str:
        self.llamadas.append(('transcribir', post.url))
        self.transcripciones += 1
        return self.textos.get(post.url, 'Transcripción de prueba sintética: hábitos, cocina y vida cotidiana en Lima.')

    def close(self):
        pass


class ClasificadorFalso:
    nombre = 'jev'
    identidad = 'clasificador:falso:v1'
    max_tokens_salida = 0

    def __init__(self, respuestas: dict | None = None):
        self.respuestas = respuestas if respuestas is not None else _demo().get('clasificaciones', {})
        self.llamadas = []
        self.contador = 0

    def preparar(self, contexto: dict) -> dict:
        return contexto

    def estimar_tokens(self, contexto: dict) -> int:
        return len(json.dumps(self.preparar(contexto), ensure_ascii=False).encode('utf-8')) + 4096

    def clasificar(self, contexto: dict) -> RespuestaClasificacion:
        usuario = contexto['perfil']['usuario']
        self.llamadas.append(contexto)
        self.contador += 1
        dato = self.respuestas.get(usuario, {'categoria': 'Otros'})
        clasificacion = Clasificacion.model_validate(dato).model_copy(deep=True)
        # Todo seguidor solicitado conserva su usuario; los no grabados quedan desconocidos.
        por_usuario = {s.usuario: s for s in clasificacion.seguidores}
        from motor.modelos import AudienciaSeguidor
        clasificacion.seguidores = [por_usuario.get(s['usuario'], AudienciaSeguidor(usuario=s['usuario']))
                                    for s in contexto.get('seguidores', [])]
        if not any(contexto.get('brief', {}).get(c) for c in ('marca', 'publico_objetivo', 'marcas_a_evitar')):
            clasificacion.encaje = None
            clasificacion.motivo_encaje = 'Sin brief; encaje no evaluado.'
        return RespuestaClasificacion(datos=clasificacion, tokens_entrada=200, tokens_salida=0)

    def close(self):
        pass
