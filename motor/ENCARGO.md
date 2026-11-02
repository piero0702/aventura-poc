# Encargo: motor de la PoC de Aventura

## Contexto
Aventura es una agencia de PR e influencer marketing en Lima. Hoy arma listas de influencers a mano en 4 pasos
(capturas → Excel → CSV → Modash), con 2 a 3 horas por lista. Praxia le va a entregar un motor que, desde una cuenta de
referencia, devuelve el **Excel de 15 columnas** que ya usa. La PoC se presenta el **jueves 29-oct** y se mide contra
**102 perfiles** que traen datos de Modash. Esa medición la corre Piero con el Excel real. Tú construyes el motor y
el validador, y los pruebas con la muestra sintética.

Stack decidido: **Apify** (datos de Instagram), **Groq** whisper-large-v3-turbo (transcripción de reels) y **Jev de
TypeSafe** (clasificación con LLM). Sin API de Meta. En el MVP lo va a orquestar n8n, así que el motor también se
expone por HTTP.

## Qué construir (en este orden)

### 1. Paquete `motor` con CLI
- `motor lista --referencia @cuenta [--brief brief.yaml]`: toma los **seguidos** de la cuenta de referencia y corre la
  tubería completa.
- `motor perfiles --entrada usuarios.txt|archivo.xlsx`: corre la tubería sobre una lista de usuarios. La validación
  usa este modo: lee la columna `@username` del Excel.
- Opciones comunes: `--limite N`, `--reels N` (por defecto 5, máximo 10), `--muestra-seguidores N` (por defecto 30,
  0 para apagarla), `--presupuesto-usd X` (corta antes de pasarse), `--estimar` (estima el costo sin llamar a nada),
  `--salida archivo.xlsx`.

### 2. Tubería (cada paso es un módulo con un proveedor intercambiable y uno falso para las pruebas)
1. **Seguidos de la cuenta de referencia:** actor `scraping_solutions/instagram-scraper-followers-following-no-cookies`
   en modo *following*. Confirma su esquema de entrada en la ficha del actor en apify.com.
2. **Perfil + últimos 12 posts:** `apify/instagram-profile-scraper`, con el ID del actor configurable (alternativa
   más barata: `figue/instagram-profile-scraper`). Trae followers, bio, categoría, privada, verificada y los posts con
   likes, comentarios, `videoViewCount`, caption, menciones y coautores.
3. **Filtro barato, antes de lo caro:** se descartan las privadas, las que no tienen reels y las que quedan fuera del
   rango de followers del brief. El motivo de cada descarte va a una columna de notas. A estos perfiles no se les
   transcribe nada.
4. **Reels:** los N con más vistas entre los posts que ya trae el perfil. Si no alcanzan, el actor
   `apify/instagram-reel-scraper`. Solo reels de hasta 3 min. Se baja el audio y se transcribe con **Groq**
   (`/openai/v1/audio/transcriptions`, modelo `whisper-large-v3-turbo`). Se salta lo que pase de 25 MB y se anota.
5. **Muestra de seguidores del creador (para la audiencia):** N seguidores con el mismo actor del paso 1, en modo
   *followers*. Instagram entrega una sola página (~25-50) en cuentas verificadas o comerciales; acéptalo y anota
   cuántos salieron.
6. **Jev (TypeSafe):** confirma en la documentación de typesafe.ai el endpoint, la autenticación y si es compatible
   con OpenAI. Deja OpenRouter como proveedor de respaldo, configurable. Salida en JSON validada con pydantic.
   - **Categoría** al estilo de Carol, a partir de la bio, los captions y las transcripciones. Ejemplos: «Salud &
     Nutrición», «Gastronomía», «Lifestyle».
   - **Marcas con las que trabajó:** separar publicidad, colab o canje de marcas que solo aparecen etiquetadas, y
     de amigos o fotógrafos. Por cada marca: tipo y post de evidencia.
   - **Audiencia, variante A (contenido):** edad, género y ciudad a quienes les habla, según bio, captions y
     transcripciones.
   - **Audiencia, variante B (muestra de seguidores):** por cada seguidor de la muestra, género, rango de edad y si
     es persona real. **Refiere a cada seguidor por su usuario, nunca por su posición en la lista** (con la posición
     se confunde con el siguiente). Se agregan en edad y género mayoritarios, y en % de personas reales.
   - **Encaje de 1 a 5** contra el brief (marca, público objetivo, marcas a evitar), con una línea de motivo.
7. **Métricas** (en un solo módulo, con su fórmula en el docstring):
   - Avg. Likes, Avg. Comments y Avg. Reel Plays con **mediana**, no promedio, sobre los últimos 12 posts. Se excluyen
     los posts con likes ocultos.
   - Engagements = mediana de likes + comentarios.
   - ER = Engagements / Followers.
8. **Caché** de 30 días por usuario y por paso, en SQLite con un esquema que se pueda pasar a Postgres sin cambios
   (SQL estándar, sin tipos propios de SQLite). Un perfil en caché no se vuelve a pagar.
9. **Registro de costos:** cada llamada guarda las unidades y los USD con los precios de `precios.yaml`. Valores
   iniciales:
   - Apify perfiles: USD 2.60 por 1,000.
   - Apify reels: USD 1.00 por 1,000.
   - Apify seguidores: USD 0.85 por 1,000.
   - Groq: USD 0.04 por hora de audio, con mínimo de 10 s por audio.
   - Jev: USD 0.042 por millón de tokens de entrada; la salida es gratis.

   Al final de cada corrida: costo total, costo por perfil y costo por paso. Si una corrida va a pasar
   `--presupuesto-usd`, se detiene antes.

### 3. Excel de salida
Hoja `Perfiles` con estas 15 columnas exactas, en este orden: `#`, `@username`, `Nombre / Marca`, `Descripción`,
`Categoría`, `Followers`, `Quality Audience`, `ER`, `Aud. Age`, `Aud. Gender`, `Audience City`, `Engagements`,
`Avg. Likes`, `Avg. Comments`, `Avg. Reel Plays`. El formato de cada columna sale de `fixtures/muestra-sintetica.xlsx`
(ER como fracción, edad como `25-34`, género `Female`/`Male`).
- `Quality Audience` = % de personas reales de la muestra de seguidores.
- Edad y género salen de la variante B si hay muestra y de la A si no la hay.
- Agrega estas columnas a la derecha: `Marcas con las que trabajó`, `Encaje (1-5)`, `Motivo del encaje`,
  `Audiencia A (contenido)`, `Audiencia B (seguidores)`, `Seguidores en la muestra`, `Notas`, `Costo USD`.
- Una segunda hoja, `Corrida`, con fecha, parámetros, duración y costos por paso.

### 4. Validador: `motor validar --modash referencia.xlsx --salida salida.xlsx`
Cruza por `@username` y escribe en `validacion.md` una tabla lista para pegar en el informe de la PoC:

| Criterio | Meta |
|---|---|
| Followers frente a Modash | ±10 % |
| ER frente a Modash | ±10 % |
| Edad mayoritaria igual a Modash | ≥ 70 % de los perfiles con dato |
| Género mayoritario igual a Modash | ≥ 70 % |
| Ciudad igual a Modash | ≥ 80 % |
| Tiempo de la corrida | < 30 min para 200 perfiles |
| Costo real por perfil | ≤ USD 0.06 |

- Edad y género se miden **por separado para la variante A y para la B**.
- Además del acierto, informa la **línea base**: qué acierto daría contestar siempre lo más común. Ejemplo: si el
  80 % de Modash es «Female», contestar siempre «Female» acierta el 80 %. Un modelo que no supera esa línea no sirve,
  aunque pase la meta.
- Lista los perfiles excluidos y por qué: no existen, privados, sin dato en Modash.

### 5. HTTP para n8n (solo si lo anterior está completo)
FastAPI: `POST /listas` (mismos parámetros que la CLI; responde un id), `GET /listas/{id}` (estado y costo) y
`GET /listas/{id}/excel`. Autenticación con un token fijo de `.env`.

## Cuándo está listo
- `uv run pytest -q` en verde. Las pruebas cubren: cada paso con respuestas grabadas, el filtro, las métricas con
  likes ocultos, la caché, el corte por presupuesto, el Excel (columnas exactas) y el validador con la muestra
  sintética (incluida la línea base).
- `uv run motor perfiles --entrada fixtures/muestra-sintetica.xlsx --estimar` imprime un costo estimado.
- `README.md` explica cómo poner las llaves en `.env`, cómo correr la validación real de los 102 y qué falta. También
  marca **cada supuesto sobre una API que no pudiste confirmar en su documentación**.
- Un `NOTAS-CODEX.md` corto con lo que decidiste, lo que quedó pendiente y lo que hay que revisar a mano.
