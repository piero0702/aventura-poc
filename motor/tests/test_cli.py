"""Contrato CLI con datos sintéticos, rutas locales y proveedores sin red."""
import json
from pathlib import Path
import shutil
from uuid import uuid4

import httpx
from openpyxl import load_workbook
import pytest
from typer.testing import CliRunner

from motor.almacen import Almacen
from motor.cli import app
from motor.configuracion import Configuracion, ruta_local
from motor.excel import COLUMNAS_BASE
from motor.fabrica import crear_motor as fabrica_real


@pytest.fixture
def carpeta_cli(monkeypatch):
    carpeta = ruta_local(Path('.motor/pruebas_cli') / str(uuid4()))
    carpeta.mkdir(parents=True)

    def prohibir_red(*_args, **_kwargs):
        pytest.fail('Las pruebas CLI no permiten ninguna llamada real')

    monkeypatch.setattr(httpx.Client, 'request', prohibir_red)
    monkeypatch.setattr(httpx.AsyncClient, 'request', prohibir_red)
    yield carpeta
    shutil.rmtree(carpeta)


def _estimacion(salida):
    return json.loads(salida[salida.index('{'):])


def test_cli_help_y_comandos():
    runner = CliRunner()
    respuesta = runner.invoke(app, ['--help'])
    assert respuesta.exit_code == 0
    for comando in ('lista', 'perfiles', 'validar'):
        assert comando in respuesta.stdout
        assert runner.invoke(app, [comando, '--help']).exit_code == 0


def test_cli_estimacion_sintetica_sin_llaves_ni_proveedores(carpeta_cli, monkeypatch):
    def prohibido(*_args, **_kwargs):
        pytest.fail('Estimar no debe construir proveedores ni solicitar llaves')

    monkeypatch.setattr('motor.cli.crear_motor', prohibido)
    monkeypatch.setattr(Configuracion, 'llave', prohibido)
    destino = carpeta_cli / 'estimacion.xlsx'
    respuesta = CliRunner().invoke(app, ['perfiles', '--entrada', 'fixtures/muestra-sintetica.xlsx',
                                        '--estimar', '--limite', '2', '--reels', '10',
                                        '--muestra-seguidores', '0', '--salida', str(destino)])
    assert respuesta.exit_code == 0, respuesta.output
    assert 'no se hizo ninguna llamada' in respuesta.stdout
    estimacion = _estimacion(respuesta.stdout)
    assert estimacion['perfiles'] == 2
    assert estimacion['costo_estimado_usd'] > 0
    assert estimacion['costos_por_paso']['followers'] == 0
    assert not destino.exists()


def test_cli_estima_lista_sin_consultar_seguidos(carpeta_cli, monkeypatch):
    def prohibido(*_args, **_kwargs):
        pytest.fail('La estimación de lista no debe consultar seguidos')

    monkeypatch.setattr('motor.cli.crear_motor', prohibido)
    respuesta = CliRunner().invoke(app, ['lista', '--referencia', '@referencia.sintetica',
                                        '--estimar', '--limite', '3'])
    assert respuesta.exit_code == 0, respuesta.output
    estimacion = _estimacion(respuesta.stdout)
    assert estimacion['perfiles'] == 3
    assert estimacion['costos_por_paso']['following'] > 0


@pytest.mark.parametrize('opciones', [['--reels', '11'], ['--reels', '-1'], ['--limite', '0'],
                                     ['--muestra-seguidores', '-1'], ['--presupuesto-usd', '-1']])
def test_cli_rechaza_rangos_antes_de_llamar(carpeta_cli, monkeypatch, opciones):
    def prohibido(*_args, **_kwargs):
        pytest.fail('Los parámetros inválidos no deben construir proveedores')

    monkeypatch.setattr('motor.cli.crear_motor', prohibido)
    respuesta = CliRunner().invoke(app, ['perfiles', '--entrada', 'fixtures/muestra-sintetica.xlsx',
                                        '--estimar', *opciones])
    assert respuesta.exit_code != 0


@pytest.mark.parametrize('opciones', [
    ['--entrada', '../privado.xlsx'], ['--entrada', '/etc/passwd'],
    ['--entrada', 'fixtures/muestra-sintetica.xlsx', '--salida', '../fuera.xlsx'],
    ['--entrada', 'fixtures/muestra-sintetica.xlsx', '--brief', '../brief.yaml'],
    ['--entrada', 'fixtures/muestra-sintetica.xlsx', '--salida', 'fixtures/muestra-sintetica.xlsx'],
])
def test_cli_rechaza_rutas_fuera_y_sobrescritura_de_entrada(carpeta_cli, monkeypatch, opciones):
    def prohibido(*_args, **_kwargs):
        pytest.fail('Las rutas inválidas no deben construir proveedores')

    monkeypatch.setattr('motor.cli.crear_motor', prohibido)
    respuesta = CliRunner().invoke(app, ['perfiles', '--estimar', *opciones])
    assert respuesta.exit_code == 1
    assert 'Error:' in respuesta.output


def test_cli_simulado_exporta_y_valida_muestra(carpeta_cli, monkeypatch):
    almacen = Almacen(carpeta_cli / 'motor.sqlite')
    instancias = []

    def fabrica(simulado):
        assert simulado is True
        motor = fabrica_real(simulado=True, almacen=almacen)
        instancias.append(motor)
        return motor

    monkeypatch.setattr('motor.cli.crear_motor', fabrica)
    salida = carpeta_cli / 'salida.xlsx'
    runner = CliRunner()
    respuesta = runner.invoke(app, ['perfiles', '--entrada', 'fixtures/muestra-sintetica.xlsx',
                                    '--simulado', '--limite', '3', '--reels', '1',
                                    '--muestra-seguidores', '3', '--salida', str(salida)])
    assert respuesta.exit_code == 0, respuesta.output
    assert salida.is_file()
    libro = load_workbook(salida, data_only=True)
    try:
        assert libro.sheetnames == ['Perfiles', 'Notas']
        assert [celda.value for celda in libro['Perfiles'][1]] == COLUMNAS_BASE
        assert libro['Perfiles'].max_row == 4
        assert libro['Perfiles']['J2'].value == 'Female'
        assert libro['Perfiles']['G2'].value is None
    finally:
        libro.close()
    assert instancias[0].proveedores.audio.transcripciones == 3
    informe = carpeta_cli / 'validacion.md'
    validacion = runner.invoke(app, ['validar', '--modash', 'fixtures/muestra-sintetica.xlsx',
                                     '--salida', str(salida), '--informe', str(informe),
                                     '--json', str(carpeta_cli / 'validacion.json')])
    assert validacion.exit_code == 0, validacion.output
    assert informe.is_file()
    texto = informe.read_text(encoding='utf-8')
    assert 'Línea base' in texto
    assert 'variante A' in texto
    assert 'variante B' in texto
    datos = json.loads((carpeta_cli / 'validacion.json').read_text())
    assert len(datos['filas']) == 5
    assert datos['tiene_muestra'] is True


def test_cli_lista_simulada_respeta_limite(carpeta_cli, monkeypatch):
    almacen = Almacen(carpeta_cli / 'motor.sqlite')
    monkeypatch.setattr('motor.cli.crear_motor', lambda simulado: fabrica_real(simulado=True, almacen=almacen))
    salida = carpeta_cli / 'lista.xlsx'
    respuesta = CliRunner().invoke(app, ['lista', '--referencia', '@referencia.sintetica', '--simulado',
                                        '--limite', '2', '--reels', '0', '--muestra-seguidores', '0',
                                        '--salida', str(salida), '--nombre', 'Lista anticipada sintética'])
    assert respuesta.exit_code == 0, respuesta.output
    libro = load_workbook(salida, data_only=True)
    try:
        assert libro['Perfiles'].max_row == 3
    finally:
        libro.close()
    corrida = _estimacion(respuesta.stdout)
    registro = almacen.obtener_corrida('http:' + corrida['id'])
    assert registro['marca'] == 'Lista anticipada sintética'
    assert registro['fuente'] == '@referencia.sintetica'
    assert len(registro['resultados']) == 2
    assert registro['excel'] == str(salida)


def test_cli_validar_rechaza_json_fuera_y_sobrescritura(carpeta_cli):
    runner = CliRunner()
    for destino in ('../no.json', 'fixtures/muestra-sintetica.xlsx'):
        respuesta = runner.invoke(app, ['validar', '--modash', 'fixtures/muestra-sintetica.xlsx',
                                        '--salida', 'fixtures/muestra-sintetica.xlsx',
                                        '--informe', str(carpeta_cli / 'informe.md'), '--json', destino])
        assert respuesta.exit_code == 1
        assert 'Error:' in respuesta.output


def test_cli_presupuesto_agotado_genera_excel_y_codigo_no_exitoso(carpeta_cli, monkeypatch):
    almacen = Almacen(carpeta_cli / 'motor.sqlite')
    monkeypatch.setattr('motor.cli.crear_motor', lambda simulado: fabrica_real(simulado=True, almacen=almacen))
    salida = carpeta_cli / 'parcial.xlsx'
    respuesta = CliRunner().invoke(app, ['perfiles', '--entrada', 'fixtures/muestra-sintetica.xlsx',
                                        '--simulado', '--presupuesto-usd', '0', '--salida', str(salida)])
    assert respuesta.exit_code == 2, respuesta.output
    assert salida.is_file()
    assert 'presupuesto_agotado' in respuesta.stdout
    corrida = _estimacion(respuesta.stdout)
    registro = almacen.obtener_corrida('http:' + corrida['id'])
    assert registro['estado'] == 'parcial'
    assert registro['corrida']['estado'] == 'parcial'
    assert len(registro['resultados']) == 5
