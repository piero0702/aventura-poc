"""Lectura de usuarios y exportación del formato de trabajo de Aventura."""
from __future__ import annotations

import json
import re
import unicodedata
from copy import copy
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from motor.modelos import Corrida, ResultadoPerfil, normalizar_usuario

COLUMNAS_BASE = [
    '#', '@username', 'Nombre / Marca', 'Descripción', 'Categoría', 'Followers',
    'Quality Audience', 'ER', 'Aud. Age', 'Aud. Gender', 'Audience City',
    'Engagements', 'Avg. Likes', 'Avg. Comments', 'Avg. Reel Plays',
]
COLUMNAS_EXTRA = [
    'Marcas con las que trabajó', 'Encaje (1-5)', 'Motivo del encaje',
    'Audiencia A (contenido)', 'Audiencia B (seguidores)',
    'Seguidores en la muestra', 'Notas', 'Costo USD',
]
COLUMNAS = COLUMNAS_BASE + COLUMNAS_EXTRA
PLANTILLA = Path('fixtures/muestra-sintetica.xlsx')


def leer_usuarios(ruta: str | Path) -> list[str]:
    """Lee TXT o la columna exacta @username de un XLSX y elimina duplicados."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == '.xlsx':
        libro = load_workbook(ruta, read_only=True, data_only=True)
        try:
            hoja = libro['Perfiles'] if 'Perfiles' in libro.sheetnames else libro.active
            filas = hoja.iter_rows(values_only=True)
            cabecera = next(filas, ())
            if '@username' not in cabecera:
                raise ValueError('El Excel debe tener la columna @username')
            indice = cabecera.index('@username')
            valores = [fila[indice] for fila in filas if len(fila) > indice]
        finally:
            libro.close()
    elif ruta.suffix.lower() == '.txt':
        valores = ruta.read_text(encoding='utf-8-sig').splitlines()
        valores = [valor for valor in valores if not valor.lstrip().startswith('#')]
    else:
        raise ValueError('La entrada debe ser un archivo .txt o .xlsx')
    return list(dict.fromkeys(normalizar_usuario(str(valor)) for valor in valores if valor is not None and str(valor).strip()))


def _json(valor: object) -> str:
    if hasattr(valor, 'model_dump'):
        valor = valor.model_dump(mode='json')
    return json.dumps(valor, ensure_ascii=False, sort_keys=True)


def _fila(resultado: ResultadoPerfil, numero: int) -> list:
    perfil = resultado.perfil
    clasificacion = resultado.clasificacion
    audiencia_a = clasificacion.audiencia_a if clasificacion else None
    audiencia, _ = resultado.audiencia_final()
    marcas = []
    if clasificacion:
        marcas = [
            marca.model_dump(mode='json') for marca in clasificacion.marcas
            if marca.tipo in {'publicidad', 'colab', 'canje'}
        ]
    notas = list(resultado.notas)
    if resultado.descartado and not notas:
        notas.append('Perfil descartado')
    if clasificacion:
        menciones = [marca for marca in clasificacion.marcas if marca.tipo in {'etiqueta', 'amigo_fotografo'}]
        if menciones:
            notas.append('Menciones sin colaboración acreditada: ' + _json([marca.model_dump() for marca in menciones]))
    metricas = resultado.metricas
    return [
        numero, '@' + perfil.usuario, perfil.nombre, (clasificacion.descripcion if clasificacion else '') or perfil.bio,
        clasificacion.categoria if clasificacion else perfil.categoria,
        perfil.followers if resultado.perfil_obtenido and perfil.existe else None, resultado.calidad_audiencia,
        metricas.er, audiencia.edad if audiencia else None,
        audiencia.genero if audiencia and audiencia.genero in {'Female', 'Male'} else None,
        # La muestra permite estimar edad/género; la ciudad procede del contenido.
        audiencia_a.ciudad if audiencia_a else None,
        metricas.engagements, metricas.likes, metricas.comentarios, metricas.reel_plays,
        _json(marcas) if marcas else None,
        clasificacion.encaje if clasificacion else None,
        clasificacion.motivo_encaje if clasificacion else None,
        _json(audiencia_a) if audiencia_a else None,
        _json(resultado.audiencia_b) if resultado.audiencia_b else None,
        resultado.seguidores_muestra, '; '.join(notas), resultado.costo_usd,
    ]


def limpiar_nombre(nombre: str | None) -> str | None:
    """Como lo escribe la agencia: sin emojis ni adornos, y sin todo en mayúsculas o minúsculas."""
    # «Maca | nutrición real»: lo que va tras un separador es lema, no nombre.
    # Instagram trae tildes como caracteres combinados («e» + «´») y rellenos invisibles (ㅤ, ⠀).
    texto = unicodedata.normalize('NFC', nombre or '')
    texto = re.sub('[\u115f\u1160\u3164\uffa0\u2800\u200b-\u200f\u2060\ufeff]', ' ', texto)
    texto = re.split(r'\s[|•·]\s', texto)[0]
    texto = re.sub(r"[^\w\s.,'&/()-]", ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip(' -|/,')
    letras = [c for c in texto if c.isalpha()]
    if letras and (all(c.isupper() for c in letras) or all(c.islower() for c in letras)):
        texto = texto.title()
    return texto or None


def _entero(valor: float | None) -> int | None:
    return None if valor is None else int(round(valor))


def _fila_cliente(resultado: ResultadoPerfil, numero: int) -> list:
    """Las 15 columnas del Excel de trabajo de Aventura, con sus mismos tipos de dato."""
    perfil = resultado.perfil
    clasificacion = resultado.clasificacion
    audiencia_a = clasificacion.audiencia_a if clasificacion else None
    audiencia, _ = resultado.audiencia_final()
    metricas = resultado.metricas
    return [
        numero, '@' + perfil.usuario, limpiar_nombre(perfil.nombre),
        (clasificacion.descripcion if clasificacion else '') or None,
        (clasificacion.categoria if clasificacion else '') or None,
        # Quality Audience vacía como en el Excel de la agencia: con 30 seguidores sale 80-93 % para casi
        # todos y no distingue perfiles. La calidad sigue en la auditoría y en la web.
        perfil.followers if resultado.perfil_obtenido and perfil.existe else None, None,
        None if metricas.er is None else round(metricas.er, 4), audiencia.edad if audiencia else None,
        audiencia.genero if audiencia and audiencia.genero in {'Female', 'Male'} else None,
        # «Otra» (una ciudad fuera de la lista) no es un valor que la agencia use.
        audiencia_a.ciudad if audiencia_a and audiencia_a.ciudad != 'Otra' else None,
        _entero(metricas.engagements), _entero(metricas.likes), _entero(metricas.comentarios),
        _entero(metricas.reel_plays),
    ]


def _escribir_fila(hoja, valores: list) -> None:
    hoja.append(valores)
    # Captions, bios o nombres pueden empezar con '=': siempre son texto.
    for celda, valor in zip(hoja[hoja.max_row], valores):
        if isinstance(valor, str):
            celda.data_type = 's'


def ruta_auditoria(salida: str | Path) -> Path:
    salida = Path(salida)
    return salida.with_name(salida.stem + '.auditoria.xlsx')


def exportar_excel(
    resultados: list[ResultadoPerfil], corrida: Corrida, salida: str | Path,
    plantilla: str | Path = PLANTILLA,
) -> Path:
    """El Excel que recibe la agencia, idéntico al suyo: hoja Perfiles con sus 15 columnas y Notas vacía.

    Al lado deja el de auditoría (marcas, encaje, audiencias A/B, costos), que es el que lee el validador.
    """
    exportar_auditoria(resultados, corrida, ruta_auditoria(salida), plantilla)
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Perfiles'
    _escribir_fila(hoja, COLUMNAS_BASE)
    arial = Font(name='Arial', size=10)
    resaltado = PatternFill('solid', fgColor='FFF2CC')
    for numero, resultado in enumerate(resultados, 1):
        _escribir_fila(hoja, _fila_cliente(resultado, numero))
        for celda in hoja[hoja.max_row]:
            celda.font = arial
            if celda.column_letter in 'CD':
                celda.alignment = Alignment(wrap_text=True)
            if celda.column_letter in 'FGHI':
                celda.fill = resaltado
        hoja.cell(hoja.max_row, 8).number_format = '0.00%'
    for celda in hoja[1]:
        celda.font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='1F4E78')
        celda.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    hoja.row_dimensions[1].height = 30
    anchos = dict(zip('ABCDEFGHIJKLMNO', (5, 24, 26, 34, 20, 12, 16, 9, 10, 12, 14, 13, 11, 14, 15)))
    for columna, ancho in anchos.items():
        hoja.column_dimensions[columna].width = ancho
    hoja.freeze_panes = 'A2'
    libro.create_sheet('Notas')
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    libro.save(salida)
    libro.close()
    return salida


def exportar_auditoria(
    resultados: list[ResultadoPerfil], corrida: Corrida, salida: str | Path,
    plantilla: str | Path = PLANTILLA,
) -> Path:
    """Uso interno de Praxia: 15 columnas del fixture, 8 de auditoría y metadatos de corrida."""
    formatos = ['General'] * len(COLUMNAS_BASE)
    estilos = [None] * len(COLUMNAS_BASE)
    plantilla = Path(plantilla)
    if plantilla.exists():
        referencia = load_workbook(plantilla)
        try:
            hoja_ref = referencia['Perfiles']
            if [celda.value for celda in hoja_ref[1]][:15] != COLUMNAS_BASE:
                raise ValueError('Las columnas de la plantilla no coinciden con el formato de Aventura')
            for indice, celda in enumerate(hoja_ref[2][:15]):
                formatos[indice] = celda.number_format
                estilos[indice] = copy(celda._style)
        finally:
            referencia.close()
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Perfiles'
    _escribir_fila(hoja, COLUMNAS)
    for numero, resultado in enumerate(resultados, 1):
        _escribir_fila(hoja, _fila(resultado, numero))
        for indice, celda in enumerate(hoja[hoja.max_row][:15]):
            if estilos[indice] is not None:
                celda._style = copy(estilos[indice])
            celda.number_format = formatos[indice]
    hoja.freeze_panes = 'C2'
    hoja.auto_filter.ref = hoja.dimensions
    for celda in hoja[1]:
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='24445C')
        celda.alignment = Alignment(wrap_text=True, vertical='top')
        hoja.column_dimensions[celda.column_letter].width = 20
    for columna in ('D', 'P', 'R', 'S', 'T', 'V'):
        hoja.column_dimensions[columna].width = 45
    hoja.column_dimensions['A'].width = 6
    hoja.column_dimensions['W'].width = 15
    for fila in hoja.iter_rows(min_row=2):
        for celda in fila:
            celda.alignment = Alignment(vertical='top', wrap_text=True)
        fila[-1].number_format = '0.000000'

    metadatos = libro.create_sheet('Corrida')
    _escribir_fila(metadatos, ['Campo', 'Valor'])
    for clave, valor in corrida.model_dump(mode='json').items():
        _escribir_fila(metadatos, [clave, _json(valor) if isinstance(valor, (dict, list)) else valor])
    _escribir_fila(metadatos, ['metricas_agregacion', corrida.parametros.get('metricas_agregacion')])
    for paso, costo in sorted(corrida.costos_por_paso.items()):
        _escribir_fila(metadatos, ['costo_paso:' + paso, costo])
    metadatos.column_dimensions['A'].width = 30
    metadatos.column_dimensions['B'].width = 100
    metadatos.freeze_panes = 'A2'
    for celda in metadatos[1]:
        celda.font = Font(bold=True)
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    libro.save(salida)
    libro.close()
    return salida
