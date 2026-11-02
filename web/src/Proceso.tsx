import { useEffect, useState } from 'react';
import { ArrowRight, Clock3, FileSpreadsheet, ScanLine, ShieldCheck } from 'lucide-react';
import { Chip, CifraGrande, Etiqueta, Monograma, Tarjeta } from './componentes';
import { formatearDuracion, formatearUSD } from './utilidades';
import type { EstadoLista, Paso } from './tipos';

// Fases de toda la lista. Perfiles y reels van en lote; el análisis corre varios perfiles a la vez.
const fases: { id: Paso; nombre: string; detalle: string; incluye: Paso[] }[] = [
  { id: 'seguidos', nombre: 'Seguidos', detalle: 'Buscamos los perfiles que sigue tu cuenta de referencia.', incluye: ['seguidos'] },
  { id: 'perfiles', nombre: 'Perfiles', detalle: 'Leemos la información y las métricas de todos los perfiles a la vez.', incluye: ['perfiles', 'filtro'] },
  { id: 'reels', nombre: 'Reels', detalle: 'Reunimos los reels más vistos de cada perfil.', incluye: ['reels'] },
  { id: 'analisis', nombre: 'Análisis', detalle: 'Transcribimos reels, estimamos la audiencia y buscamos marcas, varios perfiles a la vez.', incluye: ['analisis', 'transcripcion', 'seguidores', 'clasificacion'] },
  { id: 'excel', nombre: 'Excel', detalle: 'Damos los últimos toques a tu lista y preparamos el archivo.', incluye: ['excel'] },
];

export default function Proceso({ lista, navegar }: { lista: EstadoLista; navegar: (ruta: string) => void }) {
  const [ahora, establecerAhora] = useState(Date.now());
  useEffect(() => { const reloj = setInterval(() => establecerAhora(Date.now()), 1000); return () => clearInterval(reloj); }, []);
  const progreso = lista.progreso;
  const paso = progreso ? fases.findIndex((fase) => fase.incluye.includes(progreso.paso)) : -1;
  // El motor manda el avance de toda la lista; si no viene (motor antiguo), se usa perfiles listos / total.
  const porcentaje = progreso ? (typeof progreso.porcentaje === 'number' ? Math.min(100, Math.floor(progreso.porcentaje))
    : progreso.total > 0 ? Math.min(100, Math.round(progreso.hechos / progreso.total * 100)) : null) : null;
  const actividad = progreso?.actividad || (paso < 0 ? 'En cuanto recibamos una actualización verás el avance de tu lista.' : fases[paso].detalle);
  return <main id="contenido" tabIndex={-1} className="contenedor pagina-proceso">
    <div className="encabezado-pequeno"><button className="enlace-texto" onClick={() => navegar('/listas')}>Mis listas <ArrowRight size={14} /> Lista en proceso</button><Chip><span className="punto-vivo" /> {lista.estado === 'pendiente' ? 'En espera' : 'En proceso'}</Chip></div>
    <section className="proceso-titulo"><Etiqueta>Tu lista, paso a paso</Etiqueta><h1>Estamos encontrando tus<br /><em>próximas conexiones.</em></h1><p>Puedes seguir con tu día. Aquí nos encargamos de los detalles.</p></section>
    <Tarjeta className="tarjeta-progreso"><div className="progreso-cabecera"><span className="icono-progreso"><ScanLine size={24} /></span><div aria-live="polite"><Etiqueta>{progreso ? `${progreso.hechos} de ${progreso.total} perfiles listos` : 'Preparando tu lista'}</Etiqueta><h2>{paso < 0 ? 'Ponemos todo en marcha' : fases[paso].nombre}</h2></div><span className="porcentaje-progreso">{porcentaje === null ? 'En marcha' : `${porcentaje} %`}</span></div><div className={`barra-progreso ${porcentaje === null ? 'indeterminada' : ''}`} role="progressbar" aria-label="Avance de toda la lista" aria-valuemin={0} aria-valuemax={100} {...(porcentaje !== null ? { 'aria-valuenow': porcentaje } : {})}><span style={porcentaje !== null ? { width: `${porcentaje}%` } : undefined} /></div><p className="progreso-detalle">{actividad}</p><ol className="linea-pasos">{fases.map((fase, indice) => <li key={fase.id} className={indice === paso ? 'paso-actual' : indice < paso ? 'paso-terminado' : ''} aria-current={indice === paso ? 'step' : undefined}><span className="paso-numero">{String(indice + 1).padStart(2, '0')}</span><span>{fase.nombre}</span></li>)}</ol></Tarjeta>
    <div className="contadores-progreso"><CifraGrande valor={progreso ? <>{progreso.hechos}<small> / {progreso.total}</small></> : '—'} etiqueta="perfiles listos" /><CifraGrande valor={progreso?.descartados ?? '—'} etiqueta="perfiles descartados" /><CifraGrande valor={formatearDuracion((ahora - Date.parse(lista.fecha)) / 1000)} etiqueta="tiempo transcurrido" /><CifraGrande valor={formatearUSD(lista.costo_total_usd, 3)} etiqueta="costo acumulado" /></div>
    <div className="proceso-pie"><div><ShieldCheck size={20} /><p><strong>Con transparencia, de principio a fin.</strong><br />La audiencia estimada siempre estará identificada en tu lista.</p></div><div><FileSpreadsheet size={20} /><p>Al terminar, tu Excel estará listo.<br /><span className="texto-secundario">La pantalla se actualizará automáticamente.</span></p></div><Monograma /></div><p className="ayuda proceso-aviso"><Clock3 size={14} /> Puedes volver a esta lista desde Mis listas cuando quieras.</p>
  </main>;
}
