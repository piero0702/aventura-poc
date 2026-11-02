/* global document */
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parametrosDemo, perfilesDemo } from '../mock/datos.mjs';
import { abrir, comprobarAncho, comprobarConsola, iniciarNavegador, origen, registrarErrores } from './navegador.mjs';

const navegador = await iniciarNavegador();
const contexto = await navegador.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true, locale: 'es-PE', reducedMotion: 'reduce' });
const pagina = await contexto.newPage();
const errores = registrarErrores(pagina);
let carpetaTemporal;
try {
  await abrir(pagina, '/', '.hero-acuarela');
  await pagina.getByLabel('Cuenta de referencia', { exact: true }).fill(`@${parametrosDemo.referencia}`);
  await pagina.getByRole('button', { name: 'Calcular costo', exact: true }).click();
  await pagina.locator('.desglose-costo').waitFor();
  assert.ok((await pagina.locator('.desglose-costo').innerText()).includes('USD'), 'La estimación muestra el costo y su desglose.');
  console.log('Navegador: estimación real recibida desde el mock.');

  await abrir(pagina, '/listas/lista-demo', '.res-fila');
  const visiblesIniciales = await pagina.locator('.res-fila').count();
  assert.equal(visiblesIniciales, perfilesDemo.filter((perfil) => !perfil.descartado).length);
  await pagina.getByRole('searchbox').fill(perfilesDemo[20].usuario);
  assert.equal(await pagina.locator('.res-fila').count(), 1, 'La búsqueda reduce los resultados al usuario elegido.');
  await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
  await pagina.getByRole('checkbox', { name: /^Moda/ }).check();
  await pagina.getByRole('checkbox', { name: /^Gastronomía/ }).check();
  const categorias = await pagina.locator('.res-fila .chip').allTextContents();
  assert.ok(categorias.length > 0 && categorias.every((categoria) => ['Moda', 'Gastronomía'].includes(categoria.trim())), 'La selección múltiple combina categorías.');
  await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
  await pagina.getByLabel('Ocultar descartados', { exact: true }).uncheck();
  assert.equal(await pagina.locator('.res-fila').count(), 60);
  assert.ok(await pagina.locator('.res-descartado').count() > 0, 'Los descartados conservan su motivo.');
  await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
  await pagina.getByLabel('Excluir marcas a evitar', { exact: true }).check();
  assert.ok(await pagina.locator('.res-fila').count() < visiblesIniciales, 'Se excluyen colaboraciones con marcas del brief.');
  await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
  console.log('Navegador: búsqueda, multiselección, descartados y marcas a evitar correctos.');

  await pagina.getByRole('button', { name: 'Tabla', exact: true }).click();
  assert.equal(await pagina.locator('.res-tabla thead th').count(), 15);
  await pagina.locator('.res-tabla thead th').filter({ hasText: 'Followers' }).getByRole('button').click();
  assert.equal(await pagina.locator('.res-tabla thead th').filter({ hasText: 'Followers' }).getAttribute('aria-sort'), 'descending');
  const mayorFollower = Math.max(...perfilesDemo.filter((perfil) => !perfil.descartado).map((perfil) => perfil.followers));
  assert.equal(await pagina.locator('.res-tabla tbody tr').first().locator('td').nth(5).innerText(), new Intl.NumberFormat('es-PE').format(mayorFollower), 'El orden por followers cambia los datos de la tabla.');
  const region = pagina.getByRole('region', { name: /Tabla de las 15 columnas/ });
  await region.focus();
  await pagina.keyboard.press('ArrowRight');
  await pagina.waitForFunction(() => document.querySelector('.res-tabla-contenedor')?.scrollLeft > 0);
  await comprobarAncho(pagina, 'Tabla de 15 columnas');
  const [descarga] = await Promise.all([pagina.waitForEvent('download'), pagina.getByRole('button', { name: 'Descargar Excel', exact: true }).click()]);
  assert.match(descarga.suggestedFilename(), /^lista-casa\.bruma-\d{4}-\d{2}-\d{2}\.xlsx$/);
  carpetaTemporal = await mkdtemp(resolve('docs/capturas/descarga-temporal-'));
  const archivoExcel = resolve(carpetaTemporal, descarga.suggestedFilename());
  await descarga.saveAs(archivoExcel);
  assert.equal((await readFile(archivoExcel)).subarray(0, 2).toString(), 'PK');
  console.log('Navegador: tabla con 15 columnas, orden, teclado y descarga Excel correctos.');

  await pagina.getByRole('button', { name: 'Filas', exact: true }).click();
  const accion = pagina.getByRole('button', { name: /^Ver ficha de / }).first();
  await accion.click();
  await pagina.getByRole('dialog').waitFor();
  assert.ok(pagina.url().includes('/perfil/'));
  assert.equal(await pagina.getByRole('button', { name: 'Cerrar ficha', exact: true }).first().evaluate((elemento) => elemento === document.activeElement), true);
  await pagina.keyboard.press('Shift+Tab');
  assert.equal(await pagina.getByRole('dialog').evaluate((elemento) => elemento.contains(document.activeElement)), true, 'El foco permanece dentro del cajón.');
  await pagina.keyboard.press('Escape');
  await pagina.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.equal(pagina.url(), `${origen}/listas/lista-demo`);
  await pagina.waitForFunction(() => document.activeElement?.classList.contains('res-ver-ficha'));
  console.log('Navegador: URL propia de ficha, foco contenido, Escape y restauración del foco correctos.');

  await abrir(pagina, '/validacion', '.criterio');
  assert.equal(await pagina.locator('.criterio').count(), 7);
  assert.equal(await pagina.locator('.tabla-validacion tbody tr').count(), 102);
  await pagina.getByLabel('Solo diferencias', { exact: true }).check();
  assert.equal(await pagina.locator('.tabla-validacion tbody tr').count(), 35);
  await abrir(pagina, '/listas/lista-error', '.estado-interrumpido');
  await pagina.getByRole('button', { name: 'Reintentar', exact: true }).click();
  await pagina.locator('.tarjeta-progreso').waitFor();
  assert.ok(!pagina.url().includes('lista-error'));
  console.log('Navegador: validación de 102 filas y reintento desde error correctos.');

  await abrir(pagina, '/', '.hero-acuarela');
  await pagina.getByLabel('Cuenta de referencia', { exact: true }).fill(parametrosDemo.referencia);
  await pagina.locator('form').getByRole('button', { name: 'Armar lista', exact: true }).click();
  await pagina.locator('.tarjeta-progreso').waitFor();
  const urlProceso = pagina.url();
  await pagina.getByRole('progressbar').waitFor();
  console.log('Navegador: corrida nueva en proceso; esperando finalización automática de ~40 segundos…');
  await pagina.getByRole('heading', { name: /Tu lista está lista/ }).waitFor({ timeout: 50000 });
  await pagina.locator('.res-fila').first().waitFor();
  assert.equal(pagina.url(), urlProceso, 'La misma URL cambia de progreso a resultados automáticamente.');
  await comprobarAncho(pagina, 'Resultado de nueva corrida');
  comprobarConsola(errores);
  console.log('Navegador verificado: nueva lista → progreso → resultados, sin errores de consola.');
} catch (error) {
  console.error('Detalle del fallo de navegador:', { ruta: pagina.url(), foco: await pagina.evaluate(() => document.activeElement?.outerHTML).catch(() => 'No disponible') });
  throw error;
} finally {
  if (carpetaTemporal) await rm(carpetaTemporal, { recursive: true, force: true });
  await contexto.close();
  await navegador.close();
}
