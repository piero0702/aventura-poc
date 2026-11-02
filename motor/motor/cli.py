"""Comandos del motor para operación local y validación de la PoC."""
from pathlib import Path
from typing import Annotated
import json
from uuid import uuid4
from zipfile import BadZipFile
from openpyxl.utils.exceptions import InvalidFileException
import yaml
import typer
from pydantic import ValidationError
from motor.configuracion import PASOS_TRANSCRIPCION, Configuracion, leer_brief, ruta_local
from motor.costos import estimar_costo
from motor.excel import leer_usuarios, exportar_excel
from motor.fabrica import crear_motor
from motor.modelos import Opciones, normalizar_usuario
from motor.proveedores.base import ProveedorError
from motor.presentacion import registrar_resultado
from motor.validador import validar as validar_archivos

app = typer.Typer(help='Motor de la PoC de Aventura: listas, perfiles y validación.',
                  no_args_is_help=True, pretty_exceptions_enable=False)


def _ejecutar(entrada, referencia, brief, limite, reels, muestra_seguidores, presupuesto_usd, estimar, salida, simulado, nombre='',
              reels_revisar=10):
    try:
        opciones = Opciones(limite=limite, reels=reels, reels_revisar=reels_revisar, muestra_seguidores=muestra_seguidores,
                           presupuesto_usd=presupuesto_usd, brief=leer_brief(brief))
        usuarios = leer_usuarios(ruta_local(entrada)) if entrada else None
        referencia = normalizar_usuario(referencia) if referencia is not None else None
        if usuarios is not None and not usuarios:
            raise ValueError('La entrada no contiene usuarios')
        ruta_salida = ruta_local(salida)
        if entrada and ruta_salida == ruta_local(entrada):
            raise ValueError('La salida debe ser diferente de la entrada')
        if estimar:
            cantidad = min(len(usuarios), limite) if usuarios is not None and limite else len(usuarios) if usuarios is not None else limite or 200
            configuracion = None if simulado else Configuracion.cargar()
            proveedor = configuracion.proveedor_llm if configuracion else 'jev'
            paso_audio = PASOS_TRANSCRIPCION.get(configuracion.proveedor_transcripcion, 'transcripcion') if configuracion else 'transcripcion'
            estimacion = estimar_costo(cantidad, opciones, referencia=bool(referencia), proveedor_llm=proveedor,
                                       paso_transcripcion=paso_audio)
            typer.echo('Costo estimado (USD); no se hizo ninguna llamada:')
            typer.echo(json.dumps(estimacion, indent=2, ensure_ascii=False))
            return
        motor = crear_motor(simulado=simulado)
        try:
            resultado = motor.ejecutar(usuarios, opciones, referencia=referencia)
            resultado.corrida.parametros['nombre'] = nombre
            if usuarios is not None:
                resultado.corrida.parametros['usuarios'] = usuarios
            exportar_excel(resultado.perfiles, resultado.corrida, ruta_salida, plantilla=ruta_local('fixtures/muestra-sintetica.xlsx'))
            registrar_resultado(motor.almacen, resultado, ruta_salida,
                                '@' + referencia if referencia else f'{len(usuarios)} usuarios', nombre=nombre)
        finally:
            motor.proveedores.cerrar()
        typer.echo(f'Excel: {ruta_salida}')
        typer.echo(json.dumps(resultado.corrida.model_dump(), indent=2, ensure_ascii=False))
        if resultado.corrida.estado != 'completa':
            raise typer.Exit(code=2)
    except (ValueError, OSError, KeyError, BadZipFile, InvalidFileException, yaml.YAMLError, ProveedorError) as exc:
        # No se imprimen excepciones de red ni contenido de la configuración.
        if isinstance(exc, ValidationError):
            mensaje = 'Parámetros o brief inválidos; revisa sus tipos y rangos'
        elif isinstance(exc, (OSError, BadZipFile, InvalidFileException, yaml.YAMLError)):
            mensaje = 'No se pudo leer o escribir un archivo local'
        else:
            mensaje = str(exc) if 'key' not in str(exc).lower() else 'Configuración inválida'
        typer.echo('Error: ' + mensaje, err=True)
        raise typer.Exit(code=1) from None


@app.command()
def perfiles(
    entrada: Annotated[Path, typer.Option(help='TXT o XLSX con columna @username.')],
    brief: Annotated[Path | None, typer.Option(help='Brief YAML.')] = None,
    limite: Annotated[int | None, typer.Option(min=1, help='Máximo de perfiles.')] = None,
    reels: Annotated[int, typer.Option(min=0, max=10, help='Reels de publicidad a transcribir por perfil (máximo 10).')] = 5,
    reels_revisar: Annotated[int, typer.Option(min=0, max=100, help='Reels recientes que se revisan para encontrar publicidad.')] = 10,
    muestra_seguidores: Annotated[int, typer.Option(min=0, help='0 desactiva la muestra.')] = 50,
    presupuesto_usd: Annotated[float | None, typer.Option(min=0, help='Tope de USD para la corrida.')] = None,
    estimar: Annotated[bool, typer.Option(help='Estima sin llamar a proveedores.')] = False,
    salida: Annotated[Path, typer.Option(help='Excel de salida.')] = Path('salida.xlsx'),
    simulado: Annotated[bool, typer.Option(help='Usa únicamente las respuestas sintéticas locales.')] = False,
    nombre: Annotated[str, typer.Option(help='Título de la lista en el historial cuando no hay marca en el brief.')] = '',
):
    """Procesa una lista de usuarios o el Excel de validación."""
    _ejecutar(entrada, None, brief, limite, reels, muestra_seguidores, presupuesto_usd, estimar, salida, simulado, nombre, reels_revisar)


@app.command()
def lista(
    referencia: Annotated[str, typer.Option(help='Cuenta de referencia, con o sin @.')],
    brief: Annotated[Path | None, typer.Option(help='Brief YAML.')] = None,
    limite: Annotated[int | None, typer.Option(min=1, help='Máximo de seguidos; por defecto 200.')] = None,
    reels: Annotated[int, typer.Option(min=0, max=10)] = 5,
    reels_revisar: Annotated[int, typer.Option(min=0, max=100)] = 10,
    muestra_seguidores: Annotated[int, typer.Option(min=0)] = 50,
    presupuesto_usd: Annotated[float | None, typer.Option(min=0)] = None,
    estimar: Annotated[bool, typer.Option(help='Estima sin consultar ni siquiera los seguidos.')] = False,
    salida: Annotated[Path, typer.Option()] = Path('salida.xlsx'),
    simulado: Annotated[bool, typer.Option(help='Usa únicamente las respuestas sintéticas locales.')] = False,
    nombre: Annotated[str, typer.Option(help='Título de la lista en el historial cuando no hay marca en el brief.')] = '',
):
    """Procesa los seguidos públicos de una cuenta de referencia."""
    _ejecutar(None, referencia, brief, limite, reels, muestra_seguidores, presupuesto_usd, estimar, salida, simulado, nombre, reels_revisar)


@app.command()
def validar(
    modash: Annotated[Path, typer.Option(help='Excel de referencia de Modash.')],
    salida: Annotated[Path, typer.Option(help='Excel producido por el motor.')],
    informe: Annotated[Path, typer.Option(help='Informe Markdown.')] = Path('validacion.md'),
    json_salida: Annotated[Path, typer.Option('--json', help='Informe estructurado para la pantalla Validación.')] = Path('.motor/validacion.json'),
):
    """Compara métricas y audiencias A/B con Modash e incluye la línea base."""
    try:
        referencia, producido, destino = ruta_local(modash), ruta_local(salida), ruta_local(informe)
        destino_json = ruta_local(json_salida)
        if destino in (referencia, producido) or destino_json in (referencia, producido, destino):
            raise ValueError('Los informes deben tener rutas distintas de los Excel y entre sí')
        resultado = validar_archivos(referencia, producido, destino)
        destino_json.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino_json.with_name(f'.{destino_json.name}.{uuid4().hex}.tmp')
        temporal.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
        temporal.replace(destino_json)
        typer.echo(f'Informe: {destino}; JSON: {destino_json}; perfiles en Modash: {resultado["perfiles_modash"]}')
    except (ValueError, OSError, KeyError, BadZipFile, InvalidFileException):
        typer.echo('Error: revisa las rutas, las columnas y los usuarios de los Excel', err=True)
        raise typer.Exit(code=1) from None
