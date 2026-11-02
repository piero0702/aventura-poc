# Notas de entrega · integración con el motor

## Qué hice

- Conecté las seis vistas al motor HTTP local: Nueva lista, progreso, resultados, ficha, Validación y Mis listas. `npm run dev` usa el motor configurado; el mock queda para pruebas y capturas.
- Eliminé el token de reemplazo. Si falta `VITE_MOTOR_TOKEN`, la UI lo explica sin hacer solicitudes; si el motor está apagado, muestra «El motor no está encendido». La descarga también exige Bearer.
- El formulario envía el brief completado y omite el brief vacío. El interruptor «Modo prueba (sin costo)» empieza apagado y solo se ofrece con `VITE_PERMITIR_SIMULADO=true`.
- El progreso muestra únicamente el paso y los contadores que trae el motor. Como la tubería recorre los pasos por cada perfil, no marca las fases anteriores como globalmente terminadas. El tiempo transcurrido parte de la fecha real de la corrida.
- Resultados, tabla y ficha admiten métricas, categoría, nombre y fecha de evidencia ausentes. Se muestran como «—». Las distribuciones de audiencia solo aparecen si llegan desde el motor y la explicación distingue muestra de seguidores y contenido.
- Oculté los puntajes, filtros y orden por encaje cuando no hubo brief. Si existe brief pero no evaluación de un perfil, se muestra «—». La ficha identifica promedio o mediana según los parámetros de la corrida.
- Identifiqué los resultados simulados, su costo teórico y su duración medida. Las corridas parciales explican el corte y las corridas con reservas pendientes lo indican. Error e interrupción conservan la explicación del motor y la opción de reintentar. El reintento reconstruye únicamente los campos aceptados por la API y conserva el modo simulado; los metadatos de agregación y nombre no se reenvían como opciones de procesamiento.
- Historial abre corridas registradas por CLI o HTTP. Los perfiles procesados y la duración permanecen como «—» si todavía no están disponibles. El costo mostrado procede del registro del motor.
- La validación usa «Modash», centralizado en `src/config.ts`. Los resultados no evaluables aparecen sin cifra inventada y conservan el detalle que entrega el validador.
- Agregué `npm run demo`: inicia el motor desde la carpeta hermana `motor/` y la web desde `web/`, resuelve las rutas desde el script y cierra ambos grupos de procesos con Ctrl+C o si alguno falla.
- Actualicé el README, `.env.example` y el contrato de la API. El script `scripts/punta-a-punta.mjs` y las capturas de `docs/capturas/real/` comprueban el recorrido contra el motor simulado; las capturas anteriores de `docs/capturas/` siguen siendo del mock.

## Decisiones

- Conservé el stack y los componentes de la web; no agregué dependencias para integrar el motor.
- El token HTTP se configura explícitamente incluso al usar el mock. El cliente ya no usa `demo-local` por defecto.
- Un brief vacío no genera encaje. No impuse un rango de followers oculto en el formulario; los rangos se envían si la usuaria los completa.
- La UI no promete minutos para una lista real. Los únicos tiempos de resultados son los medidos por el motor; una simulación se identifica de forma visible.
- Las etiquetas del desglose traducen los pasos internos del registro de costos a español, sin exponer nombres de proveedores como si fueran etapas del producto.
- Las rutas hermanas usadas por `demo` responden al encargo raíz de integración, que prevalece sobre el alcance anterior de esta carpeta.

## Verificación y pendientes

`npm run build`, `npm run lint` y `npm test` verifican compilación, código y regresiones de API, formularios, fichas incompletas, filtros, formatos y sondeo. La verificación final conjunta y el resultado de la prueba de punta a punta quedan registrados en `NOTAS-CODEX.md` de la raíz.

Praxia debe completar los archivos locales de configuración, cargar las llaves y ejecutar la validación real de 102 perfiles por su cuenta. La muestra sintética no acredita exactitud, tiempo ni costo real. No se hicieron llamadas reales a proveedores, no se crearon llaves ni se realizó despliegue. La configuración exacta para la demo real está documentada en `NOTAS-CODEX.md` de la raíz y en los README.
