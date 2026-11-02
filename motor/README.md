# Motor de la PoC de Aventura

Paquete Python 3.12 para partir de seguidos públicos o de una lista de usuarios, aplicar el filtro barato, transcribir reels, clasificar con Jev y exportar el Excel contractual. Incluye CLI, caché SQLite de 30 días, costos, validador A/B con línea base y la API HTTP que consume la web Radar. La PoC corre en local; n8n queda fuera de esta integración.

La implementación y las pruebas usan exclusivamente `fixtures/muestra-sintetica.xlsx` y respuestas JSON sintéticas en `fixtures/proveedores/`. No se hicieron llamadas reales a Apify, Groq, TypeSafe ni OpenRouter. La exactitud frente a los 102 perfiles y la latencia real aún deben medirse.

## Instalación y prueba sin llaves

Ejecutar desde esta carpeta; todas las rutas de la CLI y HTTP se restringen a ella, incluidos enlaces simbólicos. No se leen las carpetas superiores.

```bash
uv sync
uv run pytest -q
uv run motor --help
uv run motor perfiles --entrada fixtures/muestra-sintetica.xlsx --estimar
uv run motor perfiles --entrada fixtures/muestra-sintetica.xlsx --simulado --nombre "Muestra sintética" --salida .motor/demo.xlsx
uv run motor validar --modash fixtures/muestra-sintetica.xlsx --salida .motor/demo.xlsx --informe .motor/validacion-demo.md --json .motor/validacion.json
uv run motor lista --referencia @referencia.sintetica --limite 3 --simulado --salida .motor/lista-demo.xlsx
```

`--estimar` no construye proveedores ni necesita llaves. Estima todos los perfiles aptos, todos los reels adicionales, 180 segundos por audio y 30 000 tokens de entrada por perfil, sin descontar caché. Para los cinco perfiles sintéticos con opciones por defecto resulta **USD 0.2218**, USD 0.04436 por perfil. Es un escenario supuesto; el tamaño real del contexto cambia el costo. La simulación registra costos teóricos de sus respuestas y se marca como simulada: no acredita gasto real ni tiempo del servicio.

Las pruebas bloquean cualquier HTTP no grabado mediante `respx`. Cubren los cuatro proveedores, filtros, métricas, likes ocultos, caché/expiración, presupuesto, evidencia de marcas, asociación por usuario, Excel, validador, CLI y HTTP. Los temporales y la caché de uv se mantienen dentro de esta carpeta. Una advertencia de Starlette sobre su cliente de pruebas no afecta los resultados.

## Demo con la web

Se mantienen dos carpetas hermanas, `motor/` y `web/`, tanto en esta entrega como en la carpeta de trabajo de Praxia. Instala el motor con `uv sync` y las dependencias de la web con `npm install` desde `web/`. Configura `motor/.env` y `web/.env.local` como indica el [README de la web](../web/README.md); el token HTTP debe coincidir en ambos archivos. Desde `web/`, ejecuta:

```bash
npm run demo
```

El comando inicia el motor en `127.0.0.1:8000` con un solo worker y Vite en `127.0.0.1:5173`; Ctrl+C apaga ambos. `npm run dev` inicia solamente la web y espera que el motor ya esté encendido. La web usa `VITE_MOTOR_URL=http://127.0.0.1:8000` por defecto y exige `VITE_MOTOR_TOKEN`; no sustituye un token faltante por uno del mock.

Para mostrar datos sin costo, la web permite activar «Modo prueba (sin costo)» en Opciones avanzadas solo si `VITE_PERMITIR_SIMULADO=true`. Esa opción envía `simulado: true` a esta API. `MOTOR_SIMULADO_RETRASO_S` configura la pausa artificial por paso, por defecto `0`; no afecta ejecuciones reales. Las corridas simuladas se identifican como tales y su duración incluye esa pausa. Para la demo con proveedores reales se deja `VITE_PERMITIR_SIMULADO=false` y `MOTOR_SIMULADO_RETRASO_S=0`.

La prueba de navegador completa vive en `web/scripts/punta-a-punta.mjs`: arranca motor y web con configuración temporal de prueba, recorre la lista simulada, descarga el Excel, ejecuta la validación sintética y guarda capturas en `web/docs/capturas/real/`. Ver los comandos de ejecución en el README de la web. Los archivos `.env` de prueba no contienen credenciales de proveedores y se eliminan al terminar.

## Configuración de la ejecución real

Piero debe completar `.env` localmente, a partir de `.env.example`. Las credenciales se leen **solo de ese archivo**, sin interpolación de variables del sistema. No se imprimen, guardan en Excel ni registran en SQLite. No poner llaves en argumentos de comandos.

```bash
cp .env.example .env
```

Completar `APIFY_TOKEN`, `GROQ_API_KEY` y `TYPESAFE_API_KEY`. Para HTTP, completar además `MOTOR_HTTP_TOKEN` con un token fijo largo. El actor de perfiles se elige con `APIFY_ACTOR_PERFILES`: `apify/instagram-profile-scraper` o `figue/instagram-profile-scraper`. Solo se admiten los actores documentados que no requieren sesión. No se implementa login, cookies, sesión de Instagram ni API de Meta.

`LLM_PROVEEDOR=jev` usa `TYPESAFE_MODELO=jev-latest`. El respaldo se selecciona explícitamente con `LLM_PROVEEDOR=openrouter`, `OPENROUTER_API_KEY` y `OPENROUTER_MODELO`. Antes hay que completar las **dos** tarifas OpenRouter en `precios.yaml` y elegir un modelo compatible con JSON Schema. No hay segundo intento pagado automático.

`METRICAS_AGREGACION=promedio|mediana` selecciona la fórmula de likes, comentarios, reproducciones y engagements. El valor por defecto es `promedio`, para comparar con la fórmula de Modash; `mediana` conserva la alternativa anterior. Se valida al cargar la configuración, se aplica también a simulaciones y queda registrada como `metricas_agregacion` en los parámetros y en la hoja `Corrida` del Excel. Esta opción cambia el cálculo, sin volver a pagar los perfiles ya guardados en caché.

El brief usa las claves de `brief.example.yaml`: `marca`, `publico_objetivo`, `marcas_a_evitar`, `followers_min`, `followers_max`. Sin brief se clasifica, pero no se inventa un puntaje de encaje. La taxonomía inicial de categorías, ciudades y umbral de confianza se puede configurar al inyectar `JevClasificador` desde Python; todavía debe contrastarse con Carol.

Los siguientes comandos son para la corrida autorizada de Piero, después de cargar las llaves y revisar las tarifas; no se ejecutaron durante la construcción:

```bash
uv run motor lista --referencia @cuenta --brief brief.example.yaml --limite 200 --presupuesto-usd 12 --salida .motor/lista.xlsx
uv run motor perfiles --entrada usuarios.txt --reels 5 --muestra-seguidores 30 --presupuesto-usd 6 --salida .motor/perfiles.xlsx
```

Opciones comunes: `--limite`, `--reels` (5 por defecto, 0 desactiva la transcripción, máximo 10), `--muestra-seguidores` (30, 0 desactiva la muestra), `--presupuesto-usd`, `--estimar`, `--salida`, `--simulado`, `--nombre "Título de la lista"`. `--nombre` aparece como título en el historial si el brief no tiene marca. `lista` limita a 200 seguidos si no se indica límite; los seguidos públicos pueden ser parciales. La entrada TXT admite un usuario por línea y comentarios que empiezan con `#`; XLSX usa la columna exacta `@username`. Se normalizan mayúsculas y `@` y se eliminan duplicados. Las corridas de ambos comandos, incluidas las parciales, guardan sus perfiles en el mismo historial que HTTP; una lista grande corrida antes por CLI se puede abrir desde Mis listas.

## Tubería, datos y costos

1. Consulta seguidos si hay referencia; obtiene perfil y hasta 12 posts.
2. Descarta inexistentes, privadas, sin reels o fuera del rango de followers, con notas. Solo paga el perfil.
3. Selecciona los reels con más vistas, completando datos con el actor de reels si no hay suficientes aptos. Solo transcribe duración conocida mayor que cero y de hasta 180 segundos y audio de hasta 25 MB. Falta de duración/audio, exceso de tamaño o duración quedan anotados.
4. Obtiene una muestra de seguidores, acepta una página parcial y registra el número obtenido. El actor exige solicitar al menos 25 aunque se pida una muestra menor; recorta localmente.
5. Jev responde preguntas cerradas y el adaptador arma y valida el JSON con Pydantic. Clasifica categorías, relaciones comerciales, audiencia de contenido A, seguidores identificados por usuario y encaje. Publicidad, colab y canje llevan evidencia de un post; etiquetas y amigos/fotógrafos quedan separados en notas. Se rechazan usuarios o evidencias inventados.
6. Calcula las métricas en `motor/metricas.py`: toma últimos 12 por fecha y excluye posts con likes ocultos/ausentes/negativos. Likes, comentarios y vistas de reels usan **promedio por defecto**, o mediana según `METRICAS_AGREGACION`. Engagements agrega likes + comentarios de cada post con ambos datos; ER = Engagements / Followers como fracción. Sin denominador/datos queda vacío. No se reemplazan comentarios o vistas ausentes por cero.

Edad y género finales usan B si se obtuvo muestra, incluso si B no pudo inferir el dato; con muestra desactivada o vacía usan A. La ciudad procede de A. B agrega edad/género con dato de las cuentas que no fueron marcadas como `persona_real=false`; los empates quedan vacíos. `Quality Audience` = personas estimadas reales / usuarios únicos de la muestra. Los desconocidos no suman al numerador de calidad y su cantidad se anota. No son datos demográficos verificados ni una muestra aleatoria.

`Perfiles` conserva las 15 columnas exactas del fixture, seguidas de las 8 columnas de auditoría. Usa formatos del fixture (en esta muestra son `General`), ER y Quality Audience numéricos como fracción, edad `25-34`, género `Female`/`Male`. Las audiencias A/B se guardan como JSON. `Corrida` contiene fecha UTC, opciones, agregación de métricas, duración medida, estado y costos por paso. Los textos externos se escriben como texto para evitar fórmulas en Excel.

La caché guarda cada usuario/paso durante 30 días en `.motor/motor.sqlite`; claves incluyen proveedor, modelo y parámetros relevantes, brief y contenido de clasificación. La simulación usa identidades distintas y no contamina la caché real. Una segunda corrida idéntica desde caché cuesta cero. Para una medición fría, Piero puede configurar otro `Almacen` desde Python o mover el archivo SQLite local antes de correr; no se borra automáticamente.

Cada llamada reserva costo **antes** de enviarse, con precios de `precios.yaml`. Apify recibe además `maxTotalChargeUsd` por petición. Se ajusta el registro a unidades entregadas/segundos (mínimo 10 por audio)/tokens reportados. El total y la comparación del presupuesto usan `Decimal`. Si falta saldo se detiene toda la corrida, se exporta el resultado parcial con notas y la CLI devuelve código 2. Una llamada fallida conserva su reserva y marca `costos_confirmados=false`; hay que conciliarla manualmente. Si el proveedor reporta unidades superiores al tope, se registra ese costo y se detiene con `limite_proveedor_excedido`: no se oculta el exceso.

Los costos por fila suman los del usuario más la parte proporcional de la consulta inicial de seguidos; el costo global por perfil divide entre perfiles terminados (incluye los descartados). Los totales incluyen cualquier reserva sin confirmar y no acreditan la meta de costo real hasta conciliación. El registro por llamada guarda unidades, paso, usuario, costo y estado. Tablas SQL estándar, sin tipos ni funciones exclusivos de SQLite; para Postgres cambia el driver/marcadores de parámetros, manteniendo el esquema.

## Validación de los 102 perfiles

Piero debe copiar el Excel real a **esta carpeta** por su cuenta; el motor no busca ni abre archivos de carpetas superiores. Para mantener datos del cliente fuera del código, usar una subcarpeta local ignorada como `.motor/entradas/`.

```bash
uv run motor perfiles --entrada .motor/entradas/referencia-102.xlsx --estimar
uv run motor perfiles --entrada .motor/entradas/referencia-102.xlsx --presupuesto-usd 6.12 --salida .motor/salida-102.xlsx
uv run motor validar --modash .motor/entradas/referencia-102.xlsx --salida .motor/salida-102.xlsx
```

El último comando escribe `validacion.md` y, por defecto, `.motor/validacion.json`, que lee la pantalla Validación. `--json RUTA` permite elegir otro destino local; para que lo muestre la API por defecto hay que usar `.motor/validacion.json`. El JSON se reemplaza de forma atómica e incluye filas por perfil con valores Motor/Modash, coincidencia por campo, exclusiones, variantes A/B y líneas base.

El cruce usa usuarios normalizados. Followers y ER pasan cuando **≥80 % de los perfiles evaluables están dentro de ±10 % de Modash**; el informe incluye tanto esa proporción con su numerador/denominador como el error relativo medio. Edad/género A y B se miden **por separado** con meta ≥70 %; ciudad ≥80 %; costo por perfil ≤USD 0.06. La línea base usa siempre la etiqueta más común de Modash del mismo universo con dato. Empatar esa línea no demuestra aporte, aunque pase la meta.

La API presenta siete criterios: para edad y género elige B si la corrida obtuvo alguna muestra de seguidores, y A si no hubo muestra; el detalle conserva la otra variante y sus líneas base. Las filas usan la audiencia que corresponde a cada perfil según el Excel. Un criterio no evaluable conserva `resultado: null` cuando falta el valor, devuelve `pasa: false` y explica el motivo; un tiempo o costo simulado puede mostrar su valor medido sin acreditar la meta real.

Las predicciones ausentes cuentan como fallo cuando Modash tiene dato. Se excluyen privados, inexistentes y datos ausentes de Modash; se detallan usuarios y campos. Sin reels o fuera del rango del brief siguen en los denominadores y se listan aparte. Una corrida de 102 o de cinco perfiles no acredita la meta de **menos de 30 minutos para 200**; se necesita medir una corrida completa real de 200. Simulaciones y reservas pendientes tampoco acreditan costo real.

## API HTTP local

```bash
uv run uvicorn motor.http:crear_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Todas las rutas funcionales exigen `Authorization: Bearer <MOTOR_HTTP_TOKEN>`. El contrato completo está en [web/CONTRATO-API.md](../web/CONTRATO-API.md).

| Ruta | Resultado |
|---|---|
| `POST /listas` | HTTP 202 con `id`; ejecuta o estima en segundo plano. |
| `GET /listas/{id}` | Estado, costo y último `progreso` disponible; al terminar, metadatos de corrida. |
| `GET /listas` | Historial compartido de CLI y HTTP, más reciente primero. |
| `GET /listas/{id}/perfiles` | Perfiles del motor adaptados al contrato, o 409 hasta disponer del resultado. |
| `GET /listas/{id}/excel` | Descarga `.xlsx`, o 409 mientras no existe; 404 si el archivo fue retirado. |
| `GET /validacion` | Siete criterios y filas desde `.motor/validacion.json`; 404 si aún no existe. |

`Motor.ejecutar(..., al_avanzar=callback)` notifica `(paso, hechos, total, descartados)` en los pasos reales: `seguidos`, `perfiles`, `filtro`, `reels`, `transcripcion`, `seguidores`, `clasificacion`, `excel`. HTTP conserva el último progreso y limita sus escrituras a SQLite a aproximadamente una por segundo; pasos breves pueden transcurrir entre dos sondeos. Al terminar conserva el progreso final junto con el resultado. No inventa etapas que las opciones desactivaron.

Las salidas HTTP se escriben en `.motor/salidas/{id}.xlsx`. Los `ResultadoPerfil` completos se serializan en la instantánea de la corrida dentro de SQLite, en una sola transacción con los metadatos: así el historial no muestra una corrida terminada antes de disponer de sus perfiles ni depende de archivos JSON separados. Las conexiones SQLite se abren por operación y admiten los hilos de `BackgroundTasks`. La API convierte los estados internos de presupuesto/límite de proveedor en `parcial`; `completa_con_errores` se publica como `parcial` si hubo perfiles terminados, o `error` si no hubo ninguno. Los estados internos siguen en el Excel y en la salida de la CLI.

Los perfiles usan la misma audiencia que Excel, con `fuente`; las distribuciones se calculan solo si hubo muestra, excluyendo `persona_real=false` y valores desconocidos. Marcas comerciales y menciones van separadas; las fechas proceden del post de evidencia. Los datos ausentes permanecen en `null` y el encaje queda en `null` cuando no hubo brief.

Ejemplo de cuerpo, con exactamente una fuente entre `referencia`, `entrada` y `usuarios`:

```json
{
  "usuarios": ["cuenta.ficticia1", "cuenta.ficticia2"],
  "limite": 2,
  "reels": 5,
  "muestra_seguidores": 30,
  "presupuesto_usd": 0.12,
  "brief": {"marca": "Marca de ejemplo", "publico_objetivo": "Adultas de Lima"},
  "simulado": true
}
```

También admite `estimar: true`, sin proveedores. Es una cola local de PoC con BackgroundTasks y SQLite, **un proceso**; al reiniciar marca trabajos pendientes como `interrumpida` y no reintenta cobros. La caché conserva pasos completos. Para el MVP hace falta una cola durable con bloqueo entre workers y recuperación operativa. El costo durante una petición remota puede incluir una reserva provisional.

## APIs: lo confirmado y lo pendiente

Las fuentes y contratos exactos están en [docs/APIS.md](docs/APIS.md). Se confirmó la entrada `Account`, `dataToScrape: Followers/Followings`, `resultsLimit` del actor sin cookies; entradas de perfil y reels; Groq multipart; Jev `POST /v1/systemone`, Bearer, `state`/`questions`, Choice y uso de tokens; y el respaldo OpenRouter con JSON Schema. **Jev no es compatible con Chat Completions ni genera texto libre**: los motivos del encaje se construyen en código con sus decisiones. Su precio de USD 0.042/Mtokens de entrada y salida gratis se confirmó en documentación pública.

Supuestos de API y revisiones manuales pendientes, sin validación mediante llamadas pagadas:

- Los posts del perfil pueden omitir duración/audio y campos comerciales. Se enriquecen desde reels; si siguen ausentes se omite la transcripción. Los aliases y códigos de error tolerados de Apify son defensivos y deben contrastarse con respuestas reales, particularmente Figue. Un `Video` sin señal de reel no se trata automáticamente como reel.
- Las tarifas iniciales son las del encargo. Las fichas actuales de Apify muestran planes/precios diferentes: **conciliar precios y mínimos antes de pagar**. Verificar la aplicación real de `maxTotalChargeUsd` por los actores elegidos. No se garantizan tarifas futuras ni que un timeout haya cancelado el actor.
- No se confirmó un tokenizador local oficial Jev. Se reserva un token por byte UTF-8 del cuerpo más 4096 de margen y se valida conservadoramente 64k por petición/32k por pregunta; puede rechazarse una petición que sí cabría. El registro confirmado usa `usage.input_tokens`.
- La cantidad y calidad de la muestra dependen de lo que entregue Instagram; nombres/usuarios sin bio pueden producir datos desconocidos. Evaluar sesgo, exactitud y abstenciones con los 102.
- Los candidatos de marcas proceden de menciones, coautores, patrocinadores, nombres del brief y extracción heurística de frases comerciales en captions/transcripciones (por ejemplo, «en colaboración con Marca Brisa», marca sintética). Jev confirma la relación usando el post y su audio. La heurística puede omitir nombres ambiguos o sin esos indicios; revisar evidencia comercial a mano. Jev no propone nombres libres.
- OpenRouter depende del modelo configurado: verificar soporte de JSON Schema, tarifas de entrada/salida y límites antes de seleccionarlo. No se lo cotiza como Jev.

Queda pendiente la medición real de precisión, latencia y facturación; calibrar la taxonomía con Carol; revisar evidencia comercial y audiencia inferida; y endurecer la cola/concurrencia para producción. La tubería es secuencial y los timeouts de Apify pueden superar la meta temporal si se acumulan. No se afirma haber validado esos puntos con la muestra sintética.
