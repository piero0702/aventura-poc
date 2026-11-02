import { createServer } from 'node:http';
import { randomUUID } from 'node:crypto';
import { crearPerfiles, parametrosDemo, perfilesDemo, pasos, corridaTerminada, estimarCosto, crearValidacion } from './datos.mjs';
import { crearExcel } from './excel.mjs';

const puerto = Number(process.env.MOCK_PUERTO ?? 8000);
const listas = new Map();
function guardarLista(resumen, parametros, perfiles) {
  listas.set(resumen.id, { resumen, parametros, perfiles });
}
guardarLista(corridaTerminada('lista-demo', '2026-10-27T14:00:00Z', parametrosDemo, perfilesDemo), parametrosDemo, perfilesDemo);
const parametrosParciales = { ...parametrosDemo, referencia: 'orilla.suave.demo', presupuesto_usd: 1.06, brief: { ...parametrosDemo.brief, marca: 'Orilla Suave' } };
const perfilesParciales = crearPerfiles(24, parametrosParciales);
guardarLista({ ...corridaTerminada('lista-parcial', '2026-10-26T17:10:00Z', parametrosParciales, perfilesParciales, 612, 'parcial'), nota: 'Llegamos al presupuesto indicado. Estos 24 perfiles ya están listos para revisar.' }, parametrosParciales, perfilesParciales);
const parametrosError = { ...parametrosDemo, referencia: 'senda.tibia.demo', brief: { ...parametrosDemo.brief, marca: 'Senda Tibia' } };
guardarLista({ ...corridaTerminada('lista-error', '2026-10-25T14:00:00Z', parametrosError, [], 22, 'error'), nota: 'No pudimos acceder a la cuenta de referencia. Comprueba el usuario y vuelve a intentarlo.' }, parametrosError, []);
const parametrosInterrumpidos = { ...parametrosDemo, referencia: 'marea.clara.demo', brief: { ...parametrosDemo.brief, marca: 'Marea Clara' } };
const interrumpida = corridaTerminada('lista-interrumpida', '2026-10-24T16:00:00Z', parametrosInterrumpidos, [], 180, 'interrumpida');
interrumpida.costo_total_usd = 0.18;
interrumpida.corrida.costo_total_usd = 0.18;
interrumpida.corrida.costos_por_paso = { perfiles: 0.18 };
guardarLista({ ...interrumpida, nota: 'La conexión con el servicio se interrumpió. Puedes volver a armar la lista.' }, parametrosInterrumpidos, []);

function actualizar(lista) {
  if (lista.inicio === undefined || lista.resumen.estado === 'estimada') return lista.resumen;
  const segundos = (Date.now() - lista.inicio) / 1000;
  const cantidad = lista.perfiles.length;
  const total = lista.perfiles.reduce((suma, perfil) => suma + perfil.costo_usd, 0);
  const duracion = lista.parametros.presupuesto_usd !== undefined && total > lista.parametros.presupuesto_usd ? Math.max(2, 40 * lista.parametros.presupuesto_usd / total) : 40;
  if (segundos >= duracion) {
    const excedePresupuesto = lista.parametros.presupuesto_usd !== undefined && total > lista.parametros.presupuesto_usd;
    let perfiles = lista.perfiles;
    if (excedePresupuesto) {
      let gastado = 0;
      perfiles = lista.perfiles.filter((perfil) => {
        if (gastado + perfil.costo_usd > lista.parametros.presupuesto_usd) return false;
        gastado += perfil.costo_usd;
        return true;
      });
    }
    lista.perfiles = perfiles;
    lista.resumen = corridaTerminada(lista.resumen.id, lista.resumen.fecha, lista.parametros, perfiles, duracion, excedePresupuesto ? 'parcial' : 'completa');
    if (excedePresupuesto) lista.resumen.nota = 'Llegamos al presupuesto indicado. Puedes descargar los perfiles que alcanzamos a procesar.';
    delete lista.inicio;
    return lista.resumen;
  }
  const hecho = Math.min(cantidad, Math.floor(cantidad * segundos / 40));
  const costoFinal = lista.perfiles.reduce((suma, perfil) => suma + perfil.costo_usd, 0);
  lista.resumen.estado = segundos < 2 ? 'pendiente' : 'en_proceso';
  lista.resumen.costo_total_usd = Number((costoFinal * segundos / 40).toFixed(3));
  lista.resumen.progreso = { paso: pasos[Math.min(7, Math.floor(segundos / 5))], hechos: hecho, total: cantidad, descartados: lista.perfiles.slice(0, hecho).filter((perfil) => perfil.descartado).length };
  return lista.resumen;
}
function historial() {
  return [...listas.values()].map((lista) => {
    const resumen = actualizar(lista);
    return { id: resumen.id, estado: resumen.estado, fecha: resumen.fecha, ...(resumen.finalizada ? { finalizada: resumen.finalizada } : {}), fuente: lista.parametros.referencia ? `@${lista.parametros.referencia}` : `${lista.parametros.usuarios?.length ?? 0} usuarios pegados`, perfiles_procesados: resumen.corrida?.perfiles_procesados ?? resumen.progreso?.hechos ?? 0, costo_total_usd: resumen.costo_total_usd, duracion_segundos: resumen.corrida?.duracion_segundos ?? (resumen.finalizada ? (Date.parse(resumen.finalizada) - Date.parse(resumen.fecha)) / 1000 : Math.floor((Date.now() - Date.parse(resumen.fecha)) / 1000)), marca: lista.parametros.brief?.marca ?? '' };
  }).sort((primera, segunda) => segunda.fecha.localeCompare(primera.fecha));
}
function responder(respuesta, estado, datos) {
  respuesta.writeHead(estado, { 'Content-Type': 'application/json; charset=utf-8' });
  respuesta.end(JSON.stringify(datos));
}
async function leerCuerpo(peticion) {
  let texto = '';
  for await (const parte of peticion) {
    texto += parte;
    if (texto.length > 150000) throw new Error('La lista es demasiado larga. Pega hasta 1000 usuarios.');
  }
  try { return JSON.parse(texto); } catch { throw new Error('El formulario no tiene un formato válido.'); }
}
function validar(parametros) {
  if (!parametros || typeof parametros !== 'object' || Array.isArray(parametros)) return 'Envía un formulario válido.';
  const referencia = typeof parametros.referencia === 'string' && parametros.referencia.trim().length > 0;
  const usuarios = Array.isArray(parametros.usuarios) && parametros.usuarios.length > 0;
  if (Boolean(referencia) === Boolean(usuarios)) return 'Ingresa una cuenta de referencia o una lista de usuarios, solo una de las dos.';
  if (referencia && !/^[a-zA-Z0-9._]{1,30}$/.test(parametros.referencia)) return 'La cuenta de referencia no tiene un usuario válido.';
  if (usuarios && (parametros.usuarios.length > 1000 || parametros.usuarios.some((usuario) => typeof usuario !== 'string' || !/^[a-zA-Z0-9._]{1,30}$/.test(usuario)))) return 'Revisa los usuarios: usa solo letras, números, puntos y guiones bajos (hasta 30 caracteres).';
  for (const [campo, minimo, maximo] of [['reels', 0, 10], ['muestra_seguidores', 0, 1000], ['limite', 1, 1000]]) {
    if (parametros[campo] !== undefined && (!Number.isInteger(parametros[campo]) || parametros[campo] < minimo || parametros[campo] > maximo)) return `Revisa ${campo}: debe estar entre ${minimo} y ${maximo}.`;
  }
  if (parametros.presupuesto_usd !== undefined && (typeof parametros.presupuesto_usd !== 'number' || !Number.isFinite(parametros.presupuesto_usd) || parametros.presupuesto_usd <= 0)) return 'El presupuesto debe ser mayor que cero.';
  if (parametros.brief !== undefined && (parametros.brief === null || typeof parametros.brief !== 'object' || Array.isArray(parametros.brief))) return 'Revisa el brief de la marca.';
  for (const campo of ['estimar', 'simulado']) {
    if (parametros[campo] !== undefined && typeof parametros[campo] !== 'boolean') return `Revisa ${campo}: debe ser verdadero o falso.`;
  }
  for (const campo of ['marca', 'publico_objetivo']) {
    if (parametros.brief?.[campo] !== undefined && typeof parametros.brief[campo] !== 'string') return 'Revisa los textos del brief de la marca.';
  }
  for (const campo of ['followers_min', 'followers_max']) {
    if (parametros.brief?.[campo] !== undefined && (!Number.isInteger(parametros.brief[campo]) || parametros.brief[campo] < 0)) return 'El rango de followers debe usar números enteros desde cero.';
  }
  if (parametros.brief?.marcas_a_evitar !== undefined && (!Array.isArray(parametros.brief.marcas_a_evitar) || parametros.brief.marcas_a_evitar.some((marca) => typeof marca !== 'string'))) return 'Revisa la lista de marcas a evitar.';
  if (parametros.brief?.followers_min !== undefined && parametros.brief?.followers_max !== undefined && parametros.brief.followers_min > parametros.brief.followers_max) return 'El mínimo de followers no puede superar el máximo.';
  return null;
}

export const servidor = createServer(async (peticion, respuesta) => {
  respuesta.setHeader('Access-Control-Allow-Origin', '*');
  respuesta.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
  respuesta.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  if (peticion.method === 'OPTIONS') { respuesta.writeHead(204); respuesta.end(); return; }
  if (!/^Bearer\s+\S+/i.test(peticion.headers.authorization ?? '')) { responder(respuesta, 401, { detail: 'Falta el token de acceso. Envía Authorization: Bearer con cualquier token sintético para usar el mock.' }); return; }
  const url = new URL(peticion.url ?? '/', 'http://127.0.0.1');
  const ruta = url.pathname.replace(/\/$/, '') || '/';
  try {
    if (peticion.method === 'GET' && ruta === '/validacion') {
      if (process.env.MOCK_SIN_VALIDACION === '1') { responder(respuesta, 404, { detail: 'Aún no corremos la validación.' }); return; }
      responder(respuesta, 200, crearValidacion()); return;
    }
    if (ruta === '/listas' && peticion.method === 'GET') { responder(respuesta, 200, historial()); return; }
    if (ruta === '/listas' && peticion.method === 'POST') {
      const parametros = await leerCuerpo(peticion);
      const error = validar(parametros);
      if (error) { responder(respuesta, 422, { detail: error }); return; }
      const id = randomUUID();
      const cantidad = parametros.usuarios?.length ?? parametros.limite ?? 60;
      const fecha = new Date().toISOString();
      const resumen = { id, estado: parametros.estimar ? 'estimada' : 'pendiente', fecha, costo_total_usd: 0 };
      if (parametros.estimar) resumen.estimacion = estimarCosto(parametros, cantidad);
      const lista = { resumen, parametros, perfiles: parametros.estimar ? [] : crearPerfiles(cantidad, parametros) };
      if (!parametros.estimar) lista.inicio = Date.now();
      listas.set(id, lista);
      responder(respuesta, 202, { id, estado: 'pendiente' }); return;
    }
    const coincidencia = /^\/listas\/([^/]+)(?:\/(perfiles|excel))?$/.exec(ruta);
    if (peticion.method === 'GET' && coincidencia) {
      const lista = listas.get(decodeURIComponent(coincidencia[1]));
      if (!lista) { responder(respuesta, 404, { detail: 'No encontramos esta lista. Vuelve a Mis listas para elegir otra.' }); return; }
      const resumen = actualizar(lista);
      if (!coincidencia[2]) { responder(respuesta, 200, resumen); return; }
      if (!['completa', 'parcial'].includes(resumen.estado)) { responder(respuesta, 409, { detail: 'La lista todavía no terminó. En unos momentos podrás revisar los perfiles.' }); return; }
      if (coincidencia[2] === 'perfiles') { responder(respuesta, 200, lista.perfiles); return; }
      const archivo = crearExcel(lista.perfiles);
      respuesta.writeHead(200, { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': `attachment; filename="lista-${lista.parametros.referencia ?? 'usuarios'}-${resumen.fecha.slice(0, 10)}.xlsx"`, 'Content-Length': archivo.length });
      respuesta.end(archivo); return;
    }
    responder(respuesta, 404, { detail: 'Esta ruta no está disponible en el mock.' });
  } catch (error) {
    responder(respuesta, 422, { detail: error instanceof Error ? error.message : 'No pudimos leer el formulario.' });
  }
});
servidor.listen(puerto, '127.0.0.1', () => console.log(`Mock de Radar listo en http://127.0.0.1:${puerto} · datos sintéticos · lista de muestra: lista-demo`));
