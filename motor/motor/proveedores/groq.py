"""Descarga acotada y transcripción de audio público: Groq (servicio) o Whisper local (pruebas)."""
from __future__ import annotations

import io
import ipaddress
import re
import threading
import time
from collections import deque
from urllib.parse import urlparse

import httpx

from motor.modelos import Post
from motor.proveedores.base import AudioDemasiadoGrande, AudioSinPista, LimiteProveedor, ProveedorError

MAX_AUDIO_BYTES = 25_000_000
# Un 429 se reintenta si Groq pide esperar poco; si pide más (tope por hora o por día), se omite el audio.
ESPERA_MAXIMA_429_S = 60
INTENTOS_429 = 3


class GroqAudio:
    identidad = 'groq:whisper-large-v3-turbo'
    nombre = 'Groq'
    llave_env = 'GROQ_API_KEY'
    url = 'https://api.groq.com/openai/v1/audio/transcriptions'
    modelo = 'whisper-large-v3-turbo'
    # Paso de precios.yaml y mínimo facturable por audio.
    paso_costo = 'transcripcion'
    tarifa_minimo = 'groq_minimo_segundos'

    # Ventana compartida por todos los hilos y corridas del proceso: el límite de Groq es por organización.
    _enviadas: deque = deque()
    _candado = threading.Lock()

    def __init__(self, clave: str, cliente: httpx.Client | None = None, rpm: int = 20,
                 dormir=time.sleep, reloj=time.monotonic):
        if not clave:
            raise ProveedorError(f'Falta {self.llave_env} en .env.')
        self._clave = clave
        self._cliente = cliente or httpx.Client(timeout=90.0, follow_redirects=False)
        self._propio = cliente is None
        self.rpm = rpm
        self._dormir = dormir
        self._reloj = reloj

    def _turno(self):
        """Espera hasta que haya cupo en el último minuto (solicitudes por minuto de la cuenta)."""
        with self._candado:
            while True:
                ahora = self._reloj()
                while self._enviadas and ahora - self._enviadas[0] >= 60:
                    self._enviadas.popleft()
                if len(self._enviadas) < self.rpm:
                    self._enviadas.append(ahora)
                    return
                self._dormir(60 - (ahora - self._enviadas[0]) + 0.05)

    def descargar_audio(self, post: Post) -> bytes:
        enlace = urlparse(post.audio_url or '')
        if enlace.scheme != 'https' or not enlace.hostname or enlace.username or enlace.password:
            raise ProveedorError('El reel no tiene una URL de audio público HTTPS válida.')
        if enlace.hostname.lower() in {'localhost', 'localhost.localdomain'}:
            raise ProveedorError('La URL de audio no es pública.')
        try:
            if not ipaddress.ip_address(enlace.hostname).is_global:
                raise ProveedorError('La URL de audio no es pública.')
        except ValueError:
            pass
        try:
            with self._cliente.stream('GET', post.audio_url) as respuesta:
                respuesta.raise_for_status()
                longitud = respuesta.headers.get('Content-Length')
                if longitud and int(longitud) > MAX_AUDIO_BYTES:
                    raise AudioDemasiadoGrande('Audio omitido: supera 25 MB.')
                partes = []
                total = 0
                for parte in respuesta.iter_bytes(chunk_size=65536):
                    total += len(parte)
                    if total > MAX_AUDIO_BYTES:
                        raise AudioDemasiadoGrande('Audio omitido: supera 25 MB.')
                    partes.append(parte)
                return b''.join(partes)
        except (httpx.HTTPError, ValueError, TypeError):
            raise ProveedorError('No se pudo descargar el audio público del reel.') from None

    def transcribir(self, audio: bytes, post: Post) -> str:
        if len(audio) > MAX_AUDIO_BYTES:
            raise AudioDemasiadoGrande('Audio omitido: supera 25 MB.')
        if not audio:
            raise ProveedorError('El audio descargado está vacío.')
        if post.duracion_segundos is None or post.duracion_segundos <= 0 or post.duracion_segundos > 180:
            raise ProveedorError('Audio omitido: duración desconocida o superior a 3 minutos.')
        try:
            for intento in range(INTENTOS_429):
                self._turno()
                respuesta = self._cliente.post(
                    self.url,
                    headers={'Authorization': f'Bearer {self._clave}'},
                    data={'model': self.modelo, 'response_format': 'json'},
                    files={'file': ('audio.mp4', audio, 'audio/mp4')},
                )
                if respuesta.status_code != 429:
                    break
                # Groq no procesa ni cobra una petición rechazada por límite: reintentar no duplica cobros.
                try:
                    espera = float(respuesta.headers.get('retry-after', '10'))
                except ValueError:
                    espera = 10.0
                if espera > ESPERA_MAXIMA_429_S or intento == INTENTOS_429 - 1:
                    raise LimiteProveedor(f'{self.nombre} alcanzó su límite de uso (pidió esperar {espera:.0f} s).')
                self._dormir(espera)
            respuesta.raise_for_status()
            texto = respuesta.json().get('text')
            if not isinstance(texto, str):
                raise ValueError('Transcripción sin texto')
            return texto
        except httpx.HTTPStatusError as exc:
            # El motivo ({"error": {"message"}}) sirve para depurar; se borran la llave y las URLs.
            try:
                detalle = str(exc.response.json().get('error', {}).get('message', ''))[:200]
                detalle = re.sub(r'https?://\S+', '[url]', detalle.replace(self._clave, '[llave]'))
            except (ValueError, AttributeError):
                detalle = ''
            if exc.response.status_code == 400 and 'no audio track' in detalle.lower():
                raise AudioSinPista('Reel sin pista de audio.') from None
            raise ProveedorError(f'Falló la transcripción de {self.nombre} (HTTP {exc.response.status_code}'
                                 f'{": " + detalle if detalle else ""}); revisar antes de reintentar.') from None
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise ProveedorError(f'Falló la transcripción de {self.nombre}; revisar antes de reintentar.') from None

    def close(self):
        if self._propio:
            self._cliente.close()


def _decodificar_16k(audio: bytes):
    """Audio a float32 mono de 16 kHz, lo que espera Whisper.

    Se decodifica aquí porque faster-whisper 1.2 llama a av.open con un argumento
    (metadata_errors) que PyAV 19 ya no acepta.
    """
    import av
    import numpy as np
    muestras = []
    with av.open(io.BytesIO(audio), mode='r') as contenedor:
        remuestreo = av.AudioResampler(format='s16', layout='mono', rate=16000)
        for cuadro in contenedor.decode(audio=0):
            for salida in remuestreo.resample(cuadro):
                muestras.append(salida.to_ndarray().reshape(-1))
        for salida in remuestreo.resample(None):
            muestras.append(salida.to_ndarray().reshape(-1))
    if not muestras:
        raise ProveedorError('El audio no trae pista de sonido.')
    return np.concatenate(muestras).astype(np.float32) / 32768.0


class WhisperLocalAudio(GroqAudio):
    """Whisper de código abierto en esta máquina (faster-whisper), solo para pruebas.

    El servicio final usa Groq. Requiere el extra: `uv sync --extra whisper-local`.
    """
    nombre = 'Whisper local'
    llave_env = ''
    paso_costo = 'transcripcion_local'
    tarifa_minimo = 'whisper_local_minimo_segundos'

    def __init__(self, modelo: str = 'large-v3-turbo', cliente: httpx.Client | None = None):
        self.modelo = modelo
        self.identidad = f'local:whisper-{modelo}'
        self._cliente = cliente or httpx.Client(timeout=90.0, follow_redirects=False)
        self._propio = cliente is None
        self._whisper = None

    def transcribir(self, audio: bytes, post: Post) -> str:
        if len(audio) > MAX_AUDIO_BYTES:
            raise AudioDemasiadoGrande('Audio omitido: supera 25 MB.')
        if not audio:
            raise ProveedorError('El audio descargado está vacío.')
        if post.duracion_segundos is None or post.duracion_segundos <= 0 or post.duracion_segundos > 180:
            raise ProveedorError('Audio omitido: duración desconocida o superior a 3 minutos.')
        if self._whisper is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise ProveedorError('Falta faster-whisper: correr `uv sync --extra whisper-local`.') from None
            # La primera vez descarga el modelo (~1.6 GB para large-v3-turbo).
            self._whisper = WhisperModel(self.modelo, device='cpu', compute_type='int8')
        try:
            segmentos, _ = self._whisper.transcribe(_decodificar_16k(audio), vad_filter=True)
            return ' '.join(s.text.strip() for s in segmentos).strip()
        except Exception:
            raise ProveedorError('Falló la transcripción con Whisper local; revisar el audio.') from None


class AudioDesactivado:
    """Sin transcripción: para probar Apify + Jev solos. Usar con --reels 0."""
    identidad = 'ninguno'

    def descargar_audio(self, post: Post) -> bytes:
        raise ProveedorError('Transcripción desactivada (TRANSCRIPCION_PROVEEDOR=ninguno); correr con --reels 0.')

    def transcribir(self, audio: bytes, post: Post) -> str:
        raise ProveedorError('Transcripción desactivada (TRANSCRIPCION_PROVEEDOR=ninguno); correr con --reels 0.')

    def close(self):
        pass
