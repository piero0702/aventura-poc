"""Contratos síncronos; sustituibles sin cambiar los pasos de la tubería."""
from typing import Literal, Protocol

from motor.modelos import Perfil, Post, RespuestaClasificacion, Seguidor


class ProveedorError(RuntimeError):
    """Fallo sanitizado: el mensaje nunca contiene llaves, URLs ni cuerpos remotos."""


class AudioDemasiadoGrande(ProveedorError):
    """Se alcanzó el límite de 25 MB antes de transcribir."""


class AudioSinPista(ProveedorError):
    """El video no tiene pista de audio: se omite ese reel, no el perfil. No se factura."""


class LimiteProveedor(ProveedorError):
    """El proveedor rechazó la petición por su límite de uso (HTTP 429): no la procesó ni la factura."""


class Instagram(Protocol):
    def obtener_perfil(self, usuario: str) -> Perfil: ...
    def relaciones(self, usuario: str, modo: Literal['followers', 'following'], limite: int) -> list[Seguidor]: ...
    def obtener_reels(self, usuario: str, limite: int) -> list[Post]: ...


class Audio(Protocol):
    def descargar_audio(self, post: Post) -> bytes: ...
    def transcribir(self, audio: bytes, post: Post) -> str: ...


class Clasificador(Protocol):
    def preparar(self, contexto: dict) -> dict: ...
    def estimar_tokens(self, contexto: dict) -> int: ...
    def clasificar(self, contexto: dict) -> RespuestaClasificacion: ...


def unidades_relaciones(limite: int) -> int:
    """El esquema público del actor exige al menos 25 resultados solicitados."""
    return max(25, limite) if limite else 0
