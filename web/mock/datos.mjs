// Todos los nombres, usuarios y marcas de este archivo son datos sintéticos para la demo.
export const parametrosDemo = {
  referencia: 'casa.bruma', usuarios: null, limite: 60, reels: 5, muestra_seguidores: 30,
  presupuesto_usd: 12, estimar: false, simulado: true,
  brief: { marca: 'Bruma Estudio', publico_objetivo: 'Mujeres de 25 a 34 años en Lima interesadas en diseño y bienestar.', marcas_a_evitar: ['Nébula Taller'], followers_min: 10000, followers_max: 200000 },
};
const nombres = ['Alina Caurí', 'Maela Quisora', 'Liano Tairuma', 'Narela Oquira', 'Elián Mayuri', 'Saira Umalí', 'Tayel Rimora', 'Naia Sullani', 'Irán Caluma', 'Amira Yaurín', 'Celina Aymora', 'Darián Quillora', 'Mirela Tacurí', 'Ilaní Chumaya', 'Lunel Acorí', 'Ariela Munayra', 'Nayel Oruma', 'Celia Aquirí', 'Tiana Rumalí', 'Malén Yacora'];
const categorias = ['Moda', 'Gastronomía', 'Viajes', 'Belleza', 'Fitness', 'Lifestyle', 'Música'];
const ciudades = ['Lima', 'Arequipa', 'Cusco', 'Trujillo', 'Piura'];
const marcas = ['Bruma Estudio', 'Nébula Taller', 'Orilla Suave', 'Savia Lunar', 'Marea Clara', 'Senda Tibia', 'Lino Nube'];
const textos = {
  Moda: 'Prendas con historia, diseño local y un estilo que se siente propio.',
  Gastronomía: 'Sabores de barrio, recetas de casa y rincones por descubrir.',
  Viajes: 'Rutas tranquilas, paisajes cercanos e historias en cada camino.',
  Belleza: 'Rutinas sencillas, cuidado personal y pequeños rituales diarios.',
  Fitness: 'Movimiento consciente, constancia y bienestar sin apuro.',
  Lifestyle: 'Ideas para vivir con calma y disfrutar los pequeños detalles.',
  Música: 'Canciones propias, sesiones acústicas y sonidos de nuestra ciudad.',
};
const redondear = (valor, decimales = 3) => Number(valor.toFixed(decimales));
function usuarioPara(nombre, indice) {
  return `${nombre.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replaceAll(' ', '.')}.demo${indice >= nombres.length ? indice + 1 : ''}`;
}
export function crearPerfiles(cantidad = 60, parametros = parametrosDemo) {
  return Array.from({ length: cantidad }, (_, indice) => {
    const nombre = nombres[indice % nombres.length];
    const categoria = categorias[indice % categorias.length];
    const followers = indice === 0 ? 48200 : 11200 + ((indice * 7919) % 182000);
    const er = indice === 0 ? 0.0388 : redondear(0.012 + ((indice * 7) % 49) / 1000, 4);
    const likes = indice === 0 ? 1830 : Math.round(followers * er * 0.975);
    const comentarios = indice === 0 ? 41 : Math.round(followers * er * 0.025);
    const edad = indice !== 0 && indice % 5 === 0 ? '18-24' : indice % 7 === 0 ? '35-44' : '25-34';
    const genero = indice % 3 === 2 ? 'Male' : 'Female';
    const ciudad = ciudades[indice !== 0 && indice % 5 === 0 ? (indice % 4) + 1 : 0];
    const fueraDeRango = (parametros.brief?.followers_min && followers < parametros.brief.followers_min) || (parametros.brief?.followers_max && followers > parametros.brief.followers_max);
    const descartado = Boolean(indice % 11 === 7 || fueraDeRango);
    const muestra = parametros.muestra_seguidores ?? 30;
    const sinAudiencia = indice === 18;
    const colaboraciones = Array.from({ length: 1 + indice % 3 }, (_, numero) => ({
      nombre: marcas[(indice + numero) % marcas.length], tipo: ['publicidad', 'colab', 'canje'][numero % 3],
      post_evidencia: `https://example.com/evidencia-sintetica/${indice + 1}/${numero + 1}`,
      fecha: ['2026-07-12', '2026-08-24', '2026-10-05'][numero],
    }));
    return {
      numero: indice + 1,
      usuario: parametros.usuarios?.[indice] ?? usuarioPara(nombre, indice),
      nombre: indice < nombres.length ? nombre : `${nombre} ${['Luz', 'Sol', 'Mar'][Math.floor(indice / nombres.length) % 3]}`,
      bio: textos[categoria], verificada: indice % 6 === 0, categoria, followers, descartado,
      metricas: { likes: indice === 14 ? null : likes, comentarios: indice === 14 ? null : comentarios, reel_plays: parametros.reels === 0 || indice === 9 ? null : Math.round(followers * (0.4 + indice % 5 / 10)), engagements: indice === 14 ? null : likes + comentarios, er: indice === 14 ? null : er },
      calidad_audiencia: sinAudiencia ? null : redondear(0.68 + ((indice * 3) % 29) / 100),
      audiencia: {
        edad: sinAudiencia ? null : edad, genero: sinAudiencia ? null : genero, ciudad: sinAudiencia ? null : ciudad,
        fuente: muestra > 0 ? 'seguidores' : 'contenido',
        ...(indice % 8 === 3 || sinAudiencia ? {} : {
          distribucion_edad: edad === '18-24' ? { '18-24': 0.48, '25-34': 0.32, '35-44': 0.14, '45-54': 0.06 } : edad === '35-44' ? { '18-24': 0.14, '25-34': 0.28, '35-44': 0.46, '45-54': 0.12 } : { '18-24': 0.31, '25-34': 0.44, '35-44': 0.15, '45-54': 0.10 },
          distribucion_genero: genero === 'Female' ? { Female: 0.68, Male: 0.32 } : { Female: 0.39, Male: 0.61 },
        }),
      },
      seguidores_muestra: sinAudiencia ? 0 : muestra,
      marcas: colaboraciones,
      menciones: indice % 3 === 0 ? [{ nombre: 'Rama Serena', tipo: 'etiqueta' }, { nombre: 'Viento Manso', tipo: 'amigo_fotografo' }] : [],
      encaje: parametros.brief?.marca || parametros.brief?.publico_objetivo ? (descartado ? 2 : indice % 4 === 0 ? 5 : 3 + indice % 2) : null,
      motivo_encaje: descartado ? 'El contenido o el rango de followers se aleja de lo que busca la marca.' : 'Su comunidad y estilo cercano conectan con el público objetivo del brief.',
      notas: descartado ? [fueraDeRango ? 'Descartado: fuera del rango de followers del brief.' : 'Descartado: el perfil representa principalmente a un negocio.'] : indice % 8 === 3 ? ['La audiencia no incluye una distribución completa.'] : indice === 9 ? ['Sin reels con audio.'] : [],
      costo_usd: redondear(0.04 + (indice % 8) / 1000),
    };
  });
}
export const perfilesDemo = crearPerfiles();
export const pasos = ['seguidos', 'perfiles', 'filtro', 'reels', 'transcripcion', 'seguidores', 'clasificacion', 'excel'];
export function estimarCosto(parametros, cantidad) {
  const porPaso = {
    perfiles: redondear(cantidad * 0.0026),
    reels: redondear(cantidad * (parametros.reels ?? 5) * 0.0021),
    transcripcion: redondear(cantidad * (parametros.reels ?? 5) * 0.0013),
    seguidores: redondear(cantidad * (parametros.muestra_seguidores ?? 30) * 0.00057),
    clasificacion: redondear(cantidad * 0.0123),
  };
  const total = redondear(Object.values(porPaso).reduce((acumulado, monto) => acumulado + monto, 0));
  return { perfiles: cantidad, costo_total_usd: total, costo_por_perfil_usd: cantidad ? redondear(total / cantidad, 4) : 0, costos_por_paso: porPaso };
}
export function corridaTerminada(id, fecha, parametros, perfiles, duracion = 1320, estado = 'completa') {
  const costo = redondear(perfiles.reduce((suma, perfil) => suma + perfil.costo_usd, 0));
  return {
    id, fecha, estado, costo_total_usd: costo,
    finalizada: new Date(Date.parse(fecha) + duracion * 1000).toISOString(),
    corrida: { id, fecha, parametros, duracion_segundos: duracion, perfiles_solicitados: parametros.usuarios?.length ?? parametros.limite ?? 60, perfiles_procesados: perfiles.length, costo_total_usd: costo, costo_por_perfil_usd: perfiles.length ? redondear(costo / perfiles.length, 4) : 0, costos_por_paso: { perfiles: redondear(costo * 0.12), reels: redondear(costo * 0.22), transcripcion: redondear(costo * 0.14), seguidores: redondear(costo * 0.34), clasificacion: redondear(costo * 0.18) }, costos_confirmados: true, ejecucion_simulada: true, estado, notas: ['Datos sintéticos de demostración.'] },
  };
}
export function crearValidacion() {
  const perfiles = crearPerfiles(102);
  const filas = perfiles.map((perfil, indice) => {
    const referencia = { followers: perfil.followers, er: perfil.metricas.er ?? 0.025, edad: perfil.audiencia.edad ?? '25-34', genero: perfil.audiencia.genero ?? 'Female', ciudad: perfil.audiencia.ciudad ?? 'Lima' };
    const coincide = { followers: indice < 99, er: indice < 72, edad: indice < 67, genero: indice < 84, ciudad: indice < 82 };
    const motor = {
      followers: Math.round(referencia.followers * (coincide.followers ? 0.985 : 0.76)),
      er: redondear(referencia.er * (coincide.er ? 0.96 : 0.70), 4),
      edad: coincide.edad ? referencia.edad : referencia.edad === '18-24' ? '25-34' : '18-24',
      genero: coincide.genero ? referencia.genero : referencia.genero === 'Female' ? 'Male' : 'Female',
      ciudad: coincide.ciudad ? referencia.ciudad : referencia.ciudad === 'Lima' ? 'Cusco' : 'Lima',
    };
    return { usuario: perfil.usuario, motor, referencia, coincide, nota: Object.values(coincide).every(Boolean) ? '' : 'Hay diferencias en los valores estimados; revisa la muestra.' };
  });
  return {
    fecha: '2026-10-27T15:30:00Z', perfiles: filas.length,
    criterios: [
      { id: 'followers', nombre: 'Followers', meta: '±10 %', resultado: 99 / 102, formato: 'porcentaje', pasa: true, detalle: '99 de 102 perfiles dentro de ±10 % de la Referencia.' },
      { id: 'er', nombre: 'ER', meta: '±10 %', resultado: 72 / 102, formato: 'porcentaje', pasa: false, detalle: '72 de 102 perfiles dentro de ±10 %. Falta ajustar la ventana de publicaciones.' },
      { id: 'edad', nombre: 'Edad mayoritaria', meta: '≥ 70 %', resultado: 67 / 102, formato: 'porcentaje', pasa: false, detalle: '67 de 102 perfiles coinciden. La muestra aún necesita ampliarse.' },
      { id: 'genero', nombre: 'Género mayoritario', meta: '≥ 70 %', resultado: 84 / 102, formato: 'porcentaje', pasa: true, detalle: '84 de 102 perfiles coinciden con la Referencia.' },
      { id: 'ciudad', nombre: 'Ciudad', meta: '≥ 80 %', resultado: 82 / 102, formato: 'porcentaje', pasa: true, detalle: '82 de 102 perfiles coinciden con la Referencia.' },
      { id: 'tiempo', nombre: 'Lista de 200 sin tocarla', meta: '< 30 min', resultado: 118, formato: 'minutos', pasa: false, detalle: 'La medición en serie tomó 118 minutos; el siguiente ajuste es correr tareas en paralelo.' },
      { id: 'costo', nombre: 'Costo por perfil', meta: '≤ USD 0.06', resultado: 0.048, formato: 'usd', pasa: true, detalle: 'USD 0.048 por perfil en la corrida sintética de validación.' },
    ], filas,
  };
}
