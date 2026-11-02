"""Casos de promedio, mediana y filtro barato, sin servicios externos."""
import pytest

from motor.filtro import motivo_descarte
from motor.metricas import calcular_metricas
from motor.modelos import Brief, Perfil, Post


def test_mediana_no_promedio_y_engagement_por_post():
    posts = [Post(likes=10, comentarios=50, tipo='reel', vistas=100),
             Post(likes=20, comentarios=1, tipo='imagen', vistas=99999),
             Post(likes=10000, comentarios=2, tipo='reel', vistas=300)]
    metricas = calcular_metricas(posts, 1000, 'mediana')
    assert metricas.likes == 20
    assert metricas.comentarios == 2
    assert metricas.reel_plays == 200
    assert metricas.engagements == 60
    assert metricas.er == .06


def test_promedio_por_defecto_sobre_cada_campo_y_engagement_por_post():
    posts = [Post(likes=10, comentarios=50, tipo='reel', vistas=100),
             Post(likes=20, comentarios=1, tipo='imagen', vistas=99999),
             Post(likes=10000, comentarios=2, tipo='reel', vistas=300)]
    metricas = calcular_metricas(posts, 1000)
    assert metricas.likes == pytest.approx(10030 / 3)
    assert metricas.comentarios == pytest.approx(53 / 3)
    assert metricas.reel_plays == 200
    assert metricas.engagements == pytest.approx(10083 / 3)
    assert metricas.er == pytest.approx(10083 / 3000)


def test_agregacion_invalida_no_se_interpreta_como_otra_formula():
    with pytest.raises(ValueError, match='METRICAS_AGREGACION'):
        calcular_metricas([], 100, 'otra')


@pytest.mark.parametrize('agregacion', ['promedio', 'mediana'])
@pytest.mark.parametrize('oculto', [Post(likes=99999, likes_ocultos=True, comentarios=9999,
                                      tipo='reel', vistas=99999),
                                    Post(likes=-1, comentarios=9999, tipo='reel', vistas=99999),
                                    Post(likes=None, comentarios=9999, tipo='reel', vistas=99999)])
def test_omite_posts_con_likes_ocultos_o_desconocidos(oculto, agregacion):
    metricas = calcular_metricas([Post(likes=20, comentarios=2, tipo='reel', vistas=100), oculto], 100, agregacion)
    assert metricas.model_dump() == dict(likes=20, comentarios=2, reel_plays=100,
                                        engagements=22, er=.22)


def test_toma_ultimos_doce_antes_de_excluir_ocultos():
    posts = [Post(likes=i, comentarios=0, fecha=f'2026-10-{i:02d}') for i in range(1, 14)]
    posts[-1].likes_ocultos = True
    metricas = calcular_metricas(list(reversed(posts)), 100)
    assert metricas.likes == 7  # Días 2 a 12; el día 1 no vuelve a la ventana.


def test_fechas_ausentes_conservan_orden_del_proveedor():
    posts = [Post(likes=i, comentarios=0) for i in range(20)]
    assert calcular_metricas(posts, 1).likes == 5.5


def test_ceros_y_datos_ausentes():
    assert calcular_metricas([], 0).er is None
    assert calcular_metricas([Post(likes=0, comentarios=0)], 100).er == 0
    metricas = calcular_metricas([Post(likes=20)], 0)
    assert metricas.likes == 20
    assert metricas.comentarios is None
    assert metricas.engagements is None
    assert metricas.reel_plays is None
    assert metricas.er is None


def test_vistas_y_comentarios_invalidos_no_se_imputan():
    metricas = calcular_metricas([Post(likes=20, comentarios=-1, tipo='reel', vistas=-1)], 100)
    assert metricas.likes == 20
    assert metricas.comentarios is None
    assert metricas.engagements is None
    assert metricas.reel_plays is None


@pytest.mark.parametrize(('cambios', 'esperado'), [
    ({'existe': False}, 'no existe'),
    ({'privada': True}, 'privada'),
    ({'followers': 99}, 'debajo'),
    ({'followers': 201}, 'encima'),
])
def test_filtro_motivos(cambios, esperado):
    datos = dict(usuario='cuenta', followers=150, posts=[Post(tipo='reel')])
    datos.update(cambios)
    assert esperado in motivo_descarte(Perfil(**datos), Brief(followers_min=100, followers_max=200))


def test_filtro_no_descarta_sin_posts():
    # Apify a veces devuelve el perfil sin latestPosts: los reels se piden aparte.
    assert motivo_descarte(Perfil(usuario='cuenta', followers=150, posts=[]), Brief()) is None


def test_metricas_excluyen_fijados_marcados():
    recientes = [Post(fecha=f'2026-10-{d:02d}T00:00:00Z', likes=100, comentarios=0) for d in (20, 19, 18)]
    fijado = Post(fecha='2026-02-13T00:00:00Z', likes=7_000_000, comentarios=0, fijado=True)
    assert calcular_metricas([fijado, *recientes], 1000).likes == 100


def test_metricas_detectan_fijados_por_orden():
    # Sin marca del proveedor: los primeros posts, más antiguos que el tramo cronológico, son fijados.
    fijados = [Post(fecha=f'2026-0{m}-01T00:00:00Z', likes=1_000_000, comentarios=0) for m in (5, 2)]
    recientes = [Post(fecha=f'2026-10-{d:02d}T00:00:00Z', likes=d * 10, comentarios=0) for d in (27, 26, 24, 21)]
    metricas = calcular_metricas([*fijados, *recientes], 1000, 'promedio')
    assert metricas.likes == sum(d * 10 for d in (27, 26, 24, 21)) / 4


def test_metricas_conservan_fijados_si_quedan_pocos():
    posts = [Post(fecha='2026-01-01T00:00:00Z', likes=500, comentarios=0),
             Post(fecha='2026-10-02T00:00:00Z', likes=100, comentarios=0),
             Post(fecha='2026-10-01T00:00:00Z', likes=100, comentarios=0)]
    assert calcular_metricas(posts, 1000).likes == pytest.approx(700 / 3)


@pytest.mark.parametrize('followers', [100, 200])
def test_filtro_limites_inclusivos(followers):
    perfil = Perfil(usuario='cuenta', followers=followers, posts=[Post(tipo='reel')])
    assert motivo_descarte(perfil, Brief(followers_min=100, followers_max=200)) is None


def test_reels_respetan_el_minimo_por_corrida_de_apify():
    from decimal import Decimal
    from motor.costos import Precios
    precios = Precios()
    assert precios.costo('reels', 3) == Decimal('0.0073')
    assert precios.costo('reels', 0) == 0
    assert precios.costo('reels', 10) == Decimal('0.0100')
