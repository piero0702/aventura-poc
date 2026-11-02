"""Contratos compartidos entre la tubería y sus proveedores."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalizar_usuario(valor: str) -> str:
    """Unifica usuarios; rechaza enlaces, rutas y nombres ajenos a Instagram."""
    import re
    usuario = str(valor).strip().lstrip('@').lower()
    if not re.fullmatch(r'[a-z0-9._]{1,30}', usuario):
        raise ValueError('Usuario de Instagram inválido')
    return usuario


class Modelo(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Post(Modelo):
    id: str = ''
    url: str = ''
    tipo: str = 'imagen'
    fijado: bool = False
    fecha: str = ''
    likes: int | None = None
    comentarios: int | None = None
    vistas: int | None = None
    likes_ocultos: bool = False
    caption: str = ''
    menciones: list[str] = Field(default_factory=list)
    coautores: list[str] = Field(default_factory=list)
    patrocinado: bool = False
    patrocinadores: list[str] = Field(default_factory=list)
    duracion_segundos: float | None = Field(default=None, ge=0)
    audio_url: str | None = None

    @property
    def es_reel(self) -> bool:
        return self.tipo.lower() in {'reel', 'reels', 'video', 'clips'}


class Perfil(Modelo):
    usuario: str
    nombre: str = ''
    bio: str = ''
    categoria: str = ''
    followers: int = Field(default=0, ge=0)
    privada: bool = False
    verificada: bool = False
    existe: bool = True
    posts: list[Post] = Field(default_factory=list)
    _usuario = field_validator('usuario')(normalizar_usuario)


class Seguidor(Modelo):
    usuario: str
    nombre: str = ''
    bio: str = ''
    privada: bool = False
    verificada: bool = False
    _usuario = field_validator('usuario')(normalizar_usuario)


class Brief(Modelo):
    marca: str = ''
    publico_objetivo: str = ''
    marcas_a_evitar: list[str] = Field(default_factory=list)
    followers_min: int = Field(default=0, ge=0)
    followers_max: int | None = Field(default=None, ge=0)

    @model_validator(mode='after')
    def validar_rango(self):
        if self.followers_max is not None and self.followers_max < self.followers_min:
            raise ValueError('followers_max debe ser mayor o igual a followers_min')
        return self


RangoEdad = Literal['13-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']


class Audiencia(Modelo):
    edad: RangoEdad | None = None
    genero: Literal['Female', 'Male', 'Unknown'] | None = None
    ciudad: str | None = None


class AudienciaSeguidor(Modelo):
    usuario: str
    edad: RangoEdad | None = None
    genero: Literal['Female', 'Male', 'Unknown'] | None = None
    persona_real: bool | None = None
    _usuario = field_validator('usuario')(normalizar_usuario)


class Marca(Modelo):
    nombre: str
    tipo: Literal['publicidad', 'colab', 'canje', 'etiqueta', 'amigo_fotografo']
    post_evidencia: str
    tamano: Literal['grande', 'mediana', 'pequena'] | None = None


class Clasificacion(Modelo):
    categoria: str = ''
    descripcion: str = ''
    marcas: list[Marca] = Field(default_factory=list)
    audiencia_a: Audiencia = Field(default_factory=Audiencia)
    seguidores: list[AudienciaSeguidor] = Field(default_factory=list)
    encaje: int | None = Field(default=None, ge=1, le=5)
    motivo_encaje: str = ''
    # Probabilidad que Jev da a cada opción de la audiencia por contenido (edad, genero, ciudad, segmento).
    probabilidades: dict[str, dict[str, float]] = Field(default_factory=dict)


class RespuestaClasificacion(Modelo):
    datos: Clasificacion
    tokens_entrada: int = Field(default=0, ge=0)
    tokens_salida: int = Field(default=0, ge=0)


class Metricas(Modelo):
    likes: float | None = None
    comentarios: float | None = None
    reel_plays: float | None = None
    engagements: float | None = None
    er: float | None = None


class Opciones(Modelo):
    limite: int | None = Field(default=None, ge=1)
    # Reels de publicidad a transcribir (los más recientes) y reels recientes que se revisan para encontrarlos.
    # Valores de costo-beneficio (~USD 0.057 por perfil); se calculan en la /calculadora de la web.
    reels: int = Field(default=5, ge=0, le=10)
    reels_revisar: int = Field(default=10, ge=0, le=100)
    muestra_seguidores: int = Field(default=50, ge=0, le=500000)
    presupuesto_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    brief: Brief = Field(default_factory=Brief)


class ResultadoPerfil(Modelo):
    perfil: Perfil
    perfil_obtenido: bool = True
    metricas: Metricas = Field(default_factory=Metricas)
    clasificacion: Clasificacion | None = None
    audiencia_b: Audiencia | None = None
    calidad_audiencia: float | None = None
    seguidores_muestra: int = 0
    notas: list[str] = Field(default_factory=list)
    costo_usd: float = 0
    descartado: bool = False


    def audiencia_final(self) -> tuple[Audiencia | None, dict[str, str | None]]:
        """La audiencia que va al Excel y a la web, con la fuente de cada dato.

        Edad y género salen de la muestra de seguidores (B); si B no logra el dato,
        se usa lo que Jev estimó del contenido del creador (A). La ciudad sale de A.
        """
        contenido = self.clasificacion.audiencia_a if self.clasificacion else None
        muestra = self.audiencia_b if self.seguidores_muestra else None
        if contenido is None and muestra is None:
            return None, {'edad': None, 'genero': None, 'ciudad': None}
        valores, fuentes = {}, {}
        for campo in ('edad', 'genero'):
            desde_muestra = getattr(muestra, campo, None) if muestra else None
            desde_contenido = getattr(contenido, campo, None) if contenido else None
            if desde_muestra not in (None, 'Unknown'):
                valores[campo], fuentes[campo] = desde_muestra, 'seguidores'
            elif desde_contenido not in (None, 'Unknown'):
                valores[campo], fuentes[campo] = desde_contenido, 'contenido'
            else:
                valores[campo], fuentes[campo] = None, None
        valores['ciudad'] = contenido.ciudad if contenido else None
        fuentes['ciudad'] = 'contenido' if valores['ciudad'] else None
        return Audiencia(**valores), fuentes

class Corrida(Modelo):
    id: str
    fecha: str
    parametros: dict = Field(default_factory=dict)
    duracion_segundos: float = 0
    perfiles_solicitados: int = 0
    perfiles_procesados: int = 0
    costo_total_usd: float = 0
    costo_por_perfil_usd: float = 0
    costos_por_paso: dict[str, float] = Field(default_factory=dict)
    costos_confirmados: bool = True
    ejecucion_simulada: bool = False
    estado: str = 'completa'
    notas: list[str] = Field(default_factory=list)


class ResultadoCorrida(Modelo):
    perfiles: list[ResultadoPerfil]
    corrida: Corrida
