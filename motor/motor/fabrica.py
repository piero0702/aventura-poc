"""Construcción explícita de proveedores: simulados o configurados desde .env."""
from motor.almacen import Almacen
from motor.configuracion import Configuracion
from motor.costos import Precios
from motor.tuberia import Motor, Proveedores


def crear_motor(simulado: bool = False, configuracion: Configuracion | None = None,
                almacen: Almacen | None = None) -> Motor:
    configuracion = configuracion or Configuracion.cargar()
    if simulado:
        from motor.proveedores.falsos import InstagramFalso, AudioFalso, ClasificadorFalso
        proveedores = Proveedores(InstagramFalso(), AudioFalso(), ClasificadorFalso())
    else:
        from motor.proveedores.apify import ApifyInstagram
        from motor.proveedores.groq import AudioDesactivado, GroqAudio, WhisperLocalAudio
        from motor.proveedores.clasificacion import JevClasificador, OpenRouterClasificador
        # Validar toda la configuración antes de abrir clientes HTTP.
        token_apify = configuracion.llave('APIFY_TOKEN')
        if configuracion.proveedor_transcripcion not in {'groq', 'local', 'ninguno'}:
            raise ValueError('TRANSCRIPCION_PROVEEDOR debe ser groq, local o ninguno')
        clave_groq = configuracion.llave('GROQ_API_KEY') if configuracion.proveedor_transcripcion == 'groq' else ''
        if configuracion.proveedor_llm == 'jev':
            clave_llm = configuracion.llave('TYPESAFE_API_KEY')
        elif configuracion.proveedor_llm == 'openrouter':
            precios = Precios()
            precios.tarifa('openrouter_entrada_por_millon')
            precios.tarifa('openrouter_salida_por_millon')
            if not configuracion.modelo_openrouter:
                raise ValueError('Configura OPENROUTER_MODELO en .env')
            clave_llm = configuracion.llave('OPENROUTER_API_KEY')
        else:
            raise ValueError('LLM_PROVEEDOR debe ser jev u openrouter')
        abiertos = []
        try:
            instagram = ApifyInstagram(token_apify,
                actor_perfiles=configuracion.actor_perfiles,
                actor_relaciones=configuracion.actor_relaciones,
                actor_reels=configuracion.actor_reels)
            abiertos.append(instagram)
            audio = {'groq': lambda: GroqAudio(clave_groq, rpm=configuracion.groq_rpm),
                     'local': lambda: WhisperLocalAudio(configuracion.modelo_whisper_local),
                     'ninguno': AudioDesactivado}[configuracion.proveedor_transcripcion]()
            abiertos.append(audio)
            clasificador = (JevClasificador(clave_llm, modelo=configuracion.modelo_jev)
                if configuracion.proveedor_llm == 'jev' else
                OpenRouterClasificador(clave_llm, modelo=configuracion.modelo_openrouter))
            abiertos.append(clasificador)
        except Exception:
            for proveedor in abiertos:
                proveedor.close()
            raise
        proveedores = Proveedores(instagram, audio, clasificador)
    return Motor(proveedores, almacen=almacen, simulado=simulado,
                 metricas_agregacion=configuracion.metricas_agregacion,
                 simulado_retraso_s=configuracion.simulado_retraso_s,
                 paralelo=configuracion.paralelo)
