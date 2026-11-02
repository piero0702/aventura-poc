"""Instantáneas de corridas y adaptación fiel del resultado al contrato web."""
from collections import Counter
from datetime import datetime, timezone

from motor.excel import limpiar_nombre
from motor.almacen import Almacen
from motor.configuracion import ruta_local
from motor.modelos import ResultadoCorrida, ResultadoPerfil
from motor.proveedores.clasificacion import EDADES

PAISES = {'Santiago': 'Chile', 'Buenos Aires': 'Argentina', 'Bogotá': 'Colombia', 'Quito': 'Ecuador',
          'Ciudad de México': 'México', 'São Paulo': 'Brasil', 'Río de Janeiro': 'Brasil', 'Madrid': 'España',
          'Barcelona': 'España', 'Miami': 'Estados Unidos', 'Nueva York': 'Estados Unidos',
          'Los Ángeles': 'Estados Unidos', 'Otra': 'Otro'}


def _normalizar(valores: dict[str, float]) -> dict[str, float]:
    total = sum(valores.values())
    return {clave: valor / total for clave, valor in valores.items()} if total > 0 else {}


def estimacion_audiencia(probabilidades: dict[str, dict[str, float]]) -> dict | None:
    """Probabilidades de Jev listas para la ficha: no son % de seguidores, sino qué tan probable ve
    Jev cada opción como la mayoritaria. Cada rango de edad se parte en mujeres y hombres según el
    segmento (género + edad); si el segmento no dice nada de ese rango, según el género."""
    edad = _normalizar(probabilidades.get('edad', {}))
    genero = _normalizar({g: probabilidades.get('genero', {}).get(g, 0) for g in ('Female', 'Male')})
    ciudad = _normalizar(probabilidades.get('ciudad', {}))
    if not (edad or genero or ciudad):
        return None
    segmento = probabilidades.get('segmento', {})
    edad_genero = {}
    for rango in EDADES:
        partes = _normalizar({g: segmento.get(f'{g} {rango}', 0) for g in ('Female', 'Male')}) or genero
        edad_genero[rango] = {g: edad.get(rango, 0) * partes.get(g, 0.5) for g in ('Female', 'Male')}
    pais: dict[str, float] = {}
    for nombre, valor in ciudad.items():
        pais[PAISES.get(nombre, 'Perú')] = pais.get(PAISES.get(nombre, 'Perú'), 0) + valor
    orden = lambda d: dict(sorted(d.items(), key=lambda par: -par[1]))
    return {'genero': genero, 'edad': {rango: edad.get(rango, 0) for rango in EDADES} if edad else {},
            'edad_genero': edad_genero if edad else {}, 'ciudad': orden(ciudad), 'pais': orden(pais)}


def estado_publico(estado: str, procesados: int = 0) -> str:
    if estado in {'presupuesto_agotado', 'limite_proveedor_excedido'}:
        return 'parcial'
    if estado == 'completa_con_errores':
        return 'parcial' if procesados else 'error'
    return estado


def registrar_resultado(almacen: Almacen, resultado: ResultadoCorrida, salida,
                        fuente: str, nombre: str = '', progreso: dict | None = None) -> dict:
    """Guarda resultado íntegro y metadatos juntos en una transacción SQLite.

    Evita archivos JSON huérfanos o una corrida visible antes de sus perfiles.
    El prefijo histórico http: también identifica instantáneas creadas por CLI.
    """
    corrida = resultado.corrida.model_dump(mode='json')
    identificador = corrida['id']
    datos = almacen.obtener_corrida('http:' + identificador) or {}
    estado_motor = corrida['estado']
    corrida['estado'] = estado_publico(estado_motor, corrida['perfiles_procesados'])
    brief = corrida['parametros'].get('brief') or {}
    datos.update(id=identificador, estado=corrida['estado'], fecha=corrida['fecha'],
                 finalizada=datetime.now(timezone.utc).isoformat(), fuente=fuente,
                 marca=brief.get('marca') or nombre, corrida=corrida,
                 costo_total_usd=corrida['costo_total_usd'], excel=str(ruta_local(salida)),
                 resultados=[perfil.model_dump(mode='json') for perfil in resultado.perfiles])
    if corrida['estado'] != 'completa':
        motivo = {'presupuesto_agotado': 'Se alcanzó el presupuesto. Conservamos los resultados obtenidos.',
                  'limite_proveedor_excedido': 'El proveedor informó un costo mayor al reservado. La corrida se detuvo.',
                  'completa_con_errores': 'Uno o más perfiles no pudieron completarse por errores del proveedor.'}
        datos['nota'] = '; '.join([motivo.get(estado_motor, 'La corrida terminó con resultados incompletos.'),
                                  *corrida['notas']])
    if progreso is not None:
        datos['progreso'] = progreso
    almacen.guardar_corrida('http:' + identificador, datos)
    return datos


def presentar_perfil(resultado: ResultadoPerfil, numero: int) -> dict:
    perfil, clasificacion = resultado.perfil, resultado.clasificacion
    audiencia, fuentes = resultado.audiencia_final()
    datos_audiencia = {
        'edad': audiencia.edad if audiencia else None,
        'genero': audiencia.genero if audiencia else None,
        'ciudad': audiencia.ciudad if audiencia else None,
        'fuente': 'seguidores' if 'seguidores' in fuentes.values() else 'contenido',
        'fuentes': fuentes,
    }
    if resultado.seguidores_muestra and clasificacion:
        for campo in ('edad', 'genero'):
            conteos = Counter(getattr(seguidor, campo) for seguidor in clasificacion.seguidores
                              if seguidor.persona_real is not False
                              and getattr(seguidor, campo) not in (None, '', 'Unknown'))
            if conteos:
                total = sum(conteos.values())
                datos_audiencia['distribucion_' + campo] = {dato: cantidad / total for dato, cantidad in conteos.items()}
    if clasificacion and (estimacion := estimacion_audiencia(clasificacion.probabilidades)):
        datos_audiencia['estimacion'] = estimacion
    fechas = {post.url or post.id: post.fecha or None for post in perfil.posts}
    marcas, menciones = [], []
    for marca in clasificacion.marcas if clasificacion else []:
        dato = marca.model_dump(mode='json')
        if marca.tipo in {'publicidad', 'colab', 'canje'}:
            dato['fecha'] = fechas.get(marca.post_evidencia)
            marcas.append(dato)
        else:
            menciones.append(dato)
    return dict(numero=numero, usuario=perfil.usuario, nombre=limpiar_nombre(perfil.nombre),
                bio=perfil.bio or None, descripcion=(clasificacion.descripcion if clasificacion else '') or None,
                verificada=perfil.verificada,
                categoria=(clasificacion.categoria if clasificacion else perfil.categoria) or None,
                followers=perfil.followers if perfil.existe and resultado.perfil_obtenido else None,
                descartado=resultado.descartado,
                metricas=resultado.metricas.model_dump(mode='json'),
                calidad_audiencia=resultado.calidad_audiencia, audiencia=datos_audiencia,
                seguidores_muestra=resultado.seguidores_muestra, marcas=marcas, menciones=menciones,
                encaje=clasificacion.encaje if clasificacion else None,
                motivo_encaje=clasificacion.motivo_encaje if clasificacion else '',
                notas=resultado.notas, costo_usd=resultado.costo_usd)


def resumir_corrida(datos: dict) -> dict:
    corrida = datos.get('corrida') or {}
    return dict(id=datos['id'], estado=datos['estado'], fecha=datos.get('fecha'),
                finalizada=datos.get('finalizada'), fuente=datos.get('fuente', 'Usuarios pegados'),
                perfiles_procesados=corrida.get('perfiles_procesados'),
                costo_total_usd=datos.get('costo_total_usd', 0),
                duracion_segundos=corrida.get('duracion_segundos'), marca=datos.get('marca', ''))
