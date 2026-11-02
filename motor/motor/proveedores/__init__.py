"""Proveedores de Instagram, audio y clasificación, reales y sintéticos."""
from dataclasses import dataclass

from motor.proveedores.base import Audio, AudioDemasiadoGrande, Clasificador, Instagram, ProveedorError, unidades_relaciones


@dataclass
class Proveedores:
    instagram: Instagram
    audio: Audio
    clasificador: Clasificador

    def close(self):
        for proveedor in (self.instagram, self.audio, self.clasificador):
            cerrar = getattr(proveedor, 'close', None)
            if cerrar:
                cerrar()

    cerrar = close


__all__ = ['Proveedores', 'ProveedorError', 'AudioDemasiadoGrande', 'unidades_relaciones']
