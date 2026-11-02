# Contrato de la API del motor (lo que consume la web)

El motor es una API FastAPI local en `http://127.0.0.1:8000`. La web la llama por `/api/*` (Vite hace de proxy y quita
el prefijo `/api`). Todas las rutas piden `Authorization: Bearer <token>`; la web lo lee de `VITE_MOTOR_TOKEN` en
`.env.local` (deja `.env.example` con el nombre, sin valor). En el mock, cualquier token no vacío vale. La web exige configurarlo; nunca agrega uno de reemplazo.

Todas las rutas están implementadas por el motor local. El mock conserva el mismo contrato solo para pruebas y capturas.

Montos en USD como número. Fechas ISO 8601 en UTC. Fracciones (ER, calidad de audiencia) entre 0 y 1.

## POST /listas
Lanza una corrida en segundo plano. Exactamente una fuente: `referencia` **o** `usuarios`.

```json
{
  "referencia": "cuenta.referencia",          // o null
  "usuarios": ["perfil.uno", "perfil.dos"],   // o null
  "limite": 200,                               // opcional; con referencia, máx. de seguidos a revisar
  "reels": 5,                                  // 0-10; reels de publicidad a transcribir (los más recientes); 0 = sin transcripción
  "reels_revisar": 10,                         // opcional (0-100); reels recientes que se revisan para encontrar la publicidad
  "muestra_seguidores": 50,                    // 0 = sin audiencia estimada por seguidores
  "presupuesto_usd": 12,                       // opcional; la corrida se detiene al llegar
  "estimar": false,                            // true = no corre, solo calcula el costo
  "simulado": false,
  "brief": {
    "marca": "Marca de ejemplo",
    "publico_objetivo": "mujeres 25-34 en Lima interesadas en moda sostenible",
    "marcas_a_evitar": ["Competidor A"],
    "followers_min": 10000,
    "followers_max": 200000
  }
}
```
Respuesta `202`: `{ "id": "uuid", "estado": "pendiente" }`. Errores `422` con `{ "detail": ... }`.

## GET /listas/{id}
```json
{
  "id": "uuid",
  "estado": "pendiente | en_proceso | completa | parcial | estimada | error | interrumpida",
  "fecha": "2026-10-28T15:00:00Z",
  "finalizada": "2026-10-28T15:22:10Z",        // ausente mientras corre
  "costo_total_usd": 4.12,
  "nota": "texto para el usuario",              // opcional
  "progreso": {                                  // opcional; si falta, la web muestra un avance indeterminado
    "paso": "seguidos | perfiles | filtro | reels | transcripcion | seguidores | clasificacion | excel",
    "hechos": 37,
    "total": 120,
    "descartados": 12
  },
  "estimacion": {                                // solo si estado = estimada
    "perfiles": 200, "costo_total_usd": 9.8, "costo_por_perfil_usd": 0.049,
    "costos_por_paso": { "perfiles": 0.52, "reels": 2.1, "transcripcion": 1.3, "seguidores": 3.4, "clasificacion": 2.48 }
  },
  "corrida": {                                   // presente al terminar
    "id": "uuid", "fecha": "...", "parametros": { },
    "duracion_segundos": 1320.5,
    "perfiles_solicitados": 200, "perfiles_procesados": 184,
    "costo_total_usd": 8.9, "costo_por_perfil_usd": 0.048,
    "costos_por_paso": { "perfiles": 0.5, "reels": 2.0 },
    "costos_confirmados": true, "ejecucion_simulada": false,
    "estado": "completa", "notas": ["..."]
  }
}
```
La web consulta esta ruta cada 3 s mientras el estado sea `pendiente` o `en_proceso`.

## GET /listas
Historial, la más reciente primero:
```json
[{ "id": "uuid", "estado": "completa", "fecha": "...", "finalizada": "...", "fuente": "@cuenta.referencia",
   "perfiles_procesados": 184, "costo_total_usd": 8.9, "duracion_segundos": 1320.5, "marca": "Marca de ejemplo" }]
```

## GET /listas/{id}/perfiles
Un objeto por perfil, en el orden de la lista. `409` si la corrida no terminó.
```json
[{
  "numero": 1,
  "usuario": "perfil.uno",
  "nombre": "Nombre Inventado",
  "bio": "texto",
  "descripcion": "Presentadora / lifestyle",          // corta, como la columna Descripción del Excel; null sin clasificación
  "verificada": false,
  "categoria": "Moda",
  "followers": 48200,
  "descartado": false,
  "metricas": { "likes": 1830, "comentarios": 41, "reel_plays": 22100, "engagements": 1871, "er": 0.0388 },
  "calidad_audiencia": 0.83,                       // personas reales estimadas / seguidores de la muestra
  "audiencia": {                                    // la que va al Excel (B si hubo muestra, si no A)
    "edad": "25-34", "genero": "Female", "ciudad": "Lima",
    "fuente": "seguidores | contenido",
    "distribucion_edad": { "18-24": 0.31, "25-34": 0.44, "35-44": 0.15, "45-54": 0.10 },  // puede faltar
    "distribucion_genero": { "Female": 0.68, "Male": 0.32 },                               // puede faltar
    "estimacion": {                                // probabilidades de Jev por contenido; puede faltar
      "genero": { "Female": 1.0 },
      "edad": { "13-17": 0, "18-24": 0.09, "25-34": 0.9, "35-44": 0.01, "45-54": 0, "55-64": 0, "65+": 0 },
      "edad_genero": { "25-34": { "Female": 0.82, "Male": 0.08 } },                         // los 7 rangos
      "ciudad": { "Lima": 0.98, "Ciudad de México": 0.01 },
      "pais": { "Perú": 0.98, "México": 0.01 }
    }
  },
  "seguidores_muestra": 30,
  "marcas": [
    { "nombre": "Marca Inventada", "tipo": "publicidad | colab | canje", "post_evidencia": "https://...", "fecha": "2026-09-14",
      "tamano": "grande | mediana | pequena | null" }
  ],
  "menciones": [ { "nombre": "Otra Marca", "tipo": "etiqueta | amigo_fotografo" } ],
  "encaje": 4,                                      // 1-5, null si no hubo brief
  "motivo_encaje": "texto corto",
  "notas": ["Sin reels con audio"],
  "costo_usd": 0.047
}]
```
Valores que pueden ser `null`: cualquier métrica, `calidad_audiencia`, campos de `audiencia`, `encaje`. La web
muestra «—» y nunca inventa un valor.

## GET /listas/{id}/excel
Devuelve el `.xlsx` igual al de Aventura: hoja `Perfiles` con sus 15 columnas y hoja `Notas` vacía. El de auditoría (15 + 8 columnas y hoja `Corrida`) queda al lado como `<id>.auditoria.xlsx` para el validador; no se descarga desde la web. La web solo ofrece el botón de descarga
(`fetch` con el token → `Blob` → descarga con nombre `lista-<fuente>-<fecha>.xlsx`).

Las 15 columnas de Aventura, en orden (la vista de tabla de la web usa estas mismas):
`#`, `@username`, `Nombre / Marca`, `Descripción`, `Categoría`, `Followers`, `Quality Audience`, `ER`, `Aud. Age`,
`Aud. Gender`, `Audience City`, `Engagements`, `Avg. Likes`, `Avg. Comments`, `Avg. Reel Plays`.

## GET /validacion
La comparación del motor contra la herramienta de referencia que Aventura usaba, sobre su lista de validación.
`404` si todavía no se corrió.
```json
{
  "fecha": "...",
  "perfiles": 102,
  "criterios": [
    { "id": "followers", "nombre": "Followers", "meta": "≥ 80 % dentro de ±10 %", "resultado": 0.97, "formato": "porcentaje", "pasa": true,
      "detalle": "99 de 102 dentro de ±10 %" },
    { "id": "er", "nombre": "ER", "meta": "≥ 80 % dentro de ±10 %", "resultado": 0.71, "formato": "porcentaje", "pasa": false, "detalle": "..." },
    { "id": "edad", "nombre": "Edad mayoritaria", "meta": "≥ 70 %", "resultado": 0.66, "formato": "porcentaje", "pasa": false, "detalle": "..." },
    { "id": "genero", "nombre": "Género mayoritario", "meta": "≥ 70 %", "resultado": 0.82, "formato": "porcentaje", "pasa": true, "detalle": "..." },
    { "id": "ciudad", "nombre": "Ciudad", "meta": "≥ 80 %", "resultado": 0.8, "formato": "porcentaje", "pasa": true, "detalle": "..." },
    { "id": "tiempo", "nombre": "Lista de 200 sin tocarla", "meta": "< 30 min", "resultado": 118, "formato": "minutos", "pasa": false, "detalle": "En serie; el MVP corre en paralelo" },
    { "id": "costo", "nombre": "Costo por perfil", "meta": "≤ USD 0.06", "resultado": 0.048, "formato": "usd", "pasa": true, "detalle": "..." }
  ],
  "filas": [{
    "usuario": "perfil.uno",
    "motor":      { "followers": 48200, "er": 0.0388, "edad": "25-34", "genero": "Female", "ciudad": "Lima" },
    "referencia": { "followers": 48900, "er": 0.0412, "edad": "25-34", "genero": "Female", "ciudad": "Lima" },
    "coincide":   { "followers": true, "er": true, "edad": true, "genero": true, "ciudad": true },
    "nota": ""
  }]
}
```
En la interfaz la referencia se llama **«Modash»**, configurable en `src/config.ts` como `PRODUCTO.referenciaValidacion`.

`resultado` puede ser `null` si falta el dato: la web muestra «—». Un criterio no evaluable tiene `pasa: false` y el motivo en `detalle`; una simulación no acredita costo ni latencia reales. Edad y género usan B si hubo muestra de seguidores y A en caso contrario, con la otra variante y su línea base en `detalle`. `filas` conserva los datos ausentes y las notas de exclusión.

El JSON se genera con `motor validar --modash referencia.xlsx --salida salida.xlsx --json .motor/validacion.json` desde la carpeta del motor. La ruta HTTP lee ese archivo; responde 404 si todavía no existe.


## Precisiones de integración

- `progreso` describe el paso real actual. La tubería procesa un perfil a la vez, así que vuelve por los pasos para el siguiente perfil. `hechos/total` es el avance de ese paso; en `seguidos` representa una consulta y en `excel`, una exportación. Los pasos desactivados o descartados no se inventan.
- `corrida.parametros` conserva las opciones efectivas y la fuente. Incluye `metricas_agregacion: "promedio" | "mediana"` y puede incluir `nombre` para las corridas CLI con `--nombre`. Sin brief, el encaje es `null`.
- Las corridas CLI `motor lista` y `motor perfiles` se registran con su Excel y perfiles en el mismo historial de las corridas HTTP.
- En historial, `perfiles_procesados` y `duracion_segundos` pueden ser `null` mientras no exista la corrida final. La web muestra «—»; el costo corresponde a las llamadas registradas hasta la consulta.
- `nombre`, `bio`, `categoria` y `marcas[].fecha` también pueden ser `null` cuando no hay dato. La fecha de una colaboración procede de su post de evidencia.
- `audiencia.estimacion` trae, normalizada sin «desconocido», la probabilidad que Jev da a cada opción de ser la mayoritaria (no es % de seguidores). `edad_genero` parte la probabilidad de cada rango entre mujeres y hombres según la pregunta de segmento (género + edad); `pais` suma las ciudades por país.
- `audiencia.distribucion_edad` y `distribucion_genero` se calculan desde seguidores con dato cuya clasificación no sea `persona_real=false`; sin muestra se omiten.
- La web habilita el envío de `simulado: true` solo cuando `VITE_PERMITIR_SIMULADO=true` y se activa el interruptor de Opciones avanzadas. El servidor mantiene el parámetro disponible para CLI y pruebas HTTP.
