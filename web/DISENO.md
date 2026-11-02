# Diseño: marca de Aventura con la estructura de una plataforma de influencers

Investigación del 27-oct-2026. La marca sale del Instagram de Aventura PR (rebranding de julio de 2026), con colores
medidos en píxel sobre sus posts. La estructura sale de cómo se ordenan las plataformas de búsqueda de influencers
(panel de filtros + filas de resultados + ficha con demografía). **Se toma la estructura, no el aspecto.**

La usuaria final es Carol, CEO de una agencia de relaciones públicas. No es técnica. La web tiene que verse como una
herramienta premium y tranquila, con la misma sensación editorial de sus posts: mucho papel, tinta negra y acuarela.

## 1. Marca de Aventura

### Identidad
- **Monograma:** una «a» minúscula en serif muy pesada con «pr» volado (superíndice) a su derecha. En el avatar va en
  tinta sobre un círculo lila. En los posts va pequeño en la esquina inferior derecha de cada tarjeta.
- Reprodúcelo tipográficamente: «a» en Gloock + «pr» en Gloock al ~45 % del tamaño, alineado arriba. No inventes otro
  logo.
- Lema: `#HistoriasQueConecten`. Descripción: «PR | Gestión de prensa | Influencer Mkt».

### Paleta (medida)
| Token | Hex | De dónde sale | Uso en la web |
|---|---|---|---|
| `papel` | `#FAF9F7` | Fondo de los posts del logo (`#FAFCF7` medido) | Fondo de la app |
| `papel-2` | `#F2F0EC` | Derivado | Fondos de paneles, filas al pasar el mouse |
| `tinta` | `#151515` | Monograma medido | Texto, botón primario |
| `tinta-60` | `rgba(21,21,21,.60)` | Derivado | Texto secundario |
| `tinta-12` | `rgba(21,21,21,.12)` | Derivado | Bordes y divisores |
| `lila` | `#D59FFF` | Círculo del monograma (medido) | Acento principal: selección, foco, chip activo |
| `turquesa` | `#3BDCE1` | Acuarela más frecuente en sus posts | Acuarela, estado «pasa» |
| `celeste` | `#48BBD8` | Acuarela | Acuarela, gráficos |
| `cobalto` | `#497CDD` | Acuarela (`#6A92E0` medido) | Enlaces, gráficos |
| `lima` | `#DFE270` | Acuarela (`#D4D86F` medido) | Acuarela, resaltado de cifras |
| `aguamarina` | `#69C9BB` | Acuarela | Acuarela |
| `magenta` | `#E85DB6` | Acento ocasional | Solo alertas suaves y «no pasa» (con moderación) |

Reglas de color:
- La base es **papel + tinta**. El color aparece solo como acuarela (fondos de tarjetas destacadas, hero) y en los
  gráficos. Nunca botones de colores saturados.
- En gráficos de categorías usa este orden: cobalto, turquesa, lila, lima, aguamarina, magenta.
- Contraste AA en todo el texto. Sobre acuarela, el texto siempre en tinta.

### La acuarela (lo que más identifica la marca)
Sus posts usan siempre la misma fórmula: una foto real y una **tarjeta de acuarela** (lavados de turquesa, celeste,
cobalto y lima, con grano de papel) con una etiqueta pequeña (el cliente) y un titular corto. Esquinas redondeadas
~12 px. Monograma abajo a la derecha.
- Hazla como textura real, no como degradado lineal: SVG con `feTurbulence` + `feDisplacementMap` sobre 3–4 manchas
  radiales de la paleta, más una capa de grano (`feTurbulence` fino, opacidad 6–10 %). Un componente
  `<Acuarela variante="mar|lila|lima" />` reutilizable.
- Úsala en: el hero de «Nueva lista», las tarjetas de resumen de una lista terminada, la tarjeta de veredicto de la
  validación y el estado vacío. **No** en tablas ni en filas.

### Tipografía
| Rol | Fuente | Detalle |
|---|---|---|
| Titulares grandes, cifras destacadas, monograma | **Gloock** (Google Fonts) | 400; titulares 48–72 px, cifras 32–56 px; tracking −1 % |
| Todo lo demás | **Instrument Sans** (Google Fonts) | 400/500/600; base 15–16 px; etiquetas 12–13 px en 500 |

Así escriben sus tarjetas: etiqueta pequeña en sans regular (el nombre del cliente seguido de «:») y debajo el titular grande en sans
regular con tracking apretado (−1.5 %), en minúsculas normales (nunca todo en mayúsculas). Replica ese par
«etiqueta + titular» en los encabezados de sección.

Cifras con `font-variant-numeric: tabular-nums` en tablas.

## 2. Estructura (patrones de plataformas de influencers)

Patrones medidos en la web de una plataforma de referencia del rubro (solo la maquetación):
- Contenedor de 1360 px máx., márgenes de 16–24 px, rejilla de 12 columnas.
- Botones en **píldora** (radio 999 px), alto 40 px, padding 8×16, borde 1.5 px. Primario: fondo tinta, texto papel.
  Secundario: transparente con borde tinta. Texto 15–16 px en 500.
- Tarjetas con radio 24 px, sin sombra o con sombra casi nula; el borde es `tinta-12` de 1 px.
- Texto secundario al 55–60 % de opacidad. Etiquetas («eyebrow») de 12 px en 500.
- **Búsqueda:** panel izquierdo fijo (~300 px) con la consulta arriba y los filtros apilados (rango de followers
  mín–máx en dos campos, ER mínimo, ubicación, colaboraciones con marcas, género), cada filtro con su etiqueta de
  12 px y un campo de radio 12 px. A la derecha, resultados en **filas**: avatar redondo, nombre + usuario, cifras
  clave en columnas cortas (followers, ER), logos o chips de marcas recientes y acciones a la derecha.
- **Ficha de demografía:** barras horizontales de género con porcentaje a la derecha; dona de rangos de edad con
  leyenda de puntos de color + porcentaje.
- **Colaboraciones con marcas:** chips/logos sobre una línea de tiempo horizontal, del más antiguo al más reciente.
- Navegación superior simple: marca a la izquierda, 3–4 enlaces de texto, una acción primaria en píldora a la
  derecha.

## 3. Tono de los textos
- Directo, cálido y corto. Habla de «listas» y «perfiles». Ejemplos: «Arma tu lista», «Pega la cuenta de
  referencia», «Listo: 184 perfiles en 22 minutos».
- Honesto con los datos inferidos: edad, género y ciudad de la audiencia son **estimaciones** hechas por IA sobre una
  muestra de seguidores. Siempre llevan la etiqueta «Estimado» y un tooltip que dice sobre cuántos seguidores se
  calculó. Nunca se presentan como dato oficial de Instagram.
- Nunca mencionar marcas reales en la interfaz ni en el mock.

## 4. Referencias visuales para el «se ve premium»
- Mucho aire: secciones separadas por 64–96 px; filas de 72–88 px de alto.
- Un solo acento por pantalla (la acuarela o el lila), no varios a la vez.
- Microinteracciones discretas: filas que se elevan 1 px al pasar el mouse, transición de 150 ms, foco visible lila.
- Estados vacíos y de carga cuidados (esqueletos con el papel-2, no spinners genéricos).
- Responsive: escritorio primero (la demo es en laptop), pero usable en tablet. En pantallas angostas el panel de
  filtros pasa a un cajón.
