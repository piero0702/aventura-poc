"""Contrato web sobre resultados del motor, sin HTTP hacia proveedores."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from motor.almacen import Almacen
from motor.cli import app as cli
from motor.configuracion import Configuracion, ruta_local
from motor.http import crear_app
from motor.modelos import (Audiencia, AudienciaSeguidor, Clasificacion, Corrida,
                          Marca, Perfil, Post, ResultadoCorrida, ResultadoPerfil)
from motor.presentacion import presentar_perfil

AUTORIZACION = {'Authorization': 'Bearer token-local'}


@pytest.fixture
def entorno_web():
    carpeta = ruta_local(Path('.motor/integracion-web') / str(uuid4()))
    carpeta.mkdir(parents=True)
    almacen = Almacen(carpeta / 'datos.sqlite')
    yield carpeta, almacen
    for registro in almacen.listar_corridas():
        if registro.get('excel'):
            ruta_local(registro['excel']).unlink(missing_ok=True)
    shutil.rmtree(carpeta)


def test_perfil_audiencia_excel_distribuciones_y_evidencia():
    resultado = ResultadoPerfil(
        perfil=Perfil(usuario='prueba.sintetica', posts=[Post(url='https://example.com/post', fecha='2026-09-14')]),
        seguidores_muestra=4, audiencia_b=Audiencia(edad='25-34', genero='Female'),
        clasificacion=Clasificacion(audiencia_a=Audiencia(edad='35-44', genero='Male', ciudad='Lima'),
            seguidores=[AudienciaSeguidor(usuario='uno', edad='25-34', genero='Female', persona_real=True),
                        AudienciaSeguidor(usuario='dos', edad='18-24', genero='Male', persona_real=None),
                        AudienciaSeguidor(usuario='tres', edad='65+', genero='Male', persona_real=False),
                        AudienciaSeguidor(usuario='cuatro', genero='Unknown')],
            marcas=[Marca(nombre='Marca ficticia', tipo='canje', post_evidencia='https://example.com/post'),
                    Marca(nombre='Mención ficticia', tipo='etiqueta', post_evidencia='https://example.com/post')]))
    perfil = presentar_perfil(resultado, 1)
    assert perfil['audiencia'] == dict(edad='25-34', genero='Female', ciudad='Lima', fuente='seguidores',
                                      fuentes={'edad': 'seguidores', 'genero': 'seguidores', 'ciudad': 'contenido'},
                                      distribucion_edad={'25-34': .5, '18-24': .5},
                                      distribucion_genero={'Female': .5, 'Male': .5})
    assert perfil['marcas'][0]['fecha'] == '2026-09-14'
    assert len(perfil['marcas']) == len(perfil['menciones']) == 1
    assert perfil['metricas']['er'] is None
    resultado.seguidores_muestra = 0
    perfil = presentar_perfil(resultado, 1)
    assert perfil['audiencia'] == dict(edad='35-44', genero='Male', ciudad='Lima', fuente='contenido',
                                      fuentes={'edad': 'contenido', 'genero': 'contenido', 'ciudad': 'contenido'})
    # Con muestra pero sin edad en B, la edad cae al contenido (A) y se marca su fuente.
    resultado.seguidores_muestra = 30
    resultado.audiencia_b = Audiencia(genero='Female')
    audiencia, fuentes = resultado.audiencia_final()
    assert (audiencia.edad, audiencia.genero) == ('35-44', 'Female')
    assert fuentes == {'edad': 'contenido', 'genero': 'seguidores', 'ciudad': 'contenido'}


def test_progreso_persistido_limitado_y_409_404(entorno_web, monkeypatch):
    carpeta, almacen = entorno_web
    config = Configuracion(secretos={'MOTOR_HTTP_TOKEN': 'token-local'})
    identificador_pendiente = str(uuid4())
    almacen.guardar_corrida('http:' + identificador_pendiente,
                           dict(id=identificador_pendiente, estado='interrumpida', fecha='2026-01-01'))
    escrituras = []
    guardar = almacen.guardar_corrida

    def registrar(clave, datos):
        escrituras.append(json.loads(json.dumps(datos)))
        guardar(clave, datos)

    monkeypatch.setattr(almacen, 'guardar_corrida', registrar)
    reloj = iter([0, .1, .2, .9, 1.1, 1.2, 2.2, 2.3, 2.4])
    monkeypatch.setattr('motor.http.monotonic', lambda: next(reloj))

    class MotorPrueba:
        def __init__(self):
            self.proveedores = self

        def cerrar(self):
            pass

        def ejecutar(self, usuarios, opciones, referencia, corrida_id, al_avanzar):
            for paso in ('seguidos', 'perfiles', 'filtro', 'reels', 'transcripcion', 'clasificacion'):
                al_avanzar(paso, 1, 1, 0)
            return ResultadoCorrida(perfiles=[ResultadoPerfil(perfil=Perfil(usuario='sintetico'))],
                                    corrida=Corrida(id=corrida_id, fecha='2026-10-27T00:00:00Z',
                                                   perfiles_procesados=1, perfiles_solicitados=1))

    monkeypatch.setattr('motor.fabrica.crear_motor', lambda **_: MotorPrueba())
    with TestClient(crear_app(config, almacen=almacen, validacion=carpeta / 'ausente.json')) as cliente:
        assert cliente.get('/validacion', headers=AUTORIZACION).status_code == 404
        assert cliente.get('/listas/' + identificador_pendiente + '/perfiles', headers=AUTORIZACION).status_code == 409
        assert cliente.get('/listas/' + str(uuid4()) + '/perfiles', headers=AUTORIZACION).status_code == 404
        respuesta = cliente.post('/listas', json={'referencia': 'referencia.sintetica', 'simulado': True}, headers=AUTORIZACION)
        identificador = respuesta.json()['id']
        estado = cliente.get('/listas/' + identificador, headers=AUTORIZACION).json()
        assert estado['estado'] == 'completa'
        assert estado['progreso'] == dict(paso='excel', hechos=1, total=1, descartados=0, porcentaje=100,
                                          en_curso=0, actividad='Excel listo')
        assert 'resultados' not in estado
        perfiles = cliente.get('/listas/' + identificador + '/perfiles', headers=AUTORIZACION).json()
        assert perfiles[0]['usuario'] == 'sintetico'
        intermedias = [fila for fila in escrituras if fila.get('progreso') and fila['estado'] == 'en_proceso']
        assert [fila['progreso']['paso'] for fila in intermedias] == ['reels', 'clasificacion']


def test_http_y_cli_comparten_historial_y_validacion(entorno_web, monkeypatch):
    carpeta, almacen = entorno_web
    from motor.fabrica import crear_motor
    fabrica = crear_motor
    monkeypatch.setattr('motor.cli.crear_motor', lambda **kwargs: fabrica(almacen=almacen, **kwargs))
    salida = carpeta / 'cli.xlsx'
    resultado = CliRunner().invoke(cli, ['perfiles', '--entrada', 'fixtures/muestra-sintetica.xlsx',
        '--simulado', '--nombre', 'Lista sintética previa', '--salida', str(salida)])
    assert resultado.exit_code == 0, resultado.output
    ruta_json = carpeta / 'validacion.json'
    validada = CliRunner().invoke(cli, ['validar', '--modash', 'fixtures/muestra-sintetica.xlsx',
        '--salida', str(salida), '--informe', str(carpeta / 'informe.md'), '--json', str(ruta_json)])
    assert validada.exit_code == 0, validada.output
    config = Configuracion(secretos={'MOTOR_HTTP_TOKEN': 'token-local'})
    with TestClient(crear_app(config, almacen=almacen, validacion=ruta_json)) as cliente:
        respuesta = cliente.post('/listas', json={'referencia': 'referencia.sintetica', 'simulado': True,
            'limite': 2, 'brief': {'marca': 'Campaña sintética'}}, headers=AUTORIZACION)
        assert respuesta.status_code == 202
        historial = cliente.get('/listas', headers=AUTORIZACION).json()
        assert len(historial) == 2
        assert historial[0]['marca'] == 'Campaña sintética'
        assert historial[1]['marca'] == 'Lista sintética previa'
        for registro in historial:
            assert cliente.get('/listas/' + registro['id'] + '/perfiles', headers=AUTORIZACION).status_code == 200
        validacion = cliente.get('/validacion', headers=AUTORIZACION).json()
        assert len(validacion['criterios']) == 7
        assert len(validacion['filas']) == validacion['perfiles'] == 5
        assert validacion['criterios'][-1]['pasa'] is False
        assert 'simulad' in validacion['criterios'][-1]['detalle'].lower()


def test_sqlite_corridas_simultaneas_sin_compartir_conexiones(entorno_web):
    carpeta, almacen = entorno_web
    config = Configuracion(secretos={'MOTOR_HTTP_TOKEN': 'token-local'})
    with TestClient(crear_app(config, almacen=almacen, validacion=carpeta / 'ausente.json')) as cliente:
        def lanzar(indice):
            return cliente.post('/listas', headers=AUTORIZACION,
                json={'usuarios': ['sol.sintetica'], 'simulado': True, 'reels': 0})
        with ThreadPoolExecutor(max_workers=4) as hilos:
            respuestas = list(hilos.map(lanzar, range(4)))
        assert all(respuesta.status_code == 202 for respuesta in respuestas)
        historial = cliente.get('/listas', headers=AUTORIZACION).json()
        assert len(historial) == 4
        assert all(fila['estado'] == 'completa' for fila in historial)


def test_primer_paso_visible_durante_llamada_larga_sin_escrituras_extra(entorno_web, monkeypatch):
    carpeta, almacen = entorno_web
    iniciada, continuar = Event(), Event()
    identificadores = []

    class MotorLento:
        def __init__(self):
            self.proveedores = self

        def cerrar(self):
            pass

        def ejecutar(self, usuarios, opciones, referencia, corrida_id, al_avanzar):
            identificadores.append(corrida_id)
            al_avanzar('seguidos', 0, 1, 0)
            iniciada.set()
            assert continuar.wait(5)
            return ResultadoCorrida(perfiles=[], corrida=Corrida(id=corrida_id, fecha='2026-10-27'))

    monkeypatch.setattr('motor.fabrica.crear_motor', lambda **_: MotorLento())
    config = Configuracion(secretos={'MOTOR_HTTP_TOKEN': 'token-local'})
    with TestClient(crear_app(config, almacen=almacen, validacion=carpeta / 'ausente.json')) as cliente:
        with ThreadPoolExecutor(max_workers=1) as hilo:
            tarea = hilo.submit(cliente.post, '/listas', headers=AUTORIZACION,
                                json={'referencia': 'referencia.sintetica', 'simulado': True})
            try:
                assert iniciada.wait(3)
                identificador = identificadores[0]
                persistida = almacen.obtener_corrida('http:' + identificador)
                assert 'progreso' not in persistida
                respuesta = cliente.get('/listas/' + identificador, headers=AUTORIZACION).json()
                assert respuesta['progreso'] == dict(paso='seguidos', hechos=0, total=1, descartados=0)
            finally:
                continuar.set()
            assert tarea.result().status_code == 202


@pytest.mark.parametrize('ruta', ['/listas', '/validacion', f'/listas/{uuid4()}/perfiles'])
def test_rutas_nuevas_exigen_bearer(entorno_web, ruta):
    carpeta, almacen = entorno_web
    config = Configuracion(secretos={'MOTOR_HTTP_TOKEN': 'token-local'})
    with TestClient(crear_app(config, almacen=almacen, validacion=carpeta / 'ausente.json')) as cliente:
        assert cliente.get(ruta).status_code == 401
