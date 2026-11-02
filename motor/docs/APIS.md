# Contratos de proveedores revisados

Revisión: 27 de octubre de 2026. Se consultó documentación pública; no se ejecutó ningún actor ni se llamó a una API de inferencia. Los JSON de `fixtures/proveedores` son respuestas sintéticas con la forma documentada.

## Apify

[Actor de relaciones: ficha y entrada](https://apify.com/scraping_solutions/instagram-scraper-followers-following-no-cookies).
La entrada confirmada es `Account: [usuario]`, `dataToScrape: "Followers"` o `"Followings"`, y `resultsLimit`. El mínimo publicado es 25. Para solicitudes menores se obtienen hasta 25 y se recorta la muestra local; hay que presupuestar esos 25 resultados. Cada fila lleva `username`, `full_name`, `is_private` e `is_verified`. Una cuenta verificada o comercial puede entregar solamente la primera página. La muestra no es aleatoria ni representa necesariamente toda la audiencia.

[Perfil oficial: entrada](https://apify.com/apify/instagram-profile-scraper/input-schema).
Se confirma `usernames: [usuario]` y la ficha anuncia posts recientes. El adaptador conserva como máximo 12 posts y normaliza los campos habituales de Apify (`followersCount`, `biography`, `businessCategoryName`, `private`, `verified`, `latestPosts`). No solicita extras de pago.

[Alternativa Figue](https://apify.com/figue/instagram-profile-scraper).
Su contrato difiere: `profiles: [usuario]`, `includeRecentPosts: true`. Devuelve aliases como `full_name`, `is_private`, `category_name`, `video_url`, `video_view_count` y `coauthor_producers`. La ficha anuncia mantenimiento y respuestas parciales: verificar disponibilidad antes de usarla.

[Reels: entrada](https://apify.com/apify/instagram-reel-scraper/input-schema) y [ejemplo de salida](https://apify.com/apify/instagram-reel-scraper).
La entrada confirmada es `username: [usuario]`, `resultsLimit`; `includeTranscript` e `includeDownloadedVideo` quedan en falso porque son extras. El ejemplo publica `audioUrl`, `videoUrl`, `videoDuration`, `productType: "clips"`, `videoViewCount`, `videoPlayCount`, `mentions`, `coauthorProducers`, `sponsors` y `paidPartnership`. Un contador de likes `-1` se interpreta como oculto. Se usa el audio público, o el MP4 si no hay pista separada (Groq admite MP4).

[API de ejecución síncrona](https://docs.apify.com/api/v2/actor-run-sync-get-dataset-items-post).
Se usa `POST /v2/acts/{propietario}~{actor}/run-sync-get-dataset-items`, autenticación Bearer y JSON. La API admite `maxTotalChargeUsd`; la tubería lo fija al importe reservado para cada llamada. La documentación general lo describe para todos los modelos de precios; la aplicación de mínimos por un actor de terceros debe verificarse antes de pagar. No se reintentan automáticamente ejecuciones pagadas, porque un timeout podría dejar un actor cobrándose. La variante síncrona tiene un límite de 300 segundos; un timeout exige revisar el run manualmente antes de reintentar.

**Supuestos pendientes de contrastar en una corrida autorizada:** duración, pista de audio y campos comerciales pueden faltar dentro de `latestPosts` del actor de perfiles, aunque aparecen en los ejemplos de reels; sin duración conocida el motor no transcribe. El mapeo tolerante de aliases no garantiza que un actor arbitrario configurable sea compatible. El precio de `precios.yaml` es el del encargo; las fichas actuales muestran tarifas y planes diferentes, que se deben reconciliar antes de pagar.

## Groq

[Speech to text](https://console.groq.com/docs/speech-to-text) y [referencia](https://console.groq.com/docs/api-reference).
Se confirma `POST https://api.groq.com/openai/v1/audio/transcriptions`, Bearer, multipart `file`, modelo `whisper-large-v3-turbo` y respuesta JSON con `text`. Admite MP4 y audio; cobra al menos 10 segundos, a USD 0.04 por hora según la ficha. Se aplica el máximo de 25 MB y 180 segundos del encargo incluso cuando el plan de Groq permita archivos mayores.

## Jev de TypeSafe

[Introducción](https://docs.typesafe.ai/introduction), [HTTP](https://docs.typesafe.ai/api/system-one), [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score) , [estado](https://docs.typesafe.ai/concepts/state) y [modelos y límites](https://docs.typesafe.ai/models).
La API confirmada es `POST https://api.typesafe.ai/v1/systemone`, autenticación `Authorization: Bearer`, con `model: "jev-latest"`, `state` y `questions`. El campo `state` admite cadena, objeto JSON o array; el motor envía un objeto. Devuelve `answers` por el nombre de cada pregunta: cada Choice incluye `choice`, `confidence` y `probabilities`, más `usage.input_tokens`/`output_tokens`. No existe un límite separado al número de preguntas: deben caber `state` más todas las preguntas en 64k tokens y `state` más cada pregunta en 32k. No se habilita long context automáticamente. La misma página confirma USD 0.042 por millón de tokens de entrada y salida gratis.

Jev no es una API de Chat Completions compatible con OpenAI y no genera texto libre. Este motor le plantea decisiones cerradas `choice` y construye el JSON final con Pydantic: categoría, edad/género/ciudad, encaje, relación comercial y seguidores identificados por usuario. Los motivos son frases construidas en código a partir de esas decisiones. Las evidencias de marcas son URLs de posts reales del estado, nunca URLs inventadas por el modelo.

**Supuestos y límites de producto:** la taxonomía inicial de Carol es configurable y provisional; las ciudades se seleccionan de un vocabulario configurable. Los candidatos de marcas salen de menciones/coautores/patrocinadores, nombres del brief y heurísticas de frases comerciales en captions y transcripciones: una marca sin estos indicios puede quedar fuera. Jev confirma o descarta la relación; la extracción local no acredita patrocinio. Los datos escasos de seguidores pueden producir `null` (desconocido), y "persona real" es una estimación, no una verificación. La utilidad de clasificar edades a partir de estos datos y el umbral de abstención requieren validación con los 102 perfiles. No se confirmó un tokenizador local oficial: la reserva usa un token por byte UTF-8 del cuerpo exacto más 4096 de margen; el registro posterior conserva `usage.input_tokens`.

## OpenRouter de respaldo

[Referencia HTTP](https://openrouter.ai/docs/api-reference/overview) y [salidas estructuradas](https://openrouter.ai/docs/guides/features/structured-outputs).
Se usa `POST https://openrouter.ai/api/v1/chat/completions` con Bearer, `messages`, `model`, `response_format.type=json_schema` y validación Pydantic local. El modelo es obligatorio en la configuración. El respaldo debe activarse explícitamente: no se hace una segunda llamada pagada automáticamente. Antes de habilitarlo hay que cargar en precios los tokens de entrada y salida del modelo elegido y comprobar que admita JSON Schema. No se asume que cueste lo mismo que Jev.

El adaptador Jev comprueba esos límites antes de reservar o llamar usando la cota conservadora por bytes. Puede rechazar una petición que sí cabría en el tokenizador real; en ese caso reduzca la muestra o los textos y revise la corrida. Las variantes toleradas de errores y aliases de Apify son un supuesto defensivo hasta contrastar sus respuestas pagadas.
