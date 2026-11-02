/* global document */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { perfilesDemo, parametrosDemo } from '../mock/datos.mjs';
import { abrir, comprobarAncho, comprobarConsola, esperarFuentes, iniciarNavegador, nuevaCorrida, origen, registrarErrores } from './navegador.mjs';

const navegador = await iniciarNavegador();
const carpeta = resolve('docs/capturas');
const verificaciones = [];
const soloProceso = process.argv.includes('--solo-proceso');
try {
  for (const [ancho, alto] of [[1440, 900], [1280, 800], [1024, 800]]) {
    const contexto = await navegador.newContext({ viewport: { width: ancho, height: alto }, deviceScaleFactor: 1, locale: 'es-PE', reducedMotion: 'reduce' });
    const pagina = await contexto.newPage();
    const errores = registrarErrores(pagina);
    const destino = ancho === 1440 ? carpeta : resolve(carpeta, `${ancho}x${alto}`);
    await mkdir(destino, { recursive: true });
    async function capturar(nombre) {
      await esperarFuentes(pagina);
      await comprobarAncho(pagina, `${ancho}x${alto} / ${nombre}`);
      await pagina.screenshot({ path: resolve(destino, `${nombre}.png`), fullPage: false, animations: 'disabled' });
      verificaciones.push({ pantalla: nombre, ancho, alto, sinDesborde: true, ...(nombre === '02-en-proceso' ? { avance: Number(await pagina.getByRole('progressbar').getAttribute('aria-valuenow')) } : {}) });
      console.log(`Captura lista: ${ancho}x${alto} / ${nombre}`);
    }
    if (!soloProceso) {
      await abrir(pagina, '/', '.hero-acuarela');
      await pagina.getByLabel('Cuenta de referencia', { exact: true }).fill(parametrosDemo.referencia);
      await capturar('01-nueva-lista');
    }
    const id = await nuevaCorrida(contexto);
    await abrir(pagina, `/listas/${id}`, '.tarjeta-progreso');
    await pagina.getByText(/Paso [1-8] de 8/).waitFor();
    await pagina.waitForFunction(() => Number(document.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')) >= 10);
    await capturar('02-en-proceso');
    if (soloProceso) { comprobarConsola(errores); await contexto.close(); continue; }
    await abrir(pagina, '/listas/lista-demo', '.res-fila');
    await capturar('03-resultados');
    await pagina.locator('.res-distribucion').evaluate((elemento) => elemento.scrollIntoView({ block: 'start', behavior: 'instant' }));
    await capturar('07-resultados-detalle');
    await pagina.getByRole('button', { name: 'Tabla', exact: true }).click();
    await pagina.locator('.res-tabla').waitFor();
    await pagina.locator('.res-distribucion').evaluate((elemento) => elemento.scrollIntoView({ block: 'start', behavior: 'instant' }));
    await capturar('08-tabla');
    await abrir(pagina, `/listas/lista-demo/perfil/${perfilesDemo[0].usuario}`, '.perfil-cajon');
    await pagina.locator('.perfil-cajon').evaluate(async (elemento) => { await Promise.all(elemento.getAnimations().map((animacion) => animacion.finished)); });
    await capturar('04-ficha-perfil');
    await abrir(pagina, '/validacion', '.criterio');
    await capturar('05-validacion');
    await abrir(pagina, '/listas', '.tabla-historial tbody tr');
    await capturar('06-historial');
    comprobarConsola(errores);
    await contexto.close();
  }
  let pantallas = verificaciones;
  if (soloProceso) {
    const anterior = JSON.parse(await readFile(resolve(carpeta, 'verificacion.json'), 'utf8'));
    pantallas = [...anterior.pantallas.filter((pantalla) => pantalla.pantalla !== '02-en-proceso'), ...verificaciones];
  }
  await writeFile(resolve(carpeta, 'verificacion.json'), `${JSON.stringify({ origen, pantallas, erroresConsola: [] }, null, 2)}\n`);
  console.log(soloProceso ? 'Tres capturas de proceso actualizadas con avance real de al menos 10 %; las demás se conservan.' : '24 capturas listas: seis pantallas y dos detalles en tres tamaños, sin desbordes ni errores de consola.');
} finally { await navegador.close(); }
