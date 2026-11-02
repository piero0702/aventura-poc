import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { iniciarNavegador, origen, registrarErrores } from './navegador.mjs';
/* global document, window */

// Recorre filtros, tabla y ficha contra el mock que ya está corriendo.
const navegador = await iniciarNavegador();
const capturar = process.argv.includes('--capturas');
if (capturar) await mkdir('docs/revision', { recursive: true });
try {
  const pagina = await navegador.newPage();
  const errores = registrarErrores(pagina);
  for (const [ancho, alto] of [[1440, 900], [1280, 800], [1024, 800]]) {
    await pagina.setViewportSize({ width: ancho, height: alto });
    await pagina.goto(`${origen}/listas/lista-demo`);
    await pagina.locator('.res-fila').first().waitFor();
    if (capturar) { await pagina.evaluate(() => document.fonts.ready); await pagina.screenshot({ path: `docs/revision/resultados-${ancho}.png` }); }
    assert.equal(await pagina.locator('h1').textContent(), 'Tu lista está lista.');
    assert.ok(await pagina.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `No debe haber desborde a ${ancho} px`);
    const inicial = await pagina.locator('.res-fila').count();
    await pagina.getByLabel('Ocultar descartados').uncheck();
    assert.ok(await pagina.locator('.res-fila').count() > inicial, 'Mostrar descartados agrega perfiles');
    const nombre = (await pagina.locator('.res-nombre').first().textContent()).trim();
    await pagina.getByPlaceholder('Busca un perfil…').fill(nombre);
    assert.ok(await pagina.locator('.res-fila').count() > 0);
    await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
    assert.equal(await pagina.locator('.res-fila').count(), inicial);
    await pagina.getByRole('button', { name: 'Tabla', exact: true }).click();
    assert.equal(await pagina.locator('.res-tabla th').count(), 15, 'Tabla con las quince columnas exactas');
    await pagina.locator('.res-tabla th button').nth(5).click();
    const enlace = pagina.locator('.res-tabla-perfil').first();
    await enlace.click();
    await pagina.getByRole('dialog').waitFor();
    if (capturar) await pagina.screenshot({ path: `docs/revision/ficha-${ancho}.png` });
    assert.ok(pagina.url().includes('/perfil/'));
    assert.equal(await pagina.locator('.cabecera').evaluate(elemento => elemento.inert), true);
    assert.equal(await pagina.locator('main').evaluate(elemento => elemento.inert), true);
    assert.equal(await pagina.locator('.perfil-cerrar').evaluate(elemento => elemento === document.activeElement), true);
    await pagina.keyboard.press('Shift+Tab');
    assert.equal(await pagina.locator('.perfil-cerrar-final').evaluate(elemento => elemento === document.activeElement), true, 'El foco queda dentro de la ficha');
    await pagina.keyboard.press('Escape');
    await pagina.getByRole('dialog').waitFor({ state: 'detached' });
    await pagina.waitForFunction(() => document.activeElement?.classList.contains('res-tabla-perfil'));
    assert.equal(await pagina.locator('.cabecera').evaluate(elemento => elemento.inert), false);
    console.log(`Resultados y ficha correctos en ${ancho} × ${alto}.`);
  }
  await pagina.goto(`${origen}/listas/lista-demo/perfil/perfil.inexistente`);
  await pagina.getByRole('dialog').waitFor();
  await pagina.keyboard.press('Tab');
  assert.equal(await pagina.getByRole('button', { name: 'Volver a la lista', exact: true }).evaluate(elemento => elemento === document.activeElement), true);
  await pagina.keyboard.press('Escape');
  await pagina.getByRole('dialog').waitFor({ state: 'detached' });
  await pagina.setViewportSize({ width: 780, height: 900 });
  await pagina.getByRole('button', { name: 'Filas', exact: true }).click();
  await pagina.getByRole('button', { name: 'Filtros', exact: true }).click();
  assert.equal(await pagina.getByRole('dialog', { name: 'Filtros de perfiles' }).isVisible(), true);
  await pagina.keyboard.press('Escape');
  assert.equal(await pagina.getByRole('button', { name: 'Filtros', exact: true }).evaluate(elemento => elemento === document.activeElement), true);
  assert.deepEqual(errores, [], 'Sin errores de JavaScript');
  console.log('Filtros en cajón, URL inexistente y restauración de foco correctos.');
} finally { await navegador.close(); }
