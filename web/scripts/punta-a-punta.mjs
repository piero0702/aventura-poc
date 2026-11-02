/* global document */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdir, open, readFile, rm, writeFile } from 'node:fs/promises';
import net from 'node:net';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { iniciarNavegador, registrarErrores, comprobarConsola, comprobarAncho } from './navegador.mjs';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const motor = resolve(web, '..', 'motor');
const temporal = resolve(motor, '.motor', `punta-a-punta-${randomUUID()}`);
const capturas = resolve(web, 'docs/capturas/real');
const entornoMotor = resolve(motor, '.env');
const puertoMotor = 18000;
const puertoWeb = 15173;
const origen = `http://127.0.0.1:${puertoWeb}`;
const autorizacion = { Authorization: 'Bearer token-local' };
const procesos = [];
let navegador;
let creoEnv = false;
let terminando = false;

const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

function iniciar(comando, argumentos, carpeta, entorno = {}) {
  const proceso = spawn(comando, argumentos, { cwd: carpeta, env: { ...process.env, ...entorno },
    detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] });
  let salida = '';
  proceso.stdout.on('data', (dato) => { salida = (salida + dato).slice(-12000); });
  proceso.stderr.on('data', (dato) => { salida = (salida + dato).slice(-12000); });
  proceso.on('error', (error) => { salida += error.message; });
  procesos.push(proceso);
  return { proceso, salida: () => salida };
}

async function ejecutar(comando, argumentos, carpeta) {
  const tarea = iniciar(comando, argumentos, carpeta);
  const [codigo] = await once(tarea.proceso, 'exit');
  assert.equal(codigo, 0, tarea.salida());
  return tarea.salida();
}

async function puertoLibre(puerto) {
  const servidor = net.createServer();
  await new Promise((resolver, rechazar) => {
    servidor.once('error', () => rechazar(new Error(`El puerto ${puerto} está ocupado; la prueba no apaga servicios ajenos.`)));
    servidor.listen(puerto, '127.0.0.1', resolver);
  });
  await new Promise((resolver) => servidor.close(resolver));
}

async function esperarServicio(url, tarea, opciones = {}) {
  for (let intento = 0; intento < 150; intento++) {
    if (tarea.proceso.exitCode !== null) throw new Error(tarea.salida());
    try { if ((await fetch(url, opciones)).ok) return; } catch { /* Aún está iniciando. */ }
    await esperar(200);
  }
  throw new Error(`El servicio no inició: ${url}\n${tarea.salida()}`);
}

async function limpiar() {
  if (terminando) return;
  terminando = true;
  await navegador?.close();
  for (const proceso of procesos) {
    if (proceso.exitCode !== null || !proceso.pid) continue;
    try {
      if (process.platform === 'win32') proceso.kill('SIGTERM');
      else process.kill(-proceso.pid, 'SIGTERM');
    } catch { /* El proceso ya terminó. */ }
  }
  await Promise.all(procesos.filter((p) => p.exitCode === null).map(async (p) => {
    await Promise.race([once(p, 'exit'), esperar(5000)]);
    if (p.exitCode === null) {
      try { process.kill(process.platform === 'win32' ? p.pid : -p.pid, 'SIGKILL'); } catch { /* Ya terminó. */ }
    }
  }));
  if (creoEnv) await rm(entornoMotor, { force: true });
  await rm(temporal, { recursive: true, force: true });
}

for (const senal of ['SIGINT', 'SIGTERM']) process.once(senal, () => {
  void limpiar().then(() => { process.exitCode = 1; });
});

try {
  await puertoLibre(puertoMotor);
  await puertoLibre(puertoWeb);
  // No se lee ni sobrescribe un .env existente: podría contener llaves reales.
  let archivo;
  try { archivo = await open(entornoMotor, 'wx', 0o600); }
  catch (error) {
    if (error.code === 'EEXIST') throw new Error('Ya existe motor/.env. Retíralo temporalmente antes de la prueba; no lo leemos ni sobrescribimos.');
    throw error;
  }
  creoEnv = true;
  await archivo.writeFile('MOTOR_HTTP_TOKEN=token-local\n');
  await archivo.close();
  await mkdir(temporal, { recursive: true });
  await mkdir(capturas, { recursive: true });
  // Solo la fábrica de prueba inyecta retraso y almacén aislado. El .env lleva únicamente el token.
  await writeFile(resolve(temporal, 'servicio_prueba.py'), [
    'import os',
    'from motor.almacen import Almacen',
    'from motor.configuracion import Configuracion',
    'from motor.http import crear_app',
    'def crear():',
    '    configuracion = Configuracion.cargar()',
    '    configuracion.simulado_retraso_s = float(os.environ["MOTOR_SIMULADO_RETRASO_S"])',
    `    return crear_app(configuracion, almacen=Almacen(${JSON.stringify(resolve(temporal, 'datos.sqlite'))}), validacion=${JSON.stringify(resolve(temporal, 'validacion.json'))})`,
    '',
  ].join('\n'));
  const servicio = iniciar('uv', ['run', 'uvicorn', 'servicio_prueba:crear', '--factory', '--app-dir', temporal,
    '--host', '127.0.0.1', '--port', String(puertoMotor), '--workers', '1'], motor, { MOTOR_SIMULADO_RETRASO_S: '0.7' });
  const interfaz = iniciar('npm', ['run', 'dev', '--', '--port', String(puertoWeb)], web,
    { VITE_MOTOR_URL: `http://127.0.0.1:${puertoMotor}`, VITE_MOTOR_TOKEN: 'token-local', VITE_PERMITIR_SIMULADO: 'true' });
  await Promise.all([esperarServicio(`http://127.0.0.1:${puertoMotor}/listas`, servicio, { headers: autorizacion }),
    esperarServicio(origen, interfaz)]);
  navegador = await iniciarNavegador();
  const contexto = await navegador.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true,
    locale: 'es-PE', reducedMotion: 'reduce' });
  // La prueba solo permite la web local; fuentes remotas quedan resueltas sin red externa.
  await contexto.route(/^https?:\/\/(?!127\.0\.0\.1(?=:))/, (ruta) => ruta.fulfill({ status: 200, body: '' }));
  const pagina = await contexto.newPage();
  const errores = registrarErrores(pagina);
  const pasos = new Set();
  pagina.on('response', async (respuesta) => {
    if (/\/api\/listas\/[^/]+$/u.test(respuesta.url()) && respuesta.request().method() === 'GET') {
      try {
        const datos = await respuesta.json();
        if (datos.progreso) pasos.add(datos.progreso.paso);
      } catch { /* Una respuesta cancelada no aporta un paso observado. */ }
    }
  });
  const capturar = async (nombre) => {
    await pagina.evaluate(async () => { await document.fonts.ready; });
    await comprobarAncho(pagina, nombre);
    await pagina.screenshot({ path: resolve(capturas, `${nombre}.png`) });
  };
  await pagina.goto(origen, { waitUntil: 'networkidle' });
  await pagina.getByLabel('Cuenta de referencia', { exact: true }).fill('@referencia.sintetica');
  await pagina.locator('summary').filter({ hasText: 'Brief de la marca' }).click();
  await pagina.getByLabel('Marca', { exact: true }).fill('Campaña sintética Bruma');
  await pagina.getByLabel('¿Con quién quieres conectar?', { exact: true }).fill('Mujeres de 25 a 34 años en Lima interesadas en cocina.');
  await pagina.locator('summary').filter({ hasText: 'Opciones avanzadas' }).click();
  await pagina.getByLabel('Límite de perfiles', { exact: true }).fill('3');
  await pagina.getByLabel('Modo prueba (sin costo)', { exact: true }).check();
  await capturar('01-nueva-lista');
  await pagina.getByRole('button', { name: 'Calcular costo', exact: true }).click();
  await pagina.locator('.desglose-costo').waitFor();
  assert.match(await pagina.locator('.desglose-costo').innerText(), /USD/u);
  await pagina.locator('form').getByRole('button', { name: 'Armar lista', exact: true }).click();
  await pagina.locator('.tarjeta-progreso').waitFor();
  await pagina.getByRole('progressbar').waitFor();
  const id = pagina.url().split('/').at(-1);
  await capturar('02-progreso');
  await pagina.locator('.res-fila').first().waitFor({ timeout: 90000 });
  assert.ok(pasos.size >= 3, `Deben verse varios pasos reales del motor: ${[...pasos].join(', ')}`);
  const estado = await (await contexto.request.get(`${origen}/api/listas/${id}`, { headers: autorizacion })).json();
  assert.equal(estado.estado, 'completa');
  assert.equal(estado.corrida.ejecucion_simulada, true);
  assert.equal(estado.corrida.parametros.brief.marca, 'Campaña sintética Bruma');
  const perfiles = await (await contexto.request.get(`${origen}/api/listas/${id}/perfiles`, { headers: autorizacion })).json();
  assert.equal(perfiles.length, 3);
  assert.equal(await pagina.locator('.res-fila').count(), 3);
  await capturar('03-resultados');
  await pagina.getByRole('searchbox').fill(perfiles[0].usuario);
  assert.equal(await pagina.locator('.res-fila').count(), 1);
  await pagina.getByRole('button', { name: /^Ver ficha de /u }).first().click();
  const ficha = pagina.getByRole('dialog');
  await ficha.waitFor();
  assert.match(await ficha.innerText(), /marca\.sintetica/u);
  assert.match(await ficha.innerText(), /25–34|25-34/u);
  assert.equal(perfiles[0].audiencia.fuente, 'seguidores');
  assert.equal(perfiles[0].seguidores_muestra, 3);
  assert.equal(perfiles[0].marcas[0].tipo, 'publicidad');
  await capturar('04-ficha');
  await ficha.locator('.perfil-timeline').scrollIntoViewIfNeeded();
  await capturar('04b-ficha-marcas');
  await pagina.keyboard.press('Escape');
  await ficha.waitFor({ state: 'hidden' });
  await pagina.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
  await pagina.getByRole('button', { name: 'Tabla', exact: true }).click();
  assert.equal(await pagina.locator('.res-tabla thead th').count(), 15);
  const [descarga] = await Promise.all([pagina.waitForEvent('download'),
    pagina.getByRole('button', { name: 'Descargar Excel', exact: true }).click()]);
  const excel = resolve(temporal, 'descargado.xlsx');
  await descarga.saveAs(excel);
  assert.equal((await readFile(excel)).subarray(0, 2).toString(), 'PK');
  await ejecutar('uv', ['run', 'python', '-c', [
    'from openpyxl import load_workbook',
    'from motor.excel import COLUMNAS_BASE, COLUMNAS_EXTRA',
    `libro = load_workbook(${JSON.stringify(excel)}, read_only=True)`,
    'assert list(next(libro["Perfiles"].values)) == COLUMNAS_BASE + COLUMNAS_EXTRA',
    'assert libro["Perfiles"].max_row == 4',
    'libro.close()',
  ].join('\n')], motor);
  await pagina.getByRole('link', { name: 'Mis listas', exact: true }).first().click();
  await pagina.locator('.tabla-historial tbody tr').first().waitFor();
  await capturar('05-historial');
  await pagina.getByRole('link', { name: 'Abrir lista de @referencia.sintetica', exact: true }).first().click();
  await pagina.locator('.res-fila').first().waitFor();
  assert.equal(pagina.url(), `${origen}/listas/${id}`);
  await ejecutar('uv', ['run', 'motor', 'validar', '--modash', 'fixtures/muestra-sintetica.xlsx',
    '--salida', excel, '--informe', resolve(temporal, 'validacion.md'), '--json', resolve(temporal, 'validacion.json')], motor);
  await pagina.getByRole('link', { name: 'Validación', exact: true }).first().click();
  await pagina.locator('.criterio').first().waitFor();
  assert.equal(await pagina.locator('.criterio').count(), 7);
  assert.equal(await pagina.locator('.tabla-validacion tbody tr').count(), 5);
  assert.match(await pagina.locator('.tabla-validacion').innerText(), /Modash/u);
  await pagina.getByLabel('Solo diferencias', { exact: true }).check();
  assert.ok(await pagina.locator('.tabla-validacion tbody tr').count() > 0);
  await capturar('06-validacion');
  comprobarConsola(errores);
  // Comprueba además el comando público de la demo y su cierre con Ctrl+C.
  await puertoLibre(8000);
  await puertoLibre(5173);
  const demo = iniciar('npm', ['run', 'demo'], web, { VITE_MOTOR_URL: 'http://127.0.0.1:8000',
    VITE_MOTOR_TOKEN: 'token-local', VITE_PERMITIR_SIMULADO: 'false' });
  await Promise.all([esperarServicio('http://127.0.0.1:8000/listas', demo, { headers: autorizacion }),
    esperarServicio('http://127.0.0.1:5173', demo)]);
  const viaProxy = await fetch('http://127.0.0.1:5173/api/listas', { headers: autorizacion });
  assert.equal(viaProxy.status, 200);
  assert.ok(Array.isArray(await viaProxy.json()));
  if (process.platform === 'win32') demo.proceso.kill('SIGINT');
  else process.kill(-demo.proceso.pid, 'SIGINT');
  await Promise.race([once(demo.proceso, 'exit'), esperar(8000)]);
  for (let intento = 0; intento < 40; intento++) {
    try { await puertoLibre(8000); await puertoLibre(5173); break; }
    catch (error) { if (intento === 39) throw error; await esperar(200); }
  }
  await writeFile(resolve(capturas, 'verificacion.json'), JSON.stringify({
    fecha: new Date().toISOString(), viewport: { width: 1440, height: 900 },
    fuente: 'Motor Python real con proveedores simulados, sin mock web',
    pasos_observados: [...pasos], perfiles: perfiles.length, columnas_excel: 15, columnas_auditoria: 8,
    criterios: 7, filas_validacion: 5, errores_consola: errores, demo_arranque_y_ctrl_c: true,
  }, null, 2) + '\n');
  console.log(`Punta a punta en verde: ${pasos.size} pasos, 3 perfiles, Excel 15+8 columnas, historial, validación 7 criterios / 5 filas y demo con Ctrl+C.`);
} finally {
  await limpiar();
}
