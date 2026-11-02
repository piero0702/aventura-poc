# Aventura · PoC

Prueba de concepto de Praxia para Aventura: arma listas de perfiles de Instagram con métricas, audiencia estimada y marcas con las que trabajó cada perfil, y las entrega en Excel.

- [`motor/`](motor/) — motor en Python (Apify, Groq, clasificación con IA) con CLI y API HTTP. Ver [motor/README.md](motor/README.md).
- [`web/`](web/) — web local en Vite + React sobre la API del motor. Ver [web/README.md](web/README.md).

## Correr la demo

```sh
cd motor && uv sync && cp .env.example .env
cd ../web && npm install && cp .env.example .env.local
npm run demo
```

Levanta el motor en `:8000` y la web en `:5173`. Las llaves de los servicios van en `motor/.env`; el token compartido en `MOTOR_HTTP_TOKEN` (motor) y `VITE_MOTOR_TOKEN` (web).

Todos los datos de prueba del repositorio son sintéticos.
