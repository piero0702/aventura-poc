"""Tarifas por unidad y reservas previas para detenerse antes del presupuesto."""
from decimal import Decimal
import threading
from pathlib import Path
import yaml
from motor.almacen import Almacen
from motor.configuracion import ruta_local
from motor.publicidad import reels_a_revisar


class PresupuestoAgotado(Exception):
    """La siguiente operación excedería el saldo disponible."""


class LimiteProveedorExcedido(PresupuestoAgotado):
    """El proveedor informó un uso superior al máximo enviado."""


class Precios:
    def __init__(self, archivo: str | Path = 'precios.yaml'):
        self.valores = yaml.safe_load(ruta_local(archivo).read_text(encoding='utf-8'))
        for valor in self.valores.values():
            if valor is not None and (not Decimal(str(valor)).is_finite() or Decimal(str(valor)) < 0):
                raise ValueError('Las tarifas deben ser finitas y no negativas')

    def tarifa(self, nombre: str) -> Decimal:
        valor = self.valores.get(nombre)
        if valor is None:
            raise ValueError(f'Completa la tarifa {nombre} en precios.yaml')
        return Decimal(str(valor))

    def costo(self, paso: str, unidades: float) -> Decimal:
        tarifas = {'perfil': ('apify_perfiles_por_1000', 1000),
                   'reels': ('apify_reels_por_1000', 1000),
                   'followers': ('apify_seguidores_por_1000', 1000),
                   'following': ('apify_seguidores_por_1000', 1000),
                   'transcripcion': ('groq_por_hora', 3600),
                   'transcripcion_local': ('whisper_local_por_hora', 3600),
                   'jev': ('jev_entrada_por_millon', 1000000),
                   'openrouter_entrada': ('openrouter_entrada_por_millon', 1000000),
                   'openrouter_salida': ('openrouter_salida_por_millon', 1000000)}
        tarifa, divisor = tarifas[paso]
        costo = Decimal(str(unidades)) * self.tarifa(tarifa) / divisor
        if paso == 'reels' and unidades > 0:
            # Cada corrida del actor de reels cobra al menos este mínimo.
            costo = max(costo, self.tarifa('apify_reels_minimo_por_corrida'))
        return costo


class RegistroCostos:
    def __init__(self, almacen: Almacen, precios: Precios, corrida_id: str, presupuesto: float | None):
        self.almacen, self.precios, self.corrida_id = almacen, precios, corrida_id
        self.presupuesto = Decimal(str(presupuesto)) if presupuesto is not None else None
        self.total = Decimal('0')
        # Los perfiles se procesan en paralelo: reservar y confirmar no pueden intercalarse.
        self._bloqueo = threading.Lock()

    def reservar(self, usuario: str, paso: str, unidades: float) -> tuple[str, Decimal]:
        costo = self.precios.costo(paso, unidades)
        with self._bloqueo:
            if self.presupuesto is not None and self.total + costo > self.presupuesto:
                raise PresupuestoAgotado('Presupuesto insuficiente para la siguiente llamada')
            identificador = self.almacen.registrar(self.corrida_id, usuario, paso, unidades, float(costo))
            self.total += costo
        return identificador, costo

    def confirmar(self, reserva: tuple[str, Decimal], paso: str, unidades: float):
        identificador, maximo = reserva
        real = self.precios.costo(paso, unidades)
        with self._bloqueo:
            self.total += real - maximo
            if real > maximo:
                self.almacen.ajustar(identificador, unidades, float(real), 'uso_inconsistente')
                raise LimiteProveedorExcedido('Unidades reales superiores al máximo reservado; corrida detenida')
            self.almacen.ajustar(identificador, unidades, float(real))


def estimar_costo(cantidad: int, opciones, precios: Precios | None = None, referencia=False,
                  proveedor_llm='jev', tokens_por_perfil=30000, max_tokens_salida=4096,
                  paso_transcripcion: str | None = 'transcripcion') -> dict:
    """Escenario conservador: todos aptos, reels adicionales y 3 min por audio.

    No consulta proveedores ni caché. Tokens es un supuesto explícito para la estimación,
    no un límite de gasto: en ejecución se reserva según la petición concreta.
    """
    if proveedor_llm not in {'jev', 'openrouter'}:
        raise ValueError('Proveedor LLM inválido')
    precios = precios or Precios()
    unidades = {'perfil': cantidad, 'reels': cantidad * reels_a_revisar(opciones),
                'followers': cantidad * max(25, opciones.muestra_seguidores) if opciones.muestra_seguidores else 0}
    if paso_transcripcion:
        unidades[paso_transcripcion] = cantidad * opciones.reels * 180
    if referencia:
        unidades['following'] = max(25, cantidad)
    if proveedor_llm == 'jev':
        unidades['jev'] = cantidad * tokens_por_perfil
    else:
        unidades['openrouter_entrada'] = cantidad * tokens_por_perfil
        unidades['openrouter_salida'] = cantidad * max_tokens_salida
    costos = {paso: float(precios.costo(paso, valor)) for paso, valor in unidades.items()}
    total = sum(costos.values())
    return {'perfiles': cantidad, 'costo_estimado_usd': total,
            'costo_por_perfil_usd': total / cantidad if cantidad else 0,
            'costos_por_paso': costos, 'supuestos': ['Sin usar caché; todos los perfiles aptos',
            '3 minutos por reel; se presupuestan todos los reels adicionales',
            f'{tokens_por_perfil} tokens de entrada por perfil para estimación',
            'Relaciones: solicitud mínima de 25 resultados; tarifas de precios.yaml']}
