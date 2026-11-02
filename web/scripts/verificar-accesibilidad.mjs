/* global document, window, getComputedStyle */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import AxeBuilder from '@axe-core/playwright';
import { perfilesDemo } from '../mock/datos.mjs';
import { abrir, comprobarConsola, iniciarNavegador, nuevaCorrida, origen, registrarErrores } from './navegador.mjs';

// Requiere npm run dev y npm run mock encendidos. Axe revisa el DOM real de Chromium.
const navegador = await iniciarNavegador();
const contexto = await navegador.newContext({ viewport: { width: 1280, height: 800 }, locale: 'es-PE', reducedMotion: 'reduce' });
const pagina = await contexto.newPage();
const errores = registrarErrores(pagina);
const hallazgos = [];
const estadosRevisados = [];
let versionAxe = '';
let revisadas = 0;

async function auditar(nombre) {
  const informe = await new AxeBuilder({ page: pagina }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']).analyze();
  for (const infraccion of informe.violations) {
    const grupos = new Map();
    for (const nodo of infraccion.nodes) {
      const clave = nodo.failureSummary;
      const grupo = grupos.get(clave);
      if (grupo) grupo.afectados += 1;
      else grupos.set(clave, { selector: nodo.target, afectados: 1, detalle: nodo.failureSummary, datos: nodo.any.flatMap((control) => control.data ? [control.data] : []) });
    }
    hallazgos.push({ pantalla: nombre, regla: infraccion.id, impacto: infraccion.impact, descripcion: infraccion.help, nodos: [...grupos.values()] });
  }
  assert.equal(await pagina.locator('main#contenido').count(), 1, `${nombre}: un contenido principal con destino para el enlace de salto.`);
  if (await pagina.getByRole('dialog').count()) {
    assert.ok(await pagina.getByRole('dialog').getByRole('heading').count() > 0, `${nombre}: el cajón tiene un encabezado.`);
  } else {
    assert.equal(await pagina.getByRole('heading', { level: 1 }).count(), 1, `${nombre}: un titular principal.`);
    assert.equal(await pagina.getByRole('navigation', { name: 'Navegación principal' }).count(), 1);
  }
  const movimiento = await pagina.evaluate(() => {
    const largos = [];
    function segundos(valor) { return valor.trim().endsWith('ms') ? Number.parseFloat(valor) / 1000 : Number.parseFloat(valor); }
    for (const elemento of document.querySelectorAll('*')) {
      const estilo = getComputedStyle(elemento);
      if (estilo.animationName !== 'none' || estilo.transitionDuration.split(',').some((valor) => segundos(valor) > 0.001)) largos.push(elemento.className);
    }
    return { reducido: window.matchMedia('(prefers-reduced-motion: reduce)').matches, largos };
  });
  assert.equal(movimiento.reducido, true);
  assert.deepEqual(movimiento.largos, [], `${nombre}: la preferencia de movimiento reducido quita animaciones y transiciones.`);
  versionAxe = informe.testEngine.version;
  estadosRevisados.push({ pantalla: nombre, violaciones: informe.violations.length, reglasAprobadas: informe.passes.length, movimientoReducido: movimiento.reducido });
  revisadas += 1;
  console.log(`Accesibilidad: ${nombre}, ${informe.violations.length} hallazgos, movimiento reducido respetado.`);
}

try {
  await abrir(pagina, '/', '.hero-acuarela');
  await auditar('Nueva lista');
  await pagina.keyboard.press('Tab');
  assert.equal(await pagina.locator('.saltar-contenido').evaluate((elemento) => elemento === document.activeElement), true, 'El primer Tab permite saltar al contenido.');
  const foco = await pagina.locator('.saltar-contenido').evaluate((elemento) => { const estilo = getComputedStyle(elemento); return { estilo: estilo.outlineStyle, ancho: Number.parseFloat(estilo.outlineWidth) }; });
  assert.ok(foco.estilo !== 'none' && foco.ancho >= 2, 'El foco de teclado tiene un contorno visible.');
  for (const plegable of await pagina.locator('details').all()) await plegable.evaluate((elemento) => { elemento.open = true; });
  await auditar('Nueva lista con brief y opciones');

  const id = await nuevaCorrida(contexto);
  await abrir(pagina, `/listas/${id}`, '.tarjeta-progreso');
  await auditar('En proceso');

  await abrir(pagina, '/listas/lista-demo', '.res-fila');
  await auditar('Resultados en filas');
  await pagina.getByLabel('Ocultar descartados', { exact: true }).uncheck();
  await auditar('Resultados con descartados');
  await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
  await pagina.getByRole('searchbox').focus();
  await pagina.keyboard.press('Tab');
  assert.equal(await pagina.locator('.res-filtros').evaluate((elemento) => elemento.contains(document.activeElement)), true, 'Los filtros permiten avanzar con Tab.');
  await pagina.getByRole('button', { name: 'Tabla', exact: true }).click();
  await auditar('Resultados en tabla');
  await pagina.getByLabel('Ocultar descartados', { exact: true }).uncheck();
  await auditar('Tabla con descartados');
  await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
  await pagina.getByRole('region', { name: /Tabla de las 15 columnas/ }).focus();
  await pagina.keyboard.press('Tab');
  assert.equal(await pagina.locator('.res-tabla-contenedor').evaluate((elemento) => elemento.contains(document.activeElement)), true, 'La tabla permite recorrer encabezados y acciones con Tab.');

  await pagina.setViewportSize({ width: 780, height: 900 });
  await abrir(pagina, '/listas/lista-demo', '.res-fila');
  await pagina.getByRole('button', { name: 'Filtros', exact: true }).click();
  await auditar('Filtros en cajón');
  await pagina.keyboard.press('Escape');
  assert.equal(await pagina.getByRole('button', { name: 'Filtros', exact: true }).evaluate((elemento) => elemento === document.activeElement), true, 'Cerrar filtros devuelve el foco a su botón.');
  await pagina.setViewportSize({ width: 1280, height: 800 });

  await abrir(pagina, `/listas/lista-demo/perfil/${perfilesDemo[0].usuario}`, '.perfil-cajon');
  await auditar('Ficha del perfil');
  await pagina.keyboard.press('Shift+Tab');
  assert.equal(await pagina.getByRole('dialog').evaluate((elemento) => elemento.contains(document.activeElement)), true, 'El foco permanece dentro del cajón.');
  await pagina.keyboard.press('Escape');
  await pagina.getByRole('dialog').waitFor({ state: 'detached' });

  await abrir(pagina, '/validacion', '.criterio');
  await auditar('Validación');
  await abrir(pagina, '/listas', '.tabla-historial tbody tr');
  await auditar('Mis listas');
  comprobarConsola(errores);
  await mkdir('docs', { recursive: true });
  await writeFile('docs/verificacion-accesibilidad.json', `${JSON.stringify({
    fecha: new Date().toISOString(), origen, motor: 'Mock local con datos sintéticos', versionAxe,
    reproducir: 'Con npm run mock y npm run dev encendidos, ejecuta node scripts/verificar-accesibilidad.mjs',
    etiquetasAxe: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'],
    estados: estadosRevisados, totalEstados: revisadas, totalViolaciones: hallazgos.length,
    comprobacionesTeclado: ['Enlace de salto como primer foco', 'Contorno de foco visible', 'Recorrido de filtros y tabla con Tab', 'Foco contenido dentro de la ficha', 'Cierre con Escape y restauración del foco de filtros'],
    encabezadosYContenidoPrincipal: true, erroresConsola: errores,
    hallazgos,
  }, null, 2)}\n`);
  if (hallazgos.length) console.log(JSON.stringify(hallazgos, null, 2));
  assert.equal(hallazgos.length, 0, 'Las seis pantallas y los estados desplegados deben cumplir las reglas WCAG A/AA revisadas por Axe.');
  console.log(`${revisadas} estados auditados en seis pantallas: WCAG A/AA, encabezados, etiquetas, foco y movimiento reducido verificados.`);
} finally {
  await contexto.close();
  await navegador.close();
}
