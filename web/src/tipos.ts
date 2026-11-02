export type EstadoCorrida = 'pendiente' | 'en_proceso' | 'completa' | 'parcial' | 'estimada' | 'error' | 'interrumpida';
export type Paso = 'seguidos' | 'perfiles' | 'filtro' | 'reels' | 'transcripcion' | 'seguidores' | 'clasificacion' | 'analisis' | 'excel';

export interface Brief {
  marca: string;
  publico_objetivo: string;
  marcas_a_evitar: string[];
  followers_min?: number;
  followers_max?: number;
}

export interface ParametrosLista {
  referencia?: string | null;
  usuarios?: string[] | null;
  limite?: number;
  reels: number;
  reels_revisar?: number;
  muestra_seguidores: number;
  presupuesto_usd?: number;
  estimar?: boolean;
  simulado?: boolean;
  brief?: Brief;
}

export interface Estimacion {
  perfiles: number;
  costo_total_usd: number;
  costo_por_perfil_usd: number;
  costos_por_paso: Record<string, number>;
}

export interface Corrida {
  id: string;
  fecha: string;
  parametros: Partial<ParametrosLista> & { nombre?: string; metricas_agregacion?: 'promedio' | 'mediana' };
  duracion_segundos: number;
  perfiles_solicitados: number;
  perfiles_procesados: number;
  costo_total_usd: number;
  costo_por_perfil_usd: number;
  costos_por_paso: Record<string, number>;
  costos_confirmados: boolean;
  ejecucion_simulada: boolean;
  estado: EstadoCorrida;
  notas: string[];
}

export interface EstadoLista {
  id: string;
  estado: EstadoCorrida;
  fecha: string;
  finalizada?: string;
  costo_total_usd: number;
  nota?: string;
  progreso?: {
    paso: Paso;
    hechos: number;
    total: number;
    descartados: number;
    /** Avance de toda la lista, 0-100; solo sube. */
    porcentaje?: number;
    en_curso?: number;
    actividad?: string;
  };
  estimacion?: Estimacion;
  corrida?: Corrida;
}

export interface ResumenLista {
  id: string;
  estado: EstadoCorrida;
  fecha: string;
  finalizada?: string;
  fuente: string;
  perfiles_procesados: number | null;
  costo_total_usd: number;
  duracion_segundos: number | null;
  marca: string;
}

export interface Perfil {
  numero: number;
  usuario: string;
  nombre: string | null;
  bio: string | null;
  descripcion?: string | null;
  verificada: boolean;
  categoria: string | null;
  followers: number | null;
  descartado: boolean;
  metricas: {
    likes: number | null;
    comentarios: number | null;
    reel_plays: number | null;
    engagements: number | null;
    er: number | null;
  };
  calidad_audiencia: number | null;
  audiencia: {
    edad: string | null;
    genero: string | null;
    ciudad: string | null;
    fuente: 'seguidores' | 'contenido' | null;
    distribucion_edad?: Record<string, number> | null;
    distribucion_genero?: Record<string, number> | null;
    // Probabilidad que Jev da a cada opción de ser la mayoritaria (no es % de seguidores).
    estimacion?: {
      genero: Record<string, number>;
      edad: Record<string, number>;
      edad_genero: Record<string, { Female: number; Male: number }>;
      ciudad: Record<string, number>;
      pais: Record<string, number>;
    } | null;
  };
  seguidores_muestra: number;
  marcas: {
    nombre: string;
    tipo: 'publicidad' | 'colab' | 'canje';
    post_evidencia: string;
    fecha: string | null;
    tamano?: 'grande' | 'mediana' | 'pequena' | null;
  }[];
  menciones: { nombre: string; tipo: 'etiqueta' | 'amigo_fotografo' }[];
  encaje: number | null;
  motivo_encaje: string;
  notas: string[];
  costo_usd: number;
}

export interface MedidasValidacion {
  followers: number | null;
  er: number | null;
  edad: string | null;
  genero: string | null;
  ciudad: string | null;
}

export interface CriterioValidacion {
  id: string;
  nombre: string;
  meta: string;
  resultado: number | null;
  formato: 'porcentaje' | 'minutos' | 'usd';
  pasa: boolean;
  detalle: string;
}

export interface Validacion {
  fecha: string;
  perfiles: number;
  criterios: CriterioValidacion[];
  filas: {
    usuario: string;
    motor: MedidasValidacion;
    referencia: MedidasValidacion;
    coincide: Record<keyof MedidasValidacion, boolean>;
    nota: string;
  }[];
}
