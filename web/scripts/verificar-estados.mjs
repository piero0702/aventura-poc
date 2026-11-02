import assert from 'node:assert/strict';
import { sinProgreso, validacionPendiente } from '../mock/estados-prueba.mjs';
import { abrir, comprobarAncho, iniciarNavegador, origen } from './navegador.mjs';

const navegador = await iniciarNavegador();
const contexto = await navegador.newContext({ viewport: { width: 1280, height: 800 }, locale: 'es-PE', reducedMotion: 'reduce' });
const pagina = await contexto.newPage();
const errores = [];
const respuestasEsperadas = [];
pagina.on('pageerror', (error) => errores.push(error.message));
pagina.on('console', (mensaje) => {
  if (mensaje.type() !== 'error') return;
  // El 404 de esta ruta se provoca a propósito para comprobar el estado vacío del contrato.
  if (mensaje.location().url.endsWith('/api/validacion') && /404/.test(mensaje.text())) respuestasEsperadas.push(mensaje.text());
  else errores.push(mensaje.text());
});
try {
  const respuesta = await contexto.request.get(`${origen}/api/listas/lista-demo`, { headers: { Authorization: 'Bearer demo-local' } });
  assert.equal(respuesta.status(), 200);
  const semilla = await respuesta.json();
  await pagina.route('**/api/listas/lista-demo', (ruta) => ruta.fulfill({ status: 200, json: sinProgreso(semilla) }));
  await abrir(pagina, '/listas/lista-demo', '.tarjeta-progreso');
  const barra = pagina.getByRole('progressbar', { name: 'Avance de la lista' });
  assert.equal(await barra.getAttribute('aria-valuenow'), null, 'Sin progreso no se presenta un porcentaje inventado.');
  assert.ok((await barra.getAttribute('class')).includes('indeterminada'));
  assert.equal(await pagina.locator('.contadores-progreso .cifra-grupo').count(), 4);
  assert.ok((await pagina.locator('.contadores-progreso').innerText()).includes(`USD ${semilla.costo_total_usd.toFixed(3)}`), 'El costo acumulado que sí conocemos sigue visible.');
  await comprobarAncho(pagina, 'Progreso indeterminado');
  console.log('Estados: progreso indeterminado, sin porcentaje inventado y con costo conocido visibles.');

  await pagina.route('**/api/validacion', (ruta) => ruta.fulfill({ status: 404, json: validacionPendiente }));
  await abrir(pagina, '/validacion', '.estado-vacio');
  assert.equal(await pagina.getByRole('heading', { name: 'Aún no corremos la validación', exact: true }).count(), 1);
  assert.equal(await pagina.locator('.criterio').count(), 0);
  await comprobarAncho(pagina, 'Validación pendiente');
  assert.deepEqual(errores, [], 'Solo el 404 de validación provocado a propósito puede aparecer en consola.');
  console.log(`Estados: Validación404 muestra su estado vacío; ${respuestasEsperadas.length} aviso(s) HTTP404 esperados, sin excepciones ni otros errores.`);
} finally { await contexto.close(); await navegador.close(); }
