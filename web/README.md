# Radar · Aventura PR

Web local de la PoC, conectada al motor Python: listas desde una cuenta de referencia o usuarios pegados, progreso medido, resultados, audiencia estimada, historial de CLI y HTTP, validación frente a Modash y descarga del Excel del motor. No hay despliegue ni n8n en esta PoC.

## Correr la demo local

Necesitas Python 3.12, `uv`, Node.js 22.12+, 24 o 26 y npm. Desde `motor/`, instala con `uv sync`. Desde esta carpeta:

```sh
npm ci --cache .npm-cache
cp .env.example .env.local
```

Completa `web/.env.local`:

```dotenv
VITE_MOTOR_URL=http://127.0.0.1:8000
VITE_MOTOR_TOKEN=el-mismo-token-local-del-motor
VITE_PERMITIR_SIMULADO=false
```

Praxia debe preparar `motor/.env` con `MOTOR_HTTP_TOKEN` y las credenciales descritas en el README del motor. El token HTTP es local, compartido con la web; la web nunca recibe las llaves de los proveedores. Luego, desde `web/`:

```sh
npm run demo
```

Abre [http://127.0.0.1:5173](http://127.0.0.1:5173). Este comando levanta `uv run uvicorn motor.http:crear_app --factory --host 127.0.0.1 --port 8000 --workers 1` desde la carpeta hermana `motor/` y Vite desde `web/`. Ctrl+C cierra ambos y sus procesos hijos. Las rutas se resuelven desde el script, así que funciona al mover la carpeta `desarrollo/` de Praxia y con espacios en su ruta. Los puertos 8000 y 5173 deben estar libres.

`npm run dev` también funciona por separado y apunta al motor real. No arranca el mock ni agrega un token de reemplazo. Si falta el token o el motor está apagado, la interfaz lo explica en español. Reinicia Vite después de cambiar el entorno.

La web llama a `/api/*`; Vite usa `VITE_MOTOR_URL` y quita `/api`. Todas las solicitudes, incluida la descarga, envían Bearer. El contrato está en [CONTRATO-API.md](CONTRATO-API.md).

## Probar sin costo

Para desarrollo sin proveedores, usa en `motor/.env` solamente:

```dotenv
MOTOR_HTTP_TOKEN=token-local
```

Configura `web/.env.local` con `VITE_MOTOR_TOKEN=token-local` y `VITE_PERMITIR_SIMULADO=true`. En **Nueva lista → Opciones avanzadas**, activa **Modo prueba (sin costo)**. Este interruptor está apagado al entrar y solo aparece con esa variable. Una cuenta de referencia sintética permite recorrer el motor completo sin llaves.

`MOTOR_SIMULADO_RETRASO_S` regula la pausa artificial del motor; por defecto es cero. Los resultados simulados se identifican como tales y muestran costo teórico y duración de esa simulación. La UI no promete una duración para una ejecución real. Con `METRICAS_AGREGACION=promedio` (valor predeterminado) o `mediana`, el motor registra el método en la corrida y el Excel.

El brief se envía únicamente si se completó alguno de sus campos. Los puntajes 1–5 y filtros de encaje aparecen solo para listas con brief. Los datos ausentes se muestran como «—»; las distribuciones de audiencia solo aparecen si el motor las entrega.

## Verificar contra el motor

```sh
npm run build
npm run lint
npm test
node scripts/punta-a-punta.mjs
```

La prueba de punta a punta levanta servidores aislados, crea una lista simulada desde el navegador, observa pasos reales, filtra, abre una ficha, descarga y revisa las 15 columnas de Aventura, reabre la lista desde el historial y ejecuta la validación sintética de siete criterios. Guarda capturas de 1440 × 900 en [docs/capturas/real/](docs/capturas/real/) y cierra sus procesos al terminar. El entorno de prueba no usa credenciales reales.

Las pruebas unitarias también cubren normalización, filtros, orden, formatos de cifras, sondeo, envío del brief y de simulación, token ausente, motor apagado y fichas con datos incompletos.

## Mock para pruebas y capturas

El mock sigue disponible únicamente como fuente sintética para pruebas visuales. En dos terminales:

```sh
npm run mock
```

```sh
VITE_MOTOR_TOKEN=demo-local npm run dev
```

Si configuraste `VITE_MOTOR_URL` para otro origen, apúntalo al mock (`http://127.0.0.1:8000`). El mock y el motor no pueden ocupar el mismo puerto a la vez. El mock conserva sus corridas en memoria y vuelve a sus ejemplos iniciales al reiniciarlo; sus perfiles y marcas son ficticios. No se cargan imágenes externas y los avatares son iniciales.

Las verificaciones anteriores del mock permanecen en `scripts/verificar-*.mjs` y `mock/verificar.mjs`. Para instalar Chromium dentro del proyecto y tomar capturas del mock:

```sh
PLAYWRIGHT_BROWSERS_PATH=0 npx --cache .npm-cache playwright install chromium
npm run capturas
```

Las [capturas originales](docs/capturas/) se generaron contra el mock en 1440 × 900, 1280 × 800 y 1024 × 800. Las nuevas capturas en `real/` corresponden al motor simulado por HTTP, sin mock.

## Organización

- `src/config.ts`: nombre, firma y nombre de la referencia de validación (`Modash`).
- `src/api.ts`, `tipos.ts`, `useSondeo.ts`: contrato, autenticación, errores y sondeo cada tres segundos.
- `src/NuevaLista.tsx`, `Proceso.tsx`, `Resultados.tsx`, `Perfil.tsx`, `Validacion.tsx`, `Historial.tsx`: las seis vistas.
- `src/componentes.tsx`: componentes, acuarela y gráficos SVG propios.
- `scripts/demo.mjs`: inicio y cierre conjunto de motor y web.
- `mock/`: servidor y datos sintéticos para pruebas.

React 18, TypeScript estricto, Vite y Tailwind CSS 3; íconos de lucide-react y fuentes Gloock e Instrument Sans con respaldo local. No se agregaron dependencias de interfaz para la integración.
