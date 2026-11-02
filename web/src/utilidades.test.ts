import { describe, expect, it } from 'vitest';
import { entradasUsuariosPrueba, perfilesPrueba } from '../mock/perfiles-prueba';
import { filtrarPerfiles, filtrosIniciales, formatearDuracion, formatearER, formatearFecha, formatearFollowers, formatearUSD, normalizarUsuarios, ordenarPerfiles, parametrosParaReintentar } from './utilidades';
import type { FiltrosResultados } from './utilidades';
import type { Corrida } from './tipos';

function usuariosCon(filtros: Partial<FiltrosResultados>) {
  return filtrarPerfiles(perfilesPrueba, { ...filtrosIniciales, ...filtros }).map((perfil) => perfil.usuario);
}

describe('reintento de una corrida con metadatos', () => {
  it('solo envía parámetros admitidos y conserva el modo simulado', () => {
    const corrida: Corrida = {
      id: 'corrida-sintetica', fecha: '2026-10-27T15:00:00Z', estado: 'error',
      parametros: { referencia: 'cuenta.sintetica', reels: 0, muestra_seguidores: 0, presupuesto_usd: 0, limite: 3, nombre: 'Lista CLI', metricas_agregacion: 'mediana' },
      duracion_segundos: 0, perfiles_solicitados: 3, perfiles_procesados: 0, costo_total_usd: 0, costo_por_perfil_usd: 0,
      costos_por_paso: {}, costos_confirmados: true, ejecucion_simulada: true, notas: [],
    };
    expect(parametrosParaReintentar(corrida)).toEqual({ referencia: 'cuenta.sintetica', reels: 0, muestra_seguidores: 0, presupuesto_usd: 0, limite: 3, estimar: false, simulado: true });
    expect(parametrosParaReintentar(undefined)).toBeNull();
    expect(parametrosParaReintentar({ ...corrida, parametros: { nombre: 'Sin fuente' } })).toBeNull();
  });
});

describe('normalización de usuarios pegados', () => {
  it('acepta arrobas, URLs de perfil y elimina repetidos sin alterar el orden', () => {
    expect(normalizarUsuarios(entradasUsuariosPrueba.mixta)).toEqual(entradasUsuariosPrueba.esperada);
  });
  it('acepta separadores y descarta entradas inválidas y enlaces a publicaciones', () => {
    expect(normalizarUsuarios(entradasUsuariosPrueba.separadores)).toEqual(entradasUsuariosPrueba.esperada);
    expect(normalizarUsuarios(entradasUsuariosPrueba.invalida)).toEqual([]);
    expect(normalizarUsuarios('')).toEqual([]);
    expect(normalizarUsuarios(entradasUsuariosPrueba.rutasInvalidas)).toEqual([]);
  });
  it('restringe las rutas reservadas solo en URLs, sin descartar usuarios pegados', () => {
    expect(normalizarUsuarios(entradasUsuariosPrueba.reservadosSinURL)).toEqual(entradasUsuariosPrueba.reservadosEsperados);
  });
});

describe('formato de cifras', () => {
  it('respeta los formatos solicitados', () => {
    expect(formatearFollowers(48200)).toBe('48.2 k');
    expect(formatearER(0.0388)).toBe('3.88 %');
    expect(formatearUSD(0.048)).toBe('USD 0.048');
    expect(formatearUSD(8.9, 2)).toBe('USD 8.90');
  });
  it('conserva ceros y representa valores ausentes con una raya', () => {
    expect(formatearFollowers(0)).toBe('0');
    expect(formatearER(0)).toBe('0.00 %');
    expect(formatearUSD(0)).toBe('USD 0.000');
    expect(formatearFollowers(null)).toBe('—');
    expect(formatearER(null)).toBe('—');
    expect(formatearUSD(null)).toBe('—');
    expect(formatearDuracion(1320)).toBe('22 min');
    expect(formatearFecha(null)).toBe('—');
    expect(formatearFecha('fecha-invalida')).toBe('—');
  });
});

describe('filtros de resultados', () => {
  it('oculta descartados por defecto y permite incluirlos', () => {
    expect(usuariosCon({})).toHaveLength(3);
    expect(usuariosCon({ ocultarDescartados: false })).toHaveLength(4);
  });
  it('busca por nombre sin tildes o por usuario con arroba', () => {
    expect(usuariosCon({ busqueda: 'LUMA' })).toEqual([perfilesPrueba[0].usuario]);
    expect(usuariosCon({ busqueda: `@${perfilesPrueba[2].usuario}` })).toEqual([perfilesPrueba[2].usuario]);
  });
  it('combina rango de followers, ER mínimo y categorías sin inventar datos nulos', () => {
    expect(usuariosCon({ followersMin: '40000', followersMax: '50000', erMin: '3', categorias: ['Moda', 'Viajes'] })).toEqual([perfilesPrueba[0].usuario]);
    expect(usuariosCon({ erMin: '5' })).toEqual([perfilesPrueba[2].usuario]);
    expect(usuariosCon({ followersMax: '100000' })).not.toContain(perfilesPrueba[3].usuario);
  });
  it('combina demografía y encaje mínimo', () => {
    expect(usuariosCon({ genero: 'Female', edad: '25-34', ciudad: 'lima', encajeMin: '4' })).toEqual([perfilesPrueba[0].usuario]);
    expect(usuariosCon({ genero: 'Male', edad: '18-24', ciudad: 'Arequipa', ocultarDescartados: false })).toEqual([perfilesPrueba[1].usuario]);
    expect(usuariosCon({ encajeMin: '5' })).toEqual([]);
  });
  it('excluye colaboraciones con marcas del brief y permite limpiar los filtros', () => {
    const marca = perfilesPrueba[0].marcas[0].nombre.toUpperCase();
    expect(usuariosCon({ excluirMarcas: true, marcasAEvitar: [marca] })).not.toContain(perfilesPrueba[0].usuario);
    expect(usuariosCon({ excluirMarcas: false, marcasAEvitar: [marca] })).toContain(perfilesPrueba[0].usuario);
    expect(filtrarPerfiles(perfilesPrueba, filtrosIniciales)).toHaveLength(3);
  });
});

describe('orden de perfiles', () => {
  it('ordena por encaje y luego ER, dejando los datos ausentes al final', () => {
    expect(ordenarPerfiles(perfilesPrueba).map((perfil) => perfil.numero)).toEqual([3, 1, 2, 4]);
    expect(ordenarPerfiles(perfilesPrueba, 'followers', 'asc').map((perfil) => perfil.numero)).toEqual([2, 1, 3, 4]);
  });
  it('permite ordenar columnas anidadas sin mutar la lista original', () => {
    expect(ordenarPerfiles(perfilesPrueba, 'metricas.er', 'desc').map((perfil) => perfil.numero)).toEqual([3, 1, 2, 4]);
    expect(perfilesPrueba.map((perfil) => perfil.numero)).toEqual([1, 2, 3, 4]);
  });
});
