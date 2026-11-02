import type { Brief, Corrida, ParametrosLista, Perfil } from './tipos';

export function tieneBrief(brief: Partial<Brief> | undefined): boolean {
  return Boolean(brief && (brief.marca?.trim() || brief.publico_objetivo?.trim() || brief.marcas_a_evitar?.length || brief.followers_min || brief.followers_max != null));
}

export function parametrosParaReintentar(corrida: Corrida | undefined): ParametrosLista | null {
  const parametros = corrida?.parametros;
  if (!corrida || !parametros || (!parametros.referencia && !parametros.usuarios?.length)) return null;
  return {
    ...(parametros.referencia ? { referencia: parametros.referencia } : { usuarios: parametros.usuarios }),
    reels: parametros.reels ?? 5,
    muestra_seguidores: parametros.muestra_seguidores ?? 30,
    ...(parametros.limite != null && { limite: parametros.limite }),
    ...(parametros.presupuesto_usd != null && { presupuesto_usd: parametros.presupuesto_usd }),
    ...(parametros.brief && { brief: parametros.brief }),
    estimar: false,
    simulado: corrida.ejecucion_simulada,
  };
}

export function normalizarUsuarios(texto: string): string[] {
  const usuarios = texto.split(/[\s,;]+/u).map((entrada) => {
    let usuario = entrada.trim().toLowerCase();
    if (/^(?:https?:\/\/)?(?:www\.)?instagram\.com\//u.test(usuario)) {
      const ruta = usuario.replace(/^(?:https?:\/\/)?(?:www\.)?instagram\.com\//u, '');
      const perfil = /^([^/?#]+)\/?(?:[?#].*)?$/u.exec(ruta);
      if (!perfil || ['p', 'reel', 'reels', 'stories', 'explore', 'accounts', 'direct'].includes(perfil[1])) return '';
      usuario = perfil[1];
    }
    return usuario.replace(/^@+/u, '');
  }).filter((usuario) => /^[a-z0-9_](?:[a-z0-9_.]{0,28}[a-z0-9_])?$/u.test(usuario) && !usuario.includes('..'));
  return [...new Set(usuarios)];
}

export function formatearFollowers(valor: number | null | undefined): string {
  if (valor == null || !Number.isFinite(valor)) return '—';
  if (Math.abs(valor) >= 1_000_000) return `${(valor / 1_000_000).toFixed(1)} M`;
  if (Math.abs(valor) >= 1_000) return `${(valor / 1_000).toFixed(1)} k`;
  return String(Math.round(valor));
}

export function formatearER(valor: number | null | undefined): string {
  return valor == null || !Number.isFinite(valor) ? '—' : `${(valor * 100).toFixed(2)} %`;
}

export function formatearUSD(valor: number | null | undefined, decimales = 3): string {
  return valor == null || !Number.isFinite(valor) ? '—' : `USD ${valor.toFixed(decimales)}`;
}

export function formatearDuracion(segundos: number | null | undefined): string {
  if (segundos == null || !Number.isFinite(segundos)) return '—';
  const total = Math.max(0, Math.floor(segundos));
  if (total < 60) return `${total} s`;
  if (total < 3600) return `${Math.floor(total / 60)} min${total % 60 ? ` ${total % 60} s` : ''}`;
  return `${Math.floor(total / 3600)} h ${Math.floor((total % 3600) / 60)} min`;
}

export function formatearFecha(fecha: string | null | undefined): string {
  if (!fecha) return '—';
  const valor = new Date(fecha);
  return Number.isNaN(valor.getTime()) ? '—' : new Intl.DateTimeFormat('es-PE', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'America/Lima' }).format(valor);
}

export function generoTexto(genero: string | null | undefined): string {
  if (!genero) return '—';
  return ({ Female: 'Mujeres', Male: 'Hombres', Other: 'Otros' } as Record<string, string>)[genero] ?? genero;
}

export interface FiltrosResultados {
  busqueda: string;
  followersMin: string;
  followersMax: string;
  erMin: string;
  categorias: string[];
  genero: string;
  edad: string;
  ciudad: string;
  encajeMin: string;
  ocultarDescartados: boolean;
  excluirMarcas: boolean;
  marcasAEvitar: string[];
}

export type FiltrosPerfiles = FiltrosResultados;

export const filtrosIniciales: FiltrosResultados = {
  busqueda: '', followersMin: '', followersMax: '', erMin: '', categorias: [], genero: '', edad: '', ciudad: '', encajeMin: '', ocultarDescartados: true, excluirMarcas: false, marcasAEvitar: [],
};

function textoComparable(texto: string): string {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/gu, '').trim().toLowerCase();
}

export function filtrarPerfiles(perfiles: Perfil[], filtros: FiltrosResultados): Perfil[] {
  const busqueda = textoComparable(filtros.busqueda).replace(/^@/u, '');
  const marcas = filtros.marcasAEvitar.map(textoComparable);
  return perfiles.filter((perfil) => {
    if (busqueda && !textoComparable(`${perfil.nombre} ${perfil.usuario}`).includes(busqueda)) return false;
    if (filtros.ocultarDescartados && perfil.descartado) return false;
    if (filtros.followersMin && (perfil.followers == null || perfil.followers < Number(filtros.followersMin))) return false;
    if (filtros.followersMax && (perfil.followers == null || perfil.followers > Number(filtros.followersMax))) return false;
    if (filtros.erMin && (perfil.metricas.er == null || perfil.metricas.er * 100 < Number(filtros.erMin))) return false;
    if (filtros.categorias.length && (!perfil.categoria || !filtros.categorias.includes(perfil.categoria))) return false;
    if (filtros.genero && perfil.audiencia.genero !== filtros.genero) return false;
    if (filtros.edad && perfil.audiencia.edad !== filtros.edad) return false;
    if (filtros.ciudad && textoComparable(perfil.audiencia.ciudad ?? '') !== textoComparable(filtros.ciudad)) return false;
    if (filtros.encajeMin && (perfil.encaje == null || perfil.encaje < Number(filtros.encajeMin))) return false;
    if (filtros.excluirMarcas && perfil.marcas.some((marca) => marcas.includes(textoComparable(marca.nombre)))) return false;
    return true;
  });
}

function valorColumna(perfil: Perfil, columna: string): string | number | null {
  const anidada = columna.split('.');
  if (anidada[0] === 'metricas') return perfil.metricas[anidada[1] as keyof Perfil['metricas']] ?? null;
  if (anidada[0] === 'audiencia') return perfil.audiencia[anidada[1] as 'edad' | 'genero' | 'ciudad'] ?? null;
  if (['er', 'likes', 'comentarios', 'engagements', 'reel_plays'].includes(columna)) return perfil.metricas[columna as keyof Perfil['metricas']];
  if (['edad', 'genero', 'ciudad'].includes(columna)) return perfil.audiencia[columna as 'edad' | 'genero' | 'ciudad'];
  if (columna === 'marcas') return perfil.marcas.map((marca) => marca.nombre).join(', ');
  const valor = perfil[columna as keyof Perfil];
  return typeof valor === 'number' || typeof valor === 'string' ? valor : null;
}

export function ordenarPerfiles(perfiles: Perfil[], columna = 'encaje', direccion: 'asc' | 'desc' = 'desc'): Perfil[] {
  return [...perfiles].sort((primero, segundo) => {
    const a = valorColumna(primero, columna);
    const b = valorColumna(segundo, columna);
    if (a == null && b == null) return (segundo.metricas.er ?? -1) - (primero.metricas.er ?? -1);
    if (a == null) return 1;
    if (b == null) return -1;
    const diferencia = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b), 'es-PE', { numeric: true });
    return diferencia ? diferencia * (direccion === 'asc' ? 1 : -1) : (segundo.metricas.er ?? -1) - (primero.metricas.er ?? -1);
  });
}
