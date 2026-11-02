"""Métricas de interacción sobre los últimos doce posts del creador."""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, median

from motor.modelos import Metricas, Post


def _fecha_orden(post: Post) -> float:
    """Las fechas ausentes conservan entre sí el orden del proveedor."""
    try:
        fecha = datetime.fromisoformat(post.fecha.replace('Z', '+00:00'))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.timestamp()
    except (ValueError, OverflowError):
        return float('-inf')


def sin_fijados(posts: list[Post]) -> list[Post]:
    """Quita los posts fijados: suelen ser virales antiguos y disparan el promedio.

    Si el proveedor no marca ninguno, se detectan por orden: Instagram los pone
    primero, antes del tramo cronológico, y son más antiguos que su primer post.
    Si quedarían menos de tres posts, se conservan todos.
    """
    if any(post.fijado for post in posts):
        restantes = [post for post in posts if not post.fijado]
    else:
        fechas = [_fecha_orden(post) for post in posts]
        inicio = len(posts) - 1
        while inicio > 0 and fechas[inicio - 1] >= fechas[inicio]:
            inicio -= 1
        if not posts or float('-inf') in fechas[:inicio + 1]:
            return list(posts)
        restantes = [post for indice, post in enumerate(posts)
                     if indice >= inicio or fechas[indice] >= fechas[inicio]]
    return restantes if len(restantes) >= 3 else list(posts)


def calcular_metricas(posts: list[Post], followers: int, agregacion: str = 'promedio') -> Metricas:
    """Calcula promedio (por defecto) o mediana sin imputar datos ausentes.

    Primero quita los fijados (ver sin_fijados) y toma los doce más recientes, ordenados por su fecha cuando se
    conoce. Después excluye por completo los posts con likes ocultos, negativos
    o ausentes. Avg. Likes = agregar(likes); Avg. Comments = agregar(comentarios
    conocidos y no negativos); Avg. Reel Plays = agregar(vistas conocidas y no
    negativas de reels). Engagements = agregar(likes + comentarios por post),
    usando los posts que tienen ambos datos. ER = Engagements / Followers,
    expresado como fracción; sin followers o sin interacciones queda sin dato.
    """
    if agregacion not in {'promedio', 'mediana'}:
        raise ValueError('METRICAS_AGREGACION debe ser promedio o mediana')
    funcion = mean if agregacion == 'promedio' else median
    def agregar(valores):
        return float(funcion(valores)) if valores else None
    ultimos = sorted(sin_fijados(posts), key=_fecha_orden, reverse=True)[:12]
    visibles = [post for post in ultimos if not post.likes_ocultos
                and post.likes is not None and post.likes >= 0]
    likes = [post.likes for post in visibles]
    comentarios = [post.comentarios for post in visibles
                   if post.comentarios is not None and post.comentarios >= 0]
    vistas = [post.vistas for post in visibles if post.es_reel
              and post.vistas is not None and post.vistas >= 0]
    interacciones = [post.likes + post.comentarios for post in visibles
                     if post.comentarios is not None and post.comentarios >= 0]
    engagements = agregar(interacciones)
    return Metricas(
        likes=agregar(likes), comentarios=agregar(comentarios),
        reel_plays=agregar(vistas), engagements=engagements,
        er=engagements / followers if engagements is not None and followers > 0 else None,
    )
