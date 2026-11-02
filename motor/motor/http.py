"""API para n8n; trabajos locales persistentes para una PoC de un proceso.

BackgroundTasks mantiene la petición breve, pero no es una cola distribuida.
Al reiniciar se marcan los trabajos pendientes como interrumpidos; no se
reintentan operaciones pagadas automáticamente. Ejecutar con un solo worker.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hmac import compare_digest
import json
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import UUID, uuid4
from zipfile import BadZipFile

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from openpyxl.utils.exceptions import InvalidFileException
from pydantic import Field, field_validator, model_validator

from motor.almacen import Almacen
from motor.configuracion import PASOS_TRANSCRIPCION, Configuracion, ruta_local
from motor.costos import estimar_costo
from motor.excel import exportar_excel, leer_usuarios
from motor.modelos import Opciones, ResultadoPerfil, normalizar_usuario
from motor.presentacion import presentar_perfil, registrar_resultado, resumir_corrida


class SolicitudLista(Opciones):
    """Una fuente de usuarios y las mismas opciones de procesamiento de la CLI."""
    referencia: str | None = None
    entrada: str | None = Field(default=None, min_length=1)
    usuarios: list[str] | None = None
    estimar: bool = False
    simulado: bool = False

    @field_validator('referencia')
    @classmethod
    def _normalizar_referencia(cls, valor):
        return normalizar_usuario(valor) if valor is not None else None

    @field_validator('usuarios')
    @classmethod
    def _normalizar_usuarios(cls, valores):
        if valores is None:
            return None
        if not valores:
            raise ValueError('La lista de usuarios no puede estar vacía')
        return list(dict.fromkeys(normalizar_usuario(valor) for valor in valores))

    @model_validator(mode='after')
    def _fuente_unica(self):
        if sum(valor is not None for valor in (self.referencia, self.entrada, self.usuarios)) != 1:
            raise ValueError('Indica exactamente una fuente: referencia, entrada o usuarios')
        if self.brief.followers_max is not None and self.brief.followers_max < self.brief.followers_min:
            raise ValueError('followers_max debe ser mayor o igual a followers_min')
        return self

    def opciones(self) -> Opciones:
        return Opciones.model_validate({nombre: getattr(self, nombre) for nombre in Opciones.model_fields})


def crear_app(configuracion: Configuracion | None = None, ejecutor=None,
              almacen: Almacen | None = None,
              validacion: str | Path = '.motor/validacion.json') -> FastAPI:
    """Crea la app; ejecutor(solicitud, id) permite pruebas sin servicios externos.

    El ejecutor devuelve ResultadoCorrida. Las estimaciones se resuelven antes
    de construir el motor y no necesitan credenciales de proveedores.
    """
    configuracion = configuracion or Configuracion.cargar()
    almacen = almacen or Almacen()
    ruta_validacion = ruta_local(validacion)
    progresos_vivos = {}
    bloqueo_progreso = Lock()

    def guardar(identificador: str, datos: dict) -> None:
        almacen.guardar_corrida('http:' + identificador, datos)

    def recuperar(identificador: str) -> dict:
        datos = almacen.obtener_corrida('http:' + identificador)
        if datos is None:
            raise HTTPException(404, 'Corrida no encontrada')
        return datos

    @asynccontextmanager
    async def ciclo_vida(_app):
        for datos in almacen.listar_corridas():
            if datos.get('estado') in {'pendiente', 'en_proceso'}:
                datos['estado'] = 'interrumpida'
                datos['nota'] = 'El proceso se reinició. Puede iniciar otra corrida y reutilizar la caché.'
                datos['finalizada'] = datetime.now(timezone.utc).isoformat()
                guardar(datos['id'], datos)
        yield

    app = FastAPI(title='Motor de Aventura', version='0.1.0', lifespan=ciclo_vida)

    def autenticar(authorization: str | None = Header(default=None)):
        try:
            esperado = configuracion.llave('MOTOR_HTTP_TOKEN')
        except ValueError:
            raise HTTPException(503, 'Configura MOTOR_HTTP_TOKEN en .env') from None
        esquema, _, token = (authorization or '').partition(' ')
        if esquema.lower() != 'bearer' or not compare_digest(token.encode(), esperado.encode()):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Token no válido',
                                headers={'WWW-Authenticate': 'Bearer'})

    def obtener_usuarios(solicitud: SolicitudLista) -> list[str] | None:
        if solicitud.entrada is not None:
            return leer_usuarios(ruta_local(solicitud.entrada))
        return solicitud.usuarios

    def ejecutar(solicitud: SolicitudLista, identificador: str):
        datos = recuperar(identificador)
        datos['estado'] = 'en_proceso'
        guardar(identificador, datos)
        ultima_escritura = monotonic()

        def al_avanzar(paso, hechos, total, descartados, **extra):
            nonlocal ultima_escritura
            datos['progreso'] = dict(paso=paso, hechos=hechos, total=total, descartados=descartados, **extra)
            with bloqueo_progreso:
                progresos_vivos[identificador] = datos['progreso'].copy()
            ahora = monotonic()
            # El estado más reciente queda en memoria; no se escribe cada perfil.
            if ahora - ultima_escritura >= 1:
                guardar(identificador, datos)
                ultima_escritura = ahora
        try:
            usuarios = obtener_usuarios(solicitud)
            if solicitud.estimar:
                cantidad = min(len(usuarios), solicitud.limite or len(usuarios)) if usuarios is not None else (solicitud.limite or 200)
                estimacion = estimar_costo(cantidad, solicitud.opciones(), referencia=solicitud.referencia is not None,
                                          proveedor_llm='jev' if solicitud.simulado else configuracion.proveedor_llm,
                                          paso_transcripcion='transcripcion' if solicitud.simulado else
                                          PASOS_TRANSCRIPCION.get(configuracion.proveedor_transcripcion, 'transcripcion'))
                estimacion['costo_total_usd'] = estimacion['costo_estimado_usd']
                datos.update(estado='estimada', estimacion=estimacion, costo_total_usd=0)
            else:
                if ejecutor is None:
                    from motor.fabrica import crear_motor
                    motor = crear_motor(simulado=solicitud.simulado, configuracion=configuracion, almacen=almacen)
                    try:
                        resultado = motor.ejecutar(usuarios, solicitud.opciones(), referencia=solicitud.referencia,
                                                  corrida_id=identificador, al_avanzar=al_avanzar)
                    finally:
                        motor.proveedores.cerrar()
                else:
                    resultado = ejecutor(solicitud, identificador)
                salida = ruta_local(Path('.motor/salidas') / f'{identificador}.xlsx')
                descartados = sum(perfil.descartado for perfil in resultado.perfiles)
                cantidad = len(resultado.perfiles)
                al_avanzar('excel', cantidad, cantidad, descartados, porcentaje=98, en_curso=0,
                           actividad='Preparando tu Excel')
                exportar_excel(resultado.perfiles, resultado.corrida, salida)
                al_avanzar('excel', cantidad, cantidad, descartados, porcentaje=100, en_curso=0,
                           actividad='Excel listo')
                registrar_resultado(almacen, resultado, salida, datos['fuente'], progreso=datos['progreso'])
                with bloqueo_progreso:
                    progresos_vivos.pop(identificador, None)
                return
        except Exception:
            # Las excepciones HTTP de proveedores pueden incluir URLs o tokens.
            # La respuesta persistida no copia su texto ni registra credenciales.
            datos.update(estado='error', nota='La corrida falló. Revise la configuración y los proveedores.')
        datos['finalizada'] = datetime.now(timezone.utc).isoformat()
        guardar(identificador, datos)
        with bloqueo_progreso:
            progresos_vivos.pop(identificador, None)

    @app.post('/listas', status_code=202, dependencies=[Depends(autenticar)])
    def crear_lista(solicitud: SolicitudLista, tareas: BackgroundTasks):
        if solicitud.entrada is not None:
            try:
                ruta = ruta_local(solicitud.entrada)
                if not ruta.is_file():
                    raise ValueError('La entrada no existe dentro de la carpeta del motor')
                # Detectar un formato inválido antes de aceptar un trabajo.
                if not leer_usuarios(ruta):
                    raise ValueError('La entrada no contiene usuarios')
            except (ValueError, OSError, BadZipFile, InvalidFileException):
                raise HTTPException(422, 'Entrada inválida: usa un TXT o XLSX dentro de la carpeta del motor') from None
        identificador = str(uuid4())
        guardar(identificador, dict(id=identificador, estado='pendiente', costo_total_usd=0,
                                   fuente='@' + solicitud.referencia if solicitud.referencia else solicitud.entrada or 'Usuarios pegados',
                                   marca=solicitud.brief.marca,
                                   fecha=datetime.now(timezone.utc).isoformat()))
        tareas.add_task(ejecutar, solicitud, identificador)
        return {'id': identificador, 'estado': 'pendiente'}

    @app.get('/listas/{identificador}', dependencies=[Depends(autenticar)])
    def estado_lista(identificador: UUID):
        identificador = str(identificador)
        datos = recuperar(identificador)
        llamadas = almacen.costos(identificador)
        costo = sum(llamada['costo_usd'] for llamada in llamadas) if llamadas else datos.get('costo_total_usd', 0)
        salida = {clave: valor for clave, valor in datos.items() if clave not in {'excel', 'resultados', 'fuente', 'marca'}}
        salida['costo_total_usd'] = costo
        with bloqueo_progreso:
            if identificador in progresos_vivos and datos['estado'] in {'pendiente', 'en_proceso'}:
                salida['progreso'] = progresos_vivos[identificador].copy()
        return salida

    @app.get('/listas', dependencies=[Depends(autenticar)])
    def historial():
        resumenes = []
        for datos in almacen.listar_corridas():
            resumen = resumir_corrida(datos)
            if datos['estado'] in {'pendiente', 'en_proceso', 'interrumpida', 'error'}:
                llamadas = almacen.costos(datos['id'])
                if llamadas:
                    resumen['costo_total_usd'] = sum(llamada['costo_usd'] for llamada in llamadas)
            resumenes.append(resumen)
        return resumenes

    @app.get('/listas/{identificador}/perfiles', dependencies=[Depends(autenticar)])
    def perfiles_lista(identificador: UUID):
        datos = recuperar(str(identificador))
        if 'resultados' not in datos:
            raise HTTPException(409, 'Los perfiles todavía no están disponibles para esta corrida')
        return [presentar_perfil(ResultadoPerfil.model_validate(perfil), numero)
                for numero, perfil in enumerate(datos['resultados'], 1)]

    @app.get('/validacion', dependencies=[Depends(autenticar)])
    def obtener_validacion():
        if not ruta_validacion.is_file():
            raise HTTPException(404, 'Aún no corremos la validación')
        from motor.validador import presentar_validacion
        try:
            resumen = json.loads(ruta_validacion.read_text(encoding='utf-8'))
            return presentar_validacion(resumen)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(422, 'El informe de validación no es válido; vuelve a ejecutar motor validar') from None

    @app.get('/listas/{identificador}/excel', dependencies=[Depends(autenticar)])
    def descargar_excel(identificador: UUID):
        datos = recuperar(str(identificador))
        if not datos.get('excel'):
            raise HTTPException(409, 'El Excel todavía no está disponible para esta corrida')
        ruta = ruta_local(datos['excel'])
        if not ruta.is_file():
            raise HTTPException(404, 'El archivo de esta corrida ya no está disponible')
        return FileResponse(ruta, filename=f'lista-{identificador}.xlsx',
                            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    return app
