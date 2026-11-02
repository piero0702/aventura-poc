"""Filtro local que evita transcripciones y clasificación innecesarias."""
from motor.modelos import Brief, Perfil


def motivo_descarte(perfil: Perfil, brief: Brief) -> str | None:
    """Devuelve un motivo auditable o None si el perfil puede continuar."""
    if not perfil.existe:
        return 'El perfil no existe o no está disponible.'
    if perfil.privada:
        return 'Cuenta privada.'
    if perfil.followers < brief.followers_min:
        return f'Followers por debajo del mínimo del brief ({brief.followers_min}).'
    if brief.followers_max is not None and perfil.followers > brief.followers_max:
        return f'Followers por encima del máximo del brief ({brief.followers_max}).'
    return None
