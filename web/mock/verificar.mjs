import assert from 'node:assert/strict';
import { writeFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const base = process.env.MOCK_URL ?? 'http://127.0.0.1:8000';
async function obtener(ruta) {
  const respuesta = await fetch(`${base}${ruta}`, { headers: { Authorization: 'Bearer token-sintetico' } });
  return { estado: respuesta.status, datos: await respuesta.json() };
}
async function crear(parametros) {
  const respuesta = await fetch(`${base}/listas`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token-sintetico' }, body: JSON.stringify(parametros) });
  return { estado: respuesta.status, datos: await respuesta.json() };
}
assert.equal((await fetch(`${base}/listas`)).status, 401, 'Todas las rutas del contrato requieren un token Bearer.');
assert.equal((await fetch(`${base}/listas`, { headers: { Authorization: 'Basic token-sintetico' } })).status, 401);
const historial = await obtener('/listas');
assert.equal(historial.estado, 200);
assert.ok(historial.datos.some((lista) => lista.estado === 'parcial'));
assert.ok(historial.datos.some((lista) => lista.estado === 'error'));
const perfiles = await obtener('/listas/lista-demo/perfiles');
assert.equal(perfiles.datos.length, 60);
assert.ok(perfiles.datos.some((perfil) => perfil.metricas.er === null));
assert.ok(perfiles.datos.some((perfil) => perfil.descartado));
assert.ok(perfiles.datos.some((perfil) => !perfil.audiencia.distribucion_edad));
assert.equal((await obtener('/listas/inexistente')).estado, 404);
const validacion = (await obtener('/validacion')).datos;
assert.equal(validacion.filas.length, 102);
assert.equal(validacion.criterios.filter((criterio) => criterio.pasa).length, 4);
for (const criterio of validacion.criterios.slice(0, 5)) {
  const campo = { edad: 'edad', genero: 'genero', ciudad: 'ciudad', followers: 'followers', er: 'er' }[criterio.id];
  const coincidentes = validacion.filas.filter((fila) => fila.coincide[campo]).length;
  assert.equal(coincidentes / 102, criterio.resultado);
}
assert.equal((await crear({ referencia: 'una.demo', usuarios: ['otra.demo'] })).estado, 422);
assert.equal((await crear({ referencia: 'una.demo', reels: 11 })).estado, 422);
const estimacion = await crear({ referencia: 'sintetica.demo', estimar: true, limite: 60, reels: 0, muestra_seguidores: 0 });
assert.equal(estimacion.estado, 202);
const estimada = await obtener(`/listas/${estimacion.datos.id}`);
assert.equal(estimada.datos.estado, 'estimada');
assert.equal(estimada.datos.estimacion.costos_por_paso.reels, 0);
assert.equal(estimada.datos.estimacion.costos_por_paso.seguidores, 0);
const excel = await fetch(`${base}/listas/lista-demo/excel`, { headers: { Authorization: 'Bearer token-sintetico' } });
assert.equal(excel.headers.get('content-type'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
const archivo = Buffer.from(await excel.arrayBuffer());
assert.equal(archivo.subarray(0, 2).toString(), 'PK');
const rutaTemporal = new URL('./verificacion-temporal.xlsx', import.meta.url);
writeFileSync(rutaTemporal, archivo);
try {
  const comprobacion = spawnSync('unzip', ['-t', rutaTemporal.pathname], { encoding: 'utf8' });
  assert.equal(comprobacion.status, 0, comprobacion.stdout);
  const hoja = spawnSync('unzip', ['-p', rutaTemporal.pathname, 'xl/worksheets/sheet1.xml'], { encoding: 'utf8' }).stdout;
  assert.ok(hoja.includes('A1:W61'));
  assert.equal((hoja.match(/<row r=/g) ?? []).length, 61);
} finally { rmSync(rutaTemporal); }
const nueva = await crear({ referencia: 'sintetica.demo', limite: 12, reels: 5, muestra_seguidores: 30, brief: { marca: 'Bruma Estudio' } });
const limitada = await crear({ usuarios: ['alina.sintetica', 'maela.sintetica', 'tiana.sintetica'], presupuesto_usd: 0.05 });
assert.equal((await obtener(`/listas/${nueva.datos.id}`)).datos.estado, 'pendiente');
assert.equal((await obtener(`/listas/${nueva.datos.id}/perfiles`)).estado, 409);
console.log('Mock: historial, perfiles, validación, estimación, errores y Excel verificados. Esperando avance autónomo de 40 s…');
await new Promise((resolver) => setTimeout(resolver, 3100));
assert.equal((await obtener(`/listas/${nueva.datos.id}`)).datos.estado, 'en_proceso');
await new Promise((resolver) => setTimeout(resolver, 37500));
assert.equal((await obtener(`/listas/${nueva.datos.id}`)).datos.estado, 'completa');
assert.equal((await obtener(`/listas/${nueva.datos.id}/perfiles`)).datos.length, 12);
assert.equal((await obtener(`/listas/${limitada.datos.id}`)).datos.estado, 'parcial');
const perfilesLimitados = (await obtener(`/listas/${limitada.datos.id}/perfiles`)).datos;
assert.equal(perfilesLimitados[0].usuario, 'alina.sintetica');
assert.equal(perfilesLimitados.length, 1);
console.log('Mock verificado: pendiente → en_proceso → completa, parcial por presupuesto y usuarios pegados correctos.');
