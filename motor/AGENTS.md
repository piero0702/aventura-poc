# Motor de la PoC de Aventura (Praxia)

Lee `ENCARGO.md` completo antes de escribir código. Ahí está qué construir, el orden y cuándo está listo.

## Reglas
- Trabaja **solo dentro de esta carpeta**. No leas ni abras nada de las carpetas de arriba (`../`, `../../`): hay
  datos de un cliente bajo NDA. Para probar usa `fixtures/muestra-sintetica.xlsx` y fixtures JSON que tú escribas.
- **No hagas llamadas reales** a Apify, Groq ni TypeSafe: no tienes llaves. Todo se prueba con respuestas grabadas y
  `respx`. Sí puedes leer la documentación pública en la web para confirmar los esquemas de entrada y salida.
- **Nunca** login, cookies ni sesión de Instagram. Solo actores de Apify que no las piden.
- Las llaves solo se leen de `.env` (nunca se imprimen ni se guardan en logs). Deja `.env.example` con los nombres.
- Python 3.12 con `uv`. Código, comentarios, mensajes y README en español. Nombres de funciones y variables en español
  cuando sea natural (`perfiles`, `costo_usd`).
- Antes de terminar: `uv run pytest -q` en verde y `uv run motor --help` funcionando.
