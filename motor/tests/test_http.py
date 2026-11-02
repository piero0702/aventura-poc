"""API autenticada con trabajos simulados, persistencia y rutas locales."""
from pathlib import Path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from motor.almacen import Almacen
from motor.configuracion import Configuracion, ruta_local
from motor.http import crear_app
from motor.modelos import Corrida, Perfil, ResultadoCorrida, ResultadoPerfil


@pytest.fixture
def entorno():
    carpeta = ruta_local(Path('.motor/pruebas_http') / str(uuid4()))
    carpeta.mkdir(parents=True)
    almacen = Almacen(carpeta / 'pruebas.sqlite')
    configuracion = Configuracion(secretos={'MOTOR_HTTP_TOKEN': 'token-de-prueba'})
    archivos = []
    yield almacen, configuracion, archivos
    for archivo in archivos:
        archivo.unlink(missing_ok=True)
    shutil.rmtree(carpeta)


def _resultado(identificador):
    return ResultadoCorrida(perfiles=[ResultadoPerfil(perfil=Perfil(usuario='cuenta'))],
                            corrida=Corrida(id=identificador, fecha='2026-10-27',
                                           perfiles_solicitados=1, perfiles_procesados=1,
                                           costo_total_usd=.003, costo_por_perfil_usd=.003))


AUTORIZACION = {'Authorization': 'Bearer token-de-prueba'}


def test_http_token_y_ciclo_de_trabajo_persistente(entorno):
    almacen, configuracion, archivos = entorno
    llamadas = []

    def ejecutor(solicitud, identificador):
        llamadas.append(solicitud.usuarios)
        almacen.registrar(identificador, 'cuenta', 'perfil', 1, .003, 'confirmado')
        return _resultado(identificador)

    with TestClient(crear_app(configuracion, ejecutor, almacen)) as cliente:
        assert cliente.post('/listas', json={'usuarios': ['cuenta']}).status_code == 401
        assert cliente.post('/listas', json={'usuarios': ['cuenta']},
                            headers={'Authorization': 'Bearer incorrecto'}).status_code == 401
        respuesta = cliente.post('/listas', json={'usuarios': ['@Cuenta', 'cuenta']}, headers=AUTORIZACION)
        assert respuesta.status_code == 202
        identificador = respuesta.json()['id']
        assert respuesta.json() == dict(id=identificador, estado='pendiente')
        estado = cliente.get(f'/listas/{identificador}', headers=AUTORIZACION).json()
        assert estado['estado'] == 'completa'
        assert estado['costo_total_usd'] == .003
        assert 'excel' not in estado
        descarga = cliente.get(f'/listas/{identificador}/excel', headers=AUTORIZACION)
        assert descarga.status_code == 200
        assert descarga.content.startswith(b'PK')
        assert cliente.get(f'/listas/{uuid4()}', headers=AUTORIZACION).status_code == 404
        archivos.append(ruta_local(f'.motor/salidas/{identificador}.xlsx'))
    assert llamadas == [['cuenta']]
    with TestClient(crear_app(configuracion, ejecutor, almacen)) as cliente:
        assert cliente.get(f'/listas/{identificador}', headers=AUTORIZACION).json()['estado'] == 'completa'


def test_http_sin_token_configurado_denegado(entorno):
    almacen, _, _ = entorno
    with TestClient(crear_app(Configuracion(), almacen=almacen)) as cliente:
        assert cliente.post('/listas', json={'usuarios': ['cuenta']}, headers=AUTORIZACION).status_code == 503


@pytest.mark.parametrize('solicitud', [
    {}, {'usuarios': []}, {'usuarios': ['cuenta'], 'referencia': 'otra'},
    {'referencia': 'cuenta', 'reels': 11}, {'usuarios': ['https://instagram.com/cuenta']},
    {'usuarios': ['cuenta'], 'brief': {'followers_min': 200, 'followers_max': 100}},
    {'entrada': '../datos.xlsx'}, {'entrada': '/etc/passwd'},
    {'entrada': 'fixtures/no-existe.xlsx'},
])
def test_http_rechaza_parametros_y_rutas_fuera_de_carpeta(entorno, solicitud):
    almacen, configuracion, _ = entorno
    with TestClient(crear_app(configuracion, almacen=almacen)) as cliente:
        assert cliente.post('/listas', json=solicitud, headers=AUTORIZACION).status_code == 422


def test_http_estimacion_sin_proveedores_y_sin_excel(entorno):
    almacen, configuracion, _ = entorno

    def prohibido(*_):
        pytest.fail('La estimación no debe invocar el ejecutor ni los proveedores')

    with TestClient(crear_app(configuracion, prohibido, almacen)) as cliente:
        respuesta = cliente.post('/listas', json={'entrada': 'fixtures/muestra-sintetica.xlsx',
                                                 'estimar': True, 'limite': 2}, headers=AUTORIZACION)
        identificador = respuesta.json()['id']
        estado = cliente.get(f'/listas/{identificador}', headers=AUTORIZACION).json()
        assert estado['estado'] == 'estimada'
        assert estado['costo_total_usd'] == 0
        assert estado['estimacion']['perfiles'] == 2
        assert estado['estimacion']['costo_estimado_usd'] > 0
        assert estado['estimacion']['costo_total_usd'] == estado['estimacion']['costo_estimado_usd']
        assert cliente.get(f'/listas/{identificador}/excel', headers=AUTORIZACION).status_code == 409


def test_http_reinicio_marca_interrumpida_y_mantiene_costos(entorno):
    almacen, configuracion, _ = entorno
    identificador = str(uuid4())
    almacen.guardar_corrida('http:' + identificador,
                           dict(id=identificador, estado='en_proceso', costo_total_usd=0))
    almacen.registrar(identificador, 'cuenta', 'perfil', 1, .0026)
    with TestClient(crear_app(configuracion, almacen=almacen)) as cliente:
        datos = cliente.get(f'/listas/{identificador}', headers=AUTORIZACION).json()
        assert datos['estado'] == 'interrumpida'
        assert datos['costo_total_usd'] == .0026


def test_http_error_no_expone_secreto(entorno):
    almacen, configuracion, _ = entorno

    def fallar(*_):
        raise RuntimeError('https://proveedor.example?token=secreto-muy-privado')

    with TestClient(crear_app(configuracion, fallar, almacen)) as cliente:
        respuesta = cliente.post('/listas', json={'usuarios': ['cuenta']}, headers=AUTORIZACION)
        estado = cliente.get('/listas/' + respuesta.json()['id'], headers=AUTORIZACION)
        assert estado.json()['estado'] == 'error'
        assert 'secreto-muy-privado' not in estado.text


def test_http_factory_recibe_opciones_y_cierra_proveedores(entorno, monkeypatch):
    almacen, configuracion, archivos = entorno
    llamadas = []

    class MotorFalso:
        proveedores = None

        def __init__(self):
            self.proveedores = self

        def ejecutar(self, usuarios, opciones, referencia, corrida_id, al_avanzar=None):
            llamadas.append((usuarios, opciones.reels, referencia))
            resultado = _resultado(corrida_id)
            resultado.corrida.estado = 'presupuesto_agotado'
            return resultado

        def cerrar(self):
            llamadas.append('cerrado')

    def fabrica(simulado, configuracion, almacen):
        assert simulado is True
        return MotorFalso()

    monkeypatch.setattr('motor.fabrica.crear_motor', fabrica)
    with TestClient(crear_app(configuracion, almacen=almacen)) as cliente:
        respuesta = cliente.post('/listas', json={'referencia': '@CuEnta', 'reels': 2, 'simulado': True},
                                 headers=AUTORIZACION)
        identificador = respuesta.json()['id']
        estado = cliente.get('/listas/' + identificador, headers=AUTORIZACION).json()
        assert estado['estado'] == 'parcial'
        archivos.append(ruta_local(f'.motor/salidas/{identificador}.xlsx'))
    assert llamadas == [(None, 2, 'cuenta'), 'cerrado']
