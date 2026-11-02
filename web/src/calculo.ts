// Costo y tiempo de una lista según la confiabilidad que se quiere (pantalla /calculadora).
// Las tarifas copian motor/precios.yaml; si cambian allá, cambiarlas aquí (o en «Supuestos»).
export const SUPUESTOS = {
  apifyPerfiles: 2.6, apifyReels: 1, apifyReelsMinimo: 0.0073, apifySeguidores: 0.85, groqHora: 0.04, groqMinimo: 10,
  jevMillon: 0.042, tokensPerfil: 30000, segundosReel: 40, loteGroq: 20, segundosLote: 60, arranque: 60, segundosPerfil: 6,
  cambio: 3.45, reparto: 65, tasaPublicidad: 8, revisarBase: 10,
};
export type Supuestos = typeof SUPUESTOS;

// Medido en la caché del motor (188 perfiles, 5,716 seguidores): % de seguidores con género.
export const CON_GENERO = 0.75;
export const MINIMO_SEGUIDORES = 25; // el motor pide al menos 25 si la muestra está activa
export const NIVELES = [{ nombre: 'Decente', confianza: 0.8 }, { nombre: 'Bueno', confianza: 0.9 }, { nombre: 'Costo-beneficio', confianza: 0.95 }, { nombre: 'Máximo', confianza: 0.99 }];

function combinaciones(n: number, k: number) { let r = 1; for (let i = 1; i <= k; i++) r = r * (n - k + i) / i; return r; }
// Probabilidad de que la mayoría de la muestra coincida con la mayoría real.
export function aciertoMayoria(n: number, real: number) {
  let total = 0;
  for (let k = Math.floor(n / 2) + 1; k <= n; k++) total += combinaciones(n, k) * real ** k * (1 - real) ** (n - k);
  return total;
}

// Seguidores a pedir para acertar el género mayoritario con esa confianza (cuenta el 25 % que sale sin género).
export function seguidoresNecesarios(confianza: number, reparto: number) {
  if (reparto <= 0.5) return null;
  let n = 1;
  while (n < 5000 && !(aciertoMayoria(n, reparto) >= confianza && aciertoMayoria(n + 1, reparto) >= confianza)) n++;
  return Math.max(MINIMO_SEGUIDORES, Math.ceil(n / CON_GENERO));
}

// Reels recientes a revisar para encontrar al menos una publicidad con esa confianza, si el creador hace
// publicidad al ritmo medido (8 % de los posts en la caché del motor, 28-oct).
export function revisarNecesarios(confianza: number, tasa: number) {
  return tasa > 0 && tasa < 1 ? Math.ceil(Math.log(1 - confianza) / Math.log(1 - tasa)) : 0;
}

// Igual que el motor: sin reels a transcribir no se revisa ninguno; si no, al menos tantos como se transcriben.
export const reelsARevisar = (reels: number, revisar: number) => reels ? Math.max(reels, revisar) : 0;

export function calcular(perfiles: number, seguidores: number, reels: number, revisar: number, s: Supuestos = SUPUESTOS) {
  const muestra = seguidores ? Math.max(MINIMO_SEGUIDORES, seguidores) : 0;
  const grupo = reelsARevisar(reels, revisar);
  // Solo se transcriben los de publicidad: en promedio, el 8 % de los revisados, con el tope de «reels».
  const transcritos = Math.min(reels, grupo * s.tasaPublicidad / 100);
  const pasos = {
    Seguidores: muestra * s.apifySeguidores / 1000,
    Reels: perfiles && grupo ? Math.max(perfiles * grupo * s.apifyReels / 1000, s.apifyReelsMinimo) / perfiles : 0,
    Perfil: s.apifyPerfiles / 1000,
    Transcripción: transcritos * Math.max(s.segundosReel, s.groqMinimo) * s.groqHora / 3600,
    Jev: s.tokensPerfil * s.jevMillon / 1e6,
  };
  const porPerfil = Object.values(pasos).reduce((a, b) => a + b, 0);
  const lotes = Math.ceil(perfiles * transcritos / s.loteGroq);
  const tiempoGroq = lotes * s.segundosLote;
  // Groq (lotes de 20 por minuto) y el análisis corren a la vez: manda el más lento.
  const tiempo = perfiles ? s.arranque + Math.max(tiempoGroq, perfiles * s.segundosPerfil) : 0;
  return { pasos, porPerfil, porLista: porPerfil * perfiles, transcritos, lotes, tiempo, cuelloGroq: tiempoGroq > perfiles * s.segundosPerfil };
}

// Confiabilidad que dan unas opciones concretas (para comparar con los valores de Nueva lista).
export function confiabilidad(seguidores: number, reels: number, revisar: number, s: Supuestos = SUPUESTOS) {
  const conGenero = Math.round(Math.max(seguidores ? MINIMO_SEGUIDORES : 0, seguidores) * CON_GENERO);
  return { genero: conGenero ? aciertoMayoria(conGenero, s.reparto / 100) : 0,
    publicidad: 1 - (1 - s.tasaPublicidad / 100) ** reelsARevisar(reels, revisar) };
}

export function formatearTiempo(segundos: number) {
  if (segundos < 60) return `${Math.round(segundos)} s`;
  const minutos = Math.round(segundos / 60);
  return minutos < 60 ? `${minutos} min` : `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}

export function formatearSoles(valor: number, decimales = 2) {
  return Number.isFinite(valor) ? `S/ ${valor.toLocaleString('es-PE', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })}` : '—';
}
