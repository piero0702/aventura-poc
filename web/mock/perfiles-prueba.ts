import type { Perfil, EstadoLista } from '../src/tipos';

export const perfilPrueba: Perfil = {
  numero: 1,
  usuario: 'luma.cuaderno',
  nombre: 'Luma Quisvera',
  bio: 'Ideas para vestir con calma.',
  verificada: false,
  categoria: 'Moda',
  followers: 48200,
  descartado: false,
  metricas: { likes: 1830, comentarios: 41, reel_plays: 22100, engagements: 1871, er: 0.0388 },
  calidad_audiencia: 0.83,
  audiencia: { edad: '25-34', genero: 'Female', ciudad: 'Lima', fuente: 'seguidores' },
  seguidores_muestra: 30,
  marcas: [{ nombre: 'Nubelia Taller', tipo: 'colab', post_evidencia: 'https://example.test/evidencia', fecha: '2026-09-14' }],
  menciones: [],
  encaje: 4,
  motivo_encaje: 'Su comunidad coincide con el público del brief.',
  notas: [],
  costo_usd: 0.047,
};

export const perfilesPrueba: Perfil[] = [
  perfilPrueba,
  { ...perfilPrueba, numero: 2, usuario: 'talo.rutas', nombre: 'Talo Anquira', categoria: 'Viajes', followers: 9800, encaje: 2, descartado: true, notas: ['Fuera del rango de followers.'], metricas: { ...perfilPrueba.metricas, er: 0.022 }, audiencia: { ...perfilPrueba.audiencia, edad: '18-24', genero: 'Male', ciudad: 'Arequipa' }, marcas: [] },
  { ...perfilPrueba, numero: 3, usuario: 'savia.mesa', nombre: 'Savia Villunqui', categoria: 'Gastronomía', followers: 77000, encaje: 4, metricas: { ...perfilPrueba.metricas, er: 0.056 }, audiencia: { ...perfilPrueba.audiencia, edad: '35-44', ciudad: 'Cusco' }, marcas: [] },
  { ...perfilPrueba, numero: 4, usuario: 'nela.taller', nombre: 'Nela Corvani', followers: null, encaje: null, metricas: { likes: null, comentarios: null, reel_plays: null, engagements: null, er: null }, audiencia: { edad: null, genero: null, ciudad: null, fuente: null }, marcas: [] },
];

export const etapasPrueba: EstadoLista[] = [
  { id: 'lista-prueba', estado: 'pendiente', fecha: '2026-10-27T15:00:00Z', costo_total_usd: 0 },
  { id: 'lista-prueba', estado: 'en_proceso', fecha: '2026-10-27T15:00:00Z', costo_total_usd: 0.12, progreso: { paso: 'perfiles', hechos: 10, total: 60, descartados: 1 } },
  { id: 'lista-prueba', estado: 'completa', fecha: '2026-10-27T15:00:00Z', finalizada: '2026-10-27T15:00:40Z', costo_total_usd: 2.88 },
];

export const entradasUsuariosPrueba = {
  mixta: '@LUMA.CUADERNO\nhttps://www.instagram.com/talo.rutas/?igsh=ejemplo\ninstagram.com/savia.mesa\n@luma.cuaderno',
  esperada: ['luma.cuaderno', 'talo.rutas', 'savia.mesa'],
  separadores: 'luma.cuaderno, @talo.rutas; savia.mesa',
  rutasInvalidas: 'https://instagram.com/luma.cuaderno/reels/ https://instagram.com/talo.rutas/publicacion/ https://instagram.com/reel https://instagram.com/stories/ https://instagram.com/explore/ https://instagram.com/accounts/ https://instagram.com/direct/',
  reservadosSinURL: '@p @reel @reels @stories @explore @accounts @direct',
  reservadosEsperados: ['p', 'reel', 'reels', 'stories', 'explore', 'accounts', 'direct'],
  invalida: 'https://otro.example/usuario nombre-invalido usuario..doble @ .usuario usuario. https://instagram.com/p/ejemplo',
};

export const formularioPrueba = {
  referencia: 'https://www.instagram.com/casa.bruma/?igsh=ejemplo',
  marca: 'Bruma Estudio',
  publico: 'Personas de 25 a 34 años en Lima',
  marcaPendiente: 'Nubelia Taller',
};

export const estimacionPrueba: EstadoLista = {
  id: 'estimacion-prueba', estado: 'estimada', fecha: '2026-10-27T15:00:00Z', costo_total_usd: 9.8,
  estimacion: { perfiles: 200, costo_total_usd: 9.8, costo_por_perfil_usd: 0.049, costos_por_paso: { perfiles: 0.52, reels: 2.1, transcripcion: 1.3, seguidores: 3.4, clasificacion: 2.48 } },
};
