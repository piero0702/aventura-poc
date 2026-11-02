"""El contrato de configuración evita leer secretos del entorno o rutas ajenas."""
from pathlib import Path
from zipfile import BadZipFile
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner
from motor.cli import app
from motor.configuracion import Configuracion, ruta_local
from motor.modelos import Audiencia, Brief


def test_llaves_solo_de_archivo_sin_interpolacion_del_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'no_leer_entorno')
    monkeypatch.setenv('VALOR_EXTERNO', 'no_expandir')
    archivo = tmp_path / 'config.env'
    archivo.write_text('TYPESAFE_API_KEY=${VALOR_EXTERNO}\nMOTOR_HTTP_TOKEN=token_falso\n', encoding='utf-8')
    configuracion = Configuracion.cargar(archivo)
    assert configuracion.llave('TYPESAFE_API_KEY') == '${VALOR_EXTERNO}'
    assert configuracion.llave('MOTOR_HTTP_TOKEN') == 'token_falso'
    with pytest.raises(ValueError, match='GROQ_API_KEY'):
        configuracion.llave('GROQ_API_KEY')
    assert 'token_falso' not in repr(configuracion)
    assert 'VALOR_EXTERNO' not in repr(configuracion)


def test_modelos_validan_edad_y_rango():
    with pytest.raises(ValidationError):
        Audiencia(edad='veintitantos')
    with pytest.raises(ValidationError):
        Brief(followers_min=100, followers_max=10)


def test_configura_agregacion_y_retraso_solo_desde_archivo(tmp_path, monkeypatch):
    monkeypatch.setenv('METRICAS_AGREGACION', 'mediana')
    archivo = tmp_path / 'config.env'
    archivo.write_text('MOTOR_SIMULADO_RETRASO_S=0.2\n', encoding='utf-8')
    configuracion = Configuracion.cargar(archivo)
    assert configuracion.metricas_agregacion == 'promedio'
    assert configuracion.simulado_retraso_s == .2
    archivo.write_text('METRICAS_AGREGACION=mediana\n', encoding='utf-8')
    assert Configuracion.cargar(archivo).metricas_agregacion == 'mediana'


@pytest.mark.parametrize('contenido', ['METRICAS_AGREGACION=suma', 'MOTOR_SIMULADO_RETRASO_S=-1',
                                     'MOTOR_SIMULADO_RETRASO_S=nan', 'MOTOR_SIMULADO_RETRASO_S=inf'])
def test_configuracion_rechaza_agregacion_o_retraso_invalidos(tmp_path, contenido):
    archivo = tmp_path / 'config.env'
    archivo.write_text(contenido, encoding='utf-8')
    with pytest.raises(ValueError):
        Configuracion.cargar(archivo)


@pytest.mark.parametrize('comando', ['perfiles', 'validar'])
def test_cli_excel_corrupto_sin_traceback(tmp_path, comando):
    archivo = tmp_path / 'corrupto.xlsx'
    archivo.write_bytes(b'no es un zip')
    argumentos = (['perfiles', '--entrada', str(archivo), '--estimar'] if comando == 'perfiles' else
                  ['validar', '--modash', str(archivo), '--salida', 'fixtures/muestra-sintetica.xlsx'])
    respuesta = CliRunner().invoke(app, argumentos)
    assert respuesta.exit_code == 1
    assert 'Error:' in respuesta.output and 'Traceback' not in respuesta.output


def test_cli_yaml_corrupto_y_referencia_vacia(tmp_path):
    archivo = tmp_path / 'corrupto.yaml'
    archivo.write_text('marca: [sin cierre', encoding='utf-8')
    respuesta = CliRunner().invoke(app, ['perfiles', '--entrada', 'fixtures/muestra-sintetica.xlsx',
                                        '--brief', str(archivo), '--estimar'])
    assert respuesta.exit_code == 1
    assert 'Traceback' not in respuesta.output
    assert CliRunner().invoke(app, ['lista', '--referencia', '', '--estimar']).exit_code == 1


def test_fabrica_no_abre_clientes_con_configuracion_incompleta(monkeypatch):
    def prohibido(*args, **kwargs):
        pytest.fail('No debe abrir clientes antes de validar todas las llaves')
    monkeypatch.setattr('motor.proveedores.apify.ApifyInstagram', prohibido)
    from motor.fabrica import crear_motor
    configuracion = Configuracion(secretos={'APIFY_TOKEN': 'falso', 'GROQ_API_KEY': 'falso'})
    with pytest.raises(ValueError, match='TYPESAFE_API_KEY'):
        crear_motor(configuracion=configuracion)
