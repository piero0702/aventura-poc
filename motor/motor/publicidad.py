"""Detecta posts de publicidad por la etiqueta de Instagram, hashtags y frases del caption.

Es un filtro para elegir qué reels transcribir, no una afirmación de patrocinio: Jev confirma
después la relación con cada marca. La etiqueta oficial («Colaboración pagada») casi nunca viene
en Apify (2 de 511 reels el 28-oct); los creadores la declaran en el caption.
"""
import re

from motor.modelos import Post

# Hashtags en español e inglés que se usan en Perú para declarar publicidad, canje o embajada.
HASHTAGS = (
    'ad', 'ads', 'advertisement', 'advertising', 'sponsored', 'sponsor', 'paidpartnership', 'paidpartner',
    'partner', 'partnership', 'brandpartner', 'brandambassador', 'ambassador', 'gifted', 'giftedby', 'pr', 'prpackage',
    'publi', 'publicidad', 'publicidadpagada', 'publicidadpaga', 'publiinfluencer', 'patrocinado', 'patrocinada',
    'patrocinio', 'auspicio', 'auspiciado', 'auspiciada', 'colab', 'collab', 'colaboracion', 'colaboración',
    'colaboracionpagada', 'colaboraciónpagada', 'canje', 'embajador', 'embajadora', 'embajadordemarca',
    'embajadorademarca', 'contenidopatrocinado', 'alianzacomercial',
)
_HASHTAG = re.compile(r'(?<![\w#])#(' + '|'.join(sorted(map(re.escape, HASHTAGS), key=len, reverse=True)) + r')(?![\w])',
                      re.IGNORECASE)
# Frases que declaran la relación aunque no haya hashtag.
_FRASE = re.compile(
    r'\b(publicidad|colaboraci[oó]n pagada|en colaboraci[oó]n con|en alianza con|patrocinad[oa] por|auspiciad[oa] por|'
    r'paid partnership|canje|c[oó]digo de descuento|usa mi c[oó]digo|con mi c[oó]digo|cup[oó]n)\b',
    re.IGNORECASE)


def reels_a_revisar(opciones) -> int:
    """Reels recientes que se piden para buscar publicidad; sin reels a transcribir no se pide ninguno."""
    return max(opciones.reels, opciones.reels_revisar) if opciones.reels else 0


def es_publicidad(post: Post | dict) -> bool:
    if isinstance(post, dict):
        post = Post(caption=post.get('caption') or '', patrocinado=bool(post.get('patrocinado')),
                    patrocinadores=post.get('patrocinadores') or [])
    if post.patrocinado or post.patrocinadores:
        return True
    texto = post.caption or ''
    return bool(_HASHTAG.search(texto) or _FRASE.search(texto))
