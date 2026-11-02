# Web de la PoC de Aventura (Praxia)

Lee completos, en este orden, antes de escribir código: `ENCARGO.md` (qué construir y cuándo está listo),
`DISENO.md` (marca y estructura visual) y `CONTRATO-API.md` (los datos que recibe la web).

## Reglas
- Trabaja **solo dentro de esta carpeta**. No leas ni abras nada de las carpetas de arriba (`../`, `../../`): hay
  datos de un cliente bajo NDA y llaves de servicios. En particular, **no abras `../motor/`**. Todo lo que necesitas
  del motor está en `CONTRATO-API.md`.
- Todos los datos de prueba son **sintéticos** y los escribes tú en `mock/`: usuarios, nombres y marcas inventados
  (nada de personas, influencers ni marcas reales). Nada de llaves ni tokens reales.
- No cargues imágenes de Instagram ni de ningún sitio externo. Los avatares son iniciales sobre un color de la paleta.
- No copies textos, logos, ilustraciones ni el nombre de ninguna otra plataforma. `DISENO.md` describe patrones de
  maquetación (paneles, filas, fichas); el aspecto es el de la marca de Aventura.
- Stack: Vite + React 18 + TypeScript estricto + Tailwind CSS 3. Gráficos en SVG propio (sin librerías de gráficos).
  Íconos: `lucide-react`. Fuentes desde Google Fonts. Nada más sin justificarlo en `NOTAS-CODEX.md`.
- Textos de la interfaz, código, comentarios y README en **español de Perú** (usted no: tuteo; «perfiles», no
  «creadores» cuando hable de la lista).
- Antes de terminar: `npm run build`, `npm run lint` y `npm test` en verde, y la app corriendo con `npm run dev`
  contra el mock (`npm run mock`).
- Al terminar, deja en `NOTAS-CODEX.md` qué hiciste, qué quedó pendiente y cualquier decisión que tomaste por tu
  cuenta.
