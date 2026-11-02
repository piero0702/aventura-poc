import type { EstadoCorrida, EstadoLista, ParametrosLista, Perfil, ResumenLista, Validacion } from './tipos';

export class ErrorAPI extends Error {
  readonly estado: number;

  constructor(mensaje: string, estado: number) {
    super(mensaje);
    this.name = 'ErrorAPI';
    this.estado = estado;
  }
}

function mensajeError(estado: number, detalle: unknown): string {
  if (estado === 401 || estado === 403) return 'No pudimos conectar con el motor. Revisa el token configurado y vuelve a intentarlo.';
  if ([500, 502, 503, 504].includes(estado) && typeof detalle !== 'string') return 'El motor no está encendido. Inicia el motor y vuelve a intentarlo.';
  if (estado === 404) return 'No encontramos la información que buscas.';
  if (estado === 409) return 'La lista todavía está en proceso. Espera un momento y vuelve a intentarlo.';
  if (estado === 422) return 'Revisa los datos: elige una cuenta o usuarios válidos y comprueba los límites de las opciones.';
  if (typeof detalle === 'string' && /[áéíóúñ¿¡]|lista|perfil|error|encontr|intenta|válid/iu.test(detalle)) return detalle;
  return 'El motor no pudo completar la solicitud. Vuelve a intentarlo en un momento.';
}

async function solicitar(ruta: string, opciones: RequestInit = {}): Promise<Response> {
  const token = import.meta.env.VITE_MOTOR_TOKEN?.trim();
  if (!token) throw new ErrorAPI('Falta el token del motor. Configura VITE_MOTOR_TOKEN en web/.env.local y reinicia la web.', 0);
  const encabezados = new Headers(opciones.headers);
  encabezados.set('Authorization', `Bearer ${token}`);
  if (opciones.body) encabezados.set('Content-Type', 'application/json');
  let respuesta: Response;
  try {
    respuesta = await fetch(`/api${ruta}`, { ...opciones, headers: encabezados });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new ErrorAPI('El motor no está encendido. Inicia el motor y vuelve a intentarlo.', 0);
  }
  if (!respuesta.ok) {
    let detalle: unknown;
    try {
      const cuerpo = await respuesta.json() as { detail?: unknown };
      detalle = cuerpo.detail;
    } catch {
      detalle = undefined;
    }
    throw new ErrorAPI(mensajeError(respuesta.status, detalle), respuesta.status);
  }
  return respuesta;
}

async function recibir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  return await (await solicitar(ruta, opciones)).json() as T;
}

export function crearLista(parametros: ParametrosLista, signal?: AbortSignal): Promise<{ id: string; estado: EstadoCorrida }> {
  return recibir('/listas', { method: 'POST', body: JSON.stringify(parametros), signal });
}

export function obtenerLista(id: string, signal?: AbortSignal): Promise<EstadoLista> {
  return recibir(`/listas/${encodeURIComponent(id)}`, { signal });
}

export function obtenerListas(signal?: AbortSignal): Promise<ResumenLista[]> {
  return recibir('/listas', { signal });
}

export function obtenerPerfiles(id: string, signal?: AbortSignal): Promise<Perfil[]> {
  return recibir(`/listas/${encodeURIComponent(id)}/perfiles`, { signal });
}

export function obtenerValidacion(signal?: AbortSignal): Promise<Validacion> {
  return recibir('/validacion', { signal });
}

export async function descargarExcel(id: string, fuente: string, fecha: string): Promise<void> {
  const respuesta = await solicitar(`/listas/${encodeURIComponent(id)}/excel`);
  const archivo = await respuesta.blob();
  const url = URL.createObjectURL(archivo);
  const enlace = document.createElement('a');
  const nombreFuente = fuente.replace(/^@/u, '').replace(/[^a-z0-9_.-]/giu, '-').slice(0, 80) || 'perfiles';
  enlace.href = url;
  enlace.download = `lista-${nombreFuente}-${fecha.slice(0, 10)}.xlsx`;
  document.body.append(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
