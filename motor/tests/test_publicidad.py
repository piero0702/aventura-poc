import pytest

from motor.modelos import Opciones, Post
from motor.publicidad import es_publicidad, reels_a_revisar


@pytest.mark.parametrize('caption', [
    'Nuevo sabor 🍓 #publicidad @marca.prueba', '#Publi con @tienda.prueba', 'Increíble #AD', '#ColaboraciónPagada',
    'Publicidad. Gracias @marca.prueba', 'En colaboración con @tienda.prueba', 'Usa mi código PRUEBA10',
    '#canje de @spa.prueba', '#embajadora de @marca.prueba', '#gifted by @marca.prueba',
])
def test_detecta_publicidad_en_el_caption(caption):
    assert es_publicidad(Post(caption=caption))


@pytest.mark.parametrize('caption', [
    'Domingo en familia', 'Vamos Alianza Lima', '#adidas en la pista', '#padel con amigos', 'Gracias @amiga.prueba por la foto',
    '#Lima #adventure', 'El #pubcrawl de anoche',
])
def test_no_marca_captions_organicos(caption):
    assert not es_publicidad(Post(caption=caption))


def test_etiqueta_oficial_y_posts_del_contexto():
    assert es_publicidad(Post(patrocinado=True))
    assert es_publicidad({'caption': '', 'patrocinadores': ['marca.prueba']})
    assert not es_publicidad({'caption': 'Sin nada comercial'})


def test_reels_a_revisar():
    assert reels_a_revisar(Opciones(reels=5, reels_revisar=20)) == 20
    assert reels_a_revisar(Opciones(reels=8, reels_revisar=3)) == 8
    assert reels_a_revisar(Opciones(reels=0, reels_revisar=20)) == 0
