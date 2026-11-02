/* global document, window */
import assert from 'node:assert/strict';
import { parametrosDemo } from '../mock/datos.mjs';

// Mantén Chromium en el proyecto; no se usa ningún perfil personal del navegador.
process.env.PLAYWRIGHT_BROWSERS_PATH ??= '0';
export const origen = process.env.RADAR_URL ?? 'http://127.0.0.1:5173';
export async function iniciarNavegador() {
  const { chromium } = await import('playwright');
  return chromium.launch({ headless: true });
}
export function registrarErrores(pagina) {
  const errores = [];
  pagina.on('pageerror', (error) => errores.push(error.message));
  pagina.on('console', (mensaje) => { if (mensaje.type() === 'error') errores.push(mensaje.text()); });
  return errores;
}
export async function esperarFuentes(pagina) {
  await pagina.evaluate(async () => { await document.fonts.ready; });
}
export async function comprobarAncho(pagina, contexto) {
  const medidas = await pagina.evaluate(() => ({ documento: document.documentElement.scrollWidth, ventana: window.innerWidth }));
  assert.ok(medidas.documento <= medidas.ventana + 1, `${contexto}: desborde global de ${medidas.documento - medidas.ventana}px`);
}
export async function abrir(pagina, ruta, selector) {
  await pagina.goto(`${origen}${ruta}`, { waitUntil: 'networkidle' });
  await pagina.locator(selector).first().waitFor();
  await esperarFuentes(pagina);
}
export async function nuevaCorrida(contexto) {
  const respuesta = await contexto.request.post(`${origen}/api/listas`, { headers: { Authorization: 'Bearer demo-local' }, data: { ...parametrosDemo, estimar: false, simulado: true } });
  assert.equal(respuesta.status(), 202, 'El mock debe aceptar la nueva corrida.');
  return (await respuesta.json()).id;
}
export function comprobarConsola(errores) {
  assert.deepEqual(errores, [], 'El navegador debe terminar sin errores de consola ni excepciones.');
}
