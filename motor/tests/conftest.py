"""Todas las pruebas bloquean HTTP no grabado; nunca requieren llaves reales."""
import pytest
from motor.configuracion import ruta_local


def pytest_configure():
    # pytest crea el basetemp, pero su carpeta padre debe existir en un clon limpio.
    ruta_local('.motor').mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def ventana_groq_limpia():
    # La ventana de solicitudes por minuto es del proceso: cada prueba empieza sin envíos previos.
    from motor.proveedores.groq import GroqAudio
    GroqAudio._enviadas.clear()


@pytest.fixture(autouse=True)
def bloquear_red(respx_mock):
    yield respx_mock
