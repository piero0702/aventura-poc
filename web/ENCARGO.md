# Encargo: la web de la PoC

## Contexto
Aventura es una agencia de relaciones públicas en Lima. Hoy arma cada lista de influencers a mano en 2 a 3 horas:
capturas de los seguidos de una cuenta de referencia, pasarlas a Excel y luego a una plataforma de pago. Praxia
construyó un **motor** (API local en Python) que hace todo eso solo: desde una cuenta de referencia saca los perfiles,
filtra, transcribe reels, estima la audiencia con IA y entrega el Excel de 15 columnas que la agencia ya usa.

Esta web es la cara de ese motor para la **demo del jueves 29-oct** con la CEO, que no es técnica. Corre en local
(laptop), sin despliegue. Tiene que verse impecable y sentirse como un producto terminado, con la marca de Aventura.

Nombre de trabajo del producto: **Radar**. Ponlo en una sola constante (`src/config.ts`), junto con la firma
«Hecho por Praxia para Aventura PR», porque el nombre final se decide después.

## Qué construir (en este orden de prioridad)

### 1. Base
- Proyecto Vite + React + TS + Tailwind con los tokens de `DISENO.md` en `tailwind.config` (colores, radios,
  fuentes). Componentes base: `Boton` (primario/secundario/fantasma), `Campo`, `Chip`, `Tarjeta`, `Acuarela`,
  `Monograma`, `Etiqueta` (eyebrow), `CifraGrande`, `BadgeEstimado` (con tooltip), `Esqueleto`.
- Cliente de API tipado según `CONTRATO-API.md` (`src/api.ts`), con el token de `VITE_MOTOR_TOKEN` y manejo de
  errores en español.
- **Mock** (`npm run mock`): un servidor Node pequeño (sin dependencias pesadas; `node:http` o `express`) en el
  puerto 8000 que implementa **todas** las rutas del contrato con datos sintéticos coherentes:
  - una lista terminada de ~60 perfiles inventados (nombres y usuarios peruanos plausibles pero ficticios, categorías
    variadas: moda, gastronomía, viajes, belleza, fitness, lifestyle, música);
  - varias corridas en el historial (una con `error`, una `parcial`);
  - una corrida nueva que avanza sola por los pasos en ~40 s al hacer POST, para ver la pantalla de progreso;
  - la validación de 102 filas con criterios mixtos (algunos pasan y otros no);
  - un Excel de ejemplo para la descarga (puede ser un `.xlsx` mínimo generado al vuelo con `exceljs`, o un archivo
    fijo en `mock/`).
- Con `VITE_MOTOR_URL` (por defecto `http://127.0.0.1:8000`) el proxy de Vite apunta al motor real o al mock sin
  tocar código.

### 2. Pantalla «Nueva lista» (`/`)
- Encabezado con hero en acuarela: etiqueta «Radar» y titular en Gloock, por ejemplo «Tu lista de influencers, sin
  capturas ni copiar y pegar». Debajo, una línea que contraste el antes y el después: «Antes 2-3 horas · Ahora unos
  minutos».
- Formulario en una tarjeta: pestañas «Desde una cuenta de referencia» / «Pegar usuarios» (área de texto, uno por
  línea, admite `@` y URLs de perfil que tú normalizas a usuario).
- «Brief de la marca» plegable: marca, público objetivo, marcas a evitar (chips), rango de followers.
- «Opciones avanzadas» plegable: reels por perfil (0-10), seguidores en la muestra, límite, presupuesto.
- Botón secundario «Calcular costo» (POST con `estimar: true`, muestra el costo total, por perfil y por paso en un
  desglose simple) y primario «Armar lista».

### 3. Pantalla «En proceso» (`/listas/:id` mientras corre)
- Línea de pasos horizontal (seguidos → perfiles → filtro → reels → transcripción → audiencia → clasificación → Excel)
  con el paso actual animado; contador `hechos/total`, descartados, tiempo transcurrido y costo acumulado en
  `CifraGrande`.
- Si no llega `progreso`, avance indeterminado elegante y los mismos contadores que haya.
- Al terminar pasa sola a resultados. Si hay `error` o `interrumpida`, muestra la `nota` y un botón para reintentar.

### 4. Pantalla «Resultados» (`/listas/:id` terminada) — la más importante
- **Resumen arriba** en tarjetas: perfiles procesados, descartados, duración, costo total y por perfil. Una tarjeta en
  acuarela con el titular, por ejemplo «184 perfiles en 22 minutos» y el botón **«Descargar Excel»**.
- **Panel de filtros a la izquierda** (`DISENO.md` §2): buscar por nombre o usuario, followers mín-máx, ER mínimo,
  categoría (multiselección), género y edad mayoritarios de la audiencia, ciudad, encaje mínimo (1-5), «ocultar
  descartados», «excluir marcas a evitar». Contador de resultados y «Limpiar filtros». Todo filtra en el navegador.
- **Resultados en filas**: avatar de iniciales, nombre + `@usuario` (+ check si está verificada), categoría (chip),
  followers, ER, audiencia en una línea («25-34 · Mujeres · Lima» con `BadgeEstimado`), calidad de audiencia como
  barra mínima, encaje como 5 puntos llenos/vacíos, hasta 3 chips de marcas y la acción «Ver ficha». Orden por
  cualquier columna (por defecto, encaje y luego ER).
- Alternador **«Filas / Tabla»**: la tabla muestra exactamente las 15 columnas de Aventura (como su Excel), con
  encabezado fijo y desplazamiento horizontal.
- Los perfiles descartados se ven atenuados con su motivo (de `notas`).

### 5. Ficha del perfil (cajón lateral desde la derecha, con URL propia `/listas/:id/perfil/:usuario`)
- Cabecera: avatar, nombre, `@usuario` (enlace a instagram.com/usuario en pestaña nueva), categoría, bio.
- Métricas en 4-5 tarjetas: followers, ER, likes promedio, comentarios, reproducciones de reels.
- **Audiencia (estimada)**: barras de género con porcentaje y dona de edades con leyenda (`DISENO.md` §2). Si no hay
  distribución, muestra solo el valor mayoritario. Ciudad. Calidad de audiencia. Siempre visible: «Estimado por IA
  sobre una muestra de N seguidores».
- **Marcas con las que trabajó**: línea de tiempo horizontal con chips por fecha y tipo (publicidad, colab, canje),
  cada chip enlaza al post de evidencia. Debajo, «Menciones sin colaboración acreditada» en gris.
- **Encaje con el brief**: puntaje grande en Gloock y el motivo.
- Notas y costo del perfil en letra pequeña al final.

### 6. Pantalla «Validación» (`/validacion`)
- Titular «¿Funciona? La comparamos con la herramienta que usabas» y la fecha.
- Una tarjeta por criterio: nombre, meta, resultado grande y estado «Pasa» / «Todavía no» (en `turquesa` / `magenta`
  suave, nunca rojo alarmante), con su `detalle`.
- Veredicto arriba en acuarela: «Pasan X de 7 criterios».
- Tabla lado a lado (Motor | Referencia) por perfil, con un punto que indica si coincide; filtro «solo diferencias».
- Si la ruta da `404`, estado vacío amable: «Aún no corremos la validación».

### 7. Historial (`/listas`)
- Lista de corridas con fuente, fecha, estado (chip), perfiles, costo y duración; clic → resultados.

### Navegación y pie
Barra superior: monograma + «Radar», enlaces «Nueva lista», «Mis listas», «Validación». Pie con la firma de
`config.ts`.

## Cuándo está listo
- `npm run mock` y `npm run dev` levantan todo; las 6 pantallas funcionan contra el mock sin errores en consola.
- Funciona en 1440×900 y 1280×800 (la laptop de la demo) y se ve bien en 1024 px.
- Accesible: foco visible, navegación por teclado en filtros, tabla y cajón; contraste AA; `prefers-reduced-motion`
  respetado.
- `npm run build`, `npm run lint` y `npm test` en verde. Pruebas con Vitest + Testing Library para: normalización de
  usuarios pegados, filtros de resultados, formato de cifras (followers `48.2 k`, ER `3.88 %`, USD `0.048`), y el
  sondeo de estado (pendiente → en proceso → completa).
- README en español con: cómo correr contra el mock, cómo apuntar al motor real (`VITE_MOTOR_URL`,
  `VITE_MOTOR_TOKEN`) y capturas de las 6 pantallas en `docs/capturas/` (con Playwright contra el mock).

## Fuera de alcance
Login, usuarios, cupos, pagos, lista de espera, despliegue y cualquier cambio al motor.
