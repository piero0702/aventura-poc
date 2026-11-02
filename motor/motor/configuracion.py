"""Configuración local: las credenciales se leen únicamente del archivo .env."""
from pathlib import Path
from dataclasses import dataclass, field
import math
from dotenv import dotenv_values
import yaml
from motor.modelos import Brief

RAIZ = Path(__file__).resolve().parent.parent


def ruta_local(valor: str | Path) -> Path:
    ruta = Path(valor)
    if not ruta.is_absolute():
        ruta = RAIZ / ruta
    ruta = ruta.resolve()
    if not ruta.is_relative_to(RAIZ):
        raise ValueError('La ruta debe estar dentro de la carpeta del motor')
    return ruta


@dataclass(repr=False)
class Configuracion:
    secretos: dict[str, str] = field(default_factory=dict, repr=False)
    actor_relaciones: str = 'scraping_solutions/instagram-scraper-followers-following-no-cookies'
    actor_perfiles: str = 'apify/instagram-profile-scraper'
    actor_reels: str = 'apify/instagram-reel-scraper'
    proveedor_llm: str = 'jev'
    modelo_jev: str = 'jev-latest'
    modelo_openrouter: str = ''
    proveedor_transcripcion: str = 'groq'
    modelo_whisper_local: str = 'large-v3-turbo'
    metricas_agregacion: str = 'promedio'
    simulado_retraso_s: float = 0
    paralelo: int = 4
    groq_rpm: int = 20

    def __post_init__(self):
        if self.metricas_agregacion not in {'promedio', 'mediana'}:
            raise ValueError('METRICAS_AGREGACION debe ser promedio o mediana')
        if not math.isfinite(self.simulado_retraso_s) or self.simulado_retraso_s < 0:
            raise ValueError('MOTOR_SIMULADO_RETRASO_S debe ser un número finito mayor o igual a cero')
        if not 1 <= self.paralelo <= 10:
            raise ValueError('MOTOR_PARALELO debe estar entre 1 y 10')
        if not 1 <= self.groq_rpm <= 10000:
            raise ValueError('GROQ_RPM debe estar entre 1 y 10000')

    def __repr__(self):
        return 'Configuracion(credenciales_ocultas=True)'

    @classmethod
    def cargar(cls, archivo: str | Path = '.env') -> 'Configuracion':
        valores = {k: v for k, v in dotenv_values(ruta_local(archivo), interpolate=False).items() if v}
        return cls(secretos={k: valores.get(k, '') for k in (
            'APIFY_TOKEN', 'GROQ_API_KEY', 'TYPESAFE_API_KEY', 'OPENROUTER_API_KEY', 'MOTOR_HTTP_TOKEN')},
            actor_relaciones=valores.get('APIFY_ACTOR_RELACIONES', cls.actor_relaciones),
            actor_perfiles=valores.get('APIFY_ACTOR_PERFILES', cls.actor_perfiles),
            actor_reels=valores.get('APIFY_ACTOR_REELS', cls.actor_reels),
            proveedor_llm=valores.get('LLM_PROVEEDOR', 'jev'),
            modelo_jev=valores.get('TYPESAFE_MODELO', 'jev-latest'),
            modelo_openrouter=valores.get('OPENROUTER_MODELO', ''),
            proveedor_transcripcion=valores.get('TRANSCRIPCION_PROVEEDOR', 'groq'),
            modelo_whisper_local=valores.get('WHISPER_LOCAL_MODELO', 'large-v3-turbo'),
            metricas_agregacion=valores.get('METRICAS_AGREGACION', 'promedio'),
            simulado_retraso_s=float(valores.get('MOTOR_SIMULADO_RETRASO_S', '0')),
            paralelo=int(valores.get('MOTOR_PARALELO', '4')),
            groq_rpm=int(valores.get('GROQ_RPM', '20')))

    def llave(self, nombre: str) -> str:
        valor = self.secretos.get(nombre, '')
        if not valor:
            raise ValueError(f'Falta configurar {nombre} en .env')
        return valor


def leer_brief(archivo: str | Path | None) -> Brief:
    if archivo is None:
        return Brief()
    with ruta_local(archivo).open(encoding='utf-8') as entrada:
        brief = Brief.model_validate(yaml.safe_load(entrada) or {})
    if brief.followers_max is not None and brief.followers_max < brief.followers_min:
        raise ValueError('followers_max debe ser mayor o igual a followers_min')
    return brief


# Paso de costo de cada proveedor de transcripción (None: no se transcribe).
PASOS_TRANSCRIPCION = {'groq': 'transcripcion', 'local': 'transcripcion_local', 'ninguno': None}
