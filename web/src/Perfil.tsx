import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowUpRight, Check, MapPin, X } from 'lucide-react';
import type { Perfil as DatosPerfil } from './tipos';
import { BadgeEstimado, Boton, Chip, Etiqueta } from './componentes';
import { formatearER, formatearFollowers, formatearUSD, generoTexto } from './utilidades';

const colores = ['#497CDD', '#3BDCE1', '#D59FFF', '#DFE270', '#69C9BB', '#E85DB6'];
const colorGenero: Record<string, string> = { Female: '#D59FFF', Male: '#497CDD' };
const porcentajeFino = (valor: number) => valor > 0 && valor < 0.01 ? '<1 %' : `${Math.round(valor * 100)} %`;
const numero = (valor: number | null) => valor === null ? '—' : new Intl.NumberFormat('es-PE').format(valor);
const porcentaje = (valor: number | null) => valor === null ? '—' : `${Math.round(valor * 100)} %`;
const inicialesPerfil = (nombre: string) => nombre.split(/\s+/).filter(Boolean).slice(0, 2).map(parte => parte[0]).join('');
export function AvatarPerfil({ perfil, grande = false }: { perfil: DatosPerfil; grande?: boolean }) {
  return <span aria-hidden="true" className={`perfil-avatar${grande ? ' perfil-avatar-grande' : ''}`} style={{ background: ['#e2d4ee', '#d9e9de', '#e9e3cc', '#d3e6e9', '#ead9e1'][perfil.numero % 5] }}>{inicialesPerfil(perfil.nombre || perfil.usuario)}</span>;
}

function DonaEdades({ distribucion }: { distribucion: Record<string, number> }) {
  const datos = Object.entries(distribucion).filter(([, valor]) => valor > 0);
  const total = datos.reduce((suma, [, valor]) => suma + valor, 0);
  let acumulado = 0;
  return <div className="perfil-edades"><svg role="img" aria-label={`Distribución de edades: ${datos.map(([edad, valor]) => `${edad}: ${porcentaje(valor)}`).join(', ')}`} viewBox="0 0 160 160" className="perfil-dona"><circle cx="80" cy="80" r="57" fill="none" stroke="#F2F0EC" strokeWidth="24" />{datos.map(([edad, valor], indice) => {
    const longitud = total > 0 ? valor / total * 358.14 : 0;
    const inicio = acumulado;
    acumulado += longitud;
    return <circle key={edad} cx="80" cy="80" r="57" fill="none" stroke={colores[indice % colores.length]} strokeWidth="24" strokeDasharray={`${longitud} ${358.14 - longitud}`} strokeDashoffset={-inicio} transform="rotate(-90 80 80)" />;
  })}<text x="80" y="78" textAnchor="middle" className="perfil-dona-texto">Edad</text><text x="80" y="99" textAnchor="middle" className="perfil-dona-subtexto">estimada</text></svg><ul className="perfil-leyenda">{datos.map(([edad, valor], indice) => <li key={edad}><span className="perfil-punto" style={{ background: colores[indice % colores.length] }} /><span>{edad} años</span><strong>{porcentaje(valor)}</strong></li>)}</ul></div>;
}

function BarrasGenero({ distribucion }: { distribucion: Record<string, number> }) {
  return <>{Object.entries(distribucion).map(([nombre, valor], indice) => <div className="perfil-genero" key={nombre}><div><span>{generoTexto(nombre)}</span><strong>{porcentaje(valor)}</strong></div><span className="perfil-barra-genero"><span style={{ width: `${valor * 100}%`, background: colorGenero[nombre] ?? colores[indice % colores.length] }} /></span></div>)}</>;
}

// Como el panel de Instagram: cada rango con su barra partida en mujeres y hombres.
function BarrasEdad({ distribucion }: { distribucion: Record<string, { Female: number; Male: number }> }) {
  return <div className="perfil-filas"><p className="perfil-leyenda-genero"><span><span className="perfil-punto" style={{ background: colorGenero.Female }} />Mujeres</span><span><span className="perfil-punto" style={{ background: colorGenero.Male }} />Hombres</span></p>
    <ul aria-label="Edad de la audiencia por género">{Object.entries(distribucion).map(([rango, partes]) => {
      const total = partes.Female + partes.Male;
      return <li key={rango} aria-label={`${rango} años: ${porcentajeFino(total)} (mujeres ${porcentajeFino(partes.Female)}, hombres ${porcentajeFino(partes.Male)})`}><span>{rango}</span><span className="perfil-barra-fila"><span style={{ width: `${partes.Female * 100}%`, background: colorGenero.Female }} /><span style={{ width: `${partes.Male * 100}%`, background: colorGenero.Male }} /></span><strong>{porcentajeFino(total)}</strong></li>;
    })}</ul></div>;
}

function Lugares({ paises, ciudades }: { paises: Record<string, number>; ciudades: Record<string, number> }) {
  const [vista, establecerVista] = useState<'paises' | 'ciudades'>('paises');
  const filas = Object.entries(vista === 'paises' ? paises : ciudades).filter(([, valor]) => valor >= 0.005).slice(0, 5);
  return <div className="perfil-lugares"><div className="perfil-lugares-cabeza"><h4>Lugares más populares</h4><div className="perfil-pestanas" role="group" aria-label="Ver por">{([['paises', 'Países'], ['ciudades', 'Ciudades']] as const).map(([clave, texto]) => <button type="button" key={clave} aria-pressed={vista === clave} onClick={() => establecerVista(clave)}>{texto}</button>)}</div></div>
    <ul className="perfil-filas" aria-label={vista === 'paises' ? 'Países de la audiencia' : 'Ciudades de la audiencia'}>{filas.map(([nombre, valor]) => <li key={nombre}><span>{nombre}</span><span className="perfil-barra-fila"><span style={{ width: `${valor * 100}%` }} /></span><strong>{porcentajeFino(valor)}</strong></li>)}</ul></div>;
}

function fechaMarca(fecha: string | null): string {
  if (!fecha) return '—';
  const valor = new Date(fecha);
  return Number.isNaN(valor.getTime()) ? '—' : new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short', timeZone: 'UTC' }).format(valor);
}

function enlaceSeguro(url: string) {
  try { const enlace = new URL(url); return ['https:', 'http:'].includes(enlace.protocol) ? enlace.href : undefined; } catch { return undefined; }
}

export function Perfil({ perfil, cerrar, controlAnterior, conBrief = false, agregacion }: { perfil: DatosPerfil; cerrar: () => void; controlAnterior?: HTMLElement | null; conBrief?: boolean; agregacion?: 'promedio' | 'mediana' }) {
  const cajon = useRef<HTMLElement>(null);
  const botonCerrar = useRef<HTMLButtonElement>(null);
  const enfoqueAnterior = useRef(controlAnterior ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null));
  const cerrarActual = useRef(cerrar);
  cerrarActual.current = cerrar;
  useEffect(() => {
    const anterior = enfoqueAnterior.current;
    const desborde = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    botonCerrar.current?.focus();
    function teclado(evento: KeyboardEvent) {
      if (evento.key === 'Escape') { evento.preventDefault(); cerrarActual.current(); }
      if (evento.key !== 'Tab' || !cajon.current) return;
      const controles = Array.from(cajon.current.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input,select,textarea,[tabindex="0"]')).filter(elemento => elemento.getClientRects().length > 0);
      const primero = controles[0]; const ultimo = controles[controles.length - 1];
      if (evento.shiftKey && (document.activeElement === primero || !cajon.current.contains(document.activeElement))) { evento.preventDefault(); ultimo?.focus(); }
      else if (!evento.shiftKey && (document.activeElement === ultimo || !cajon.current.contains(document.activeElement))) { evento.preventDefault(); primero?.focus(); }
    }
    document.addEventListener('keydown', teclado);
    return () => { document.body.style.overflow = desborde; document.removeEventListener('keydown', teclado); requestAnimationFrame(() => anterior?.focus()); };
  }, []);
  const marcas = [...perfil.marcas].sort((a, b) => (a.fecha ?? '').localeCompare(b.fecha ?? ''));
  const genero = perfil.audiencia.distribucion_genero;
  const edades = perfil.audiencia.distribucion_edad;
  const estimacion = perfil.audiencia.estimacion;
  const conEdadGenero = !!estimacion && Object.keys(estimacion.edad_genero).length > 0;
  const conLugares = !!estimacion && Object.keys(estimacion.ciudad).length > 0;
  return createPortal(<div className="perfil-fondo" onMouseDown={evento => { if (evento.target === evento.currentTarget) cerrar(); }}><section ref={cajon} className="perfil-cajon" role="dialog" aria-modal="true" aria-labelledby="perfil-titulo">
    <div className="perfil-barra"><span>Ficha del perfil <span className="perfil-barra-separador">/</span> #{String(perfil.numero).padStart(2, '0')}</span><button ref={botonCerrar} type="button" onClick={cerrar} className="perfil-cerrar" aria-label="Cerrar ficha"><X size={20} /></button></div>
    <div className="perfil-contenido"><header className="perfil-cabecera"><AvatarPerfil perfil={perfil} grande /><div><div className="perfil-nombre"><h2 id="perfil-titulo">{perfil.nombre || '—'}</h2>{perfil.verificada && <Check size={18} aria-label="Cuenta verificada" />}</div><a href={`https://instagram.com/${encodeURIComponent(perfil.usuario)}`} target="_blank" rel="noreferrer" className="perfil-enlace">@{perfil.usuario}<ArrowUpRight size={14} /><span className="sr-only"> (se abre en otra pestaña)</span></a><Chip>{perfil.categoria || '—'}</Chip></div></header>
    <p className="perfil-bio">{perfil.bio || '—'}</p>
    {perfil.descartado && <p className="perfil-aviso">Perfil descartado · {perfil.notas.join(' · ') || 'No cumple los criterios de la lista.'}</p>}
    <div className="perfil-metricas">{[['Followers', formatearFollowers(perfil.followers)], ['Tasa de interacción', formatearER(perfil.metricas.er)], [agregacion === 'mediana' ? 'Likes (mediana)' : agregacion === 'promedio' ? 'Likes promedio' : 'Likes', numero(perfil.metricas.likes)], ['Comentarios', numero(perfil.metricas.comentarios)], ['Reproducciones', numero(perfil.metricas.reel_plays)]].map(([etiqueta, valor]) => <div key={etiqueta}><span>{etiqueta}</span><strong>{valor}</strong></div>)}</div>
    <section className="perfil-seccion"><div className="perfil-titulo-seccion"><div><Etiqueta>Conoce a su comunidad</Etiqueta><h3>Audiencia</h3></div><BadgeEstimado muestra={perfil.seguidores_muestra} fuente={perfil.audiencia.fuente} /></div><p className="perfil-texto-estimado">{perfil.audiencia.fuente === 'seguidores' ? `Estimado por IA sobre una muestra de ${perfil.seguidores_muestra} seguidores.` : perfil.audiencia.fuente === 'contenido' ? 'Estimado por IA a partir del contenido del perfil. Sin muestra de seguidores.' : 'Sin datos de audiencia disponibles.'}</p>
    <div className="perfil-demografia"><div><h4>Género</h4>{genero && Object.keys(genero).length > 0 ? <BarrasGenero distribucion={genero} /> : estimacion && Object.keys(estimacion.genero).length > 0 ? <BarrasGenero distribucion={estimacion.genero} /> : <p className="perfil-mayoria">{generoTexto(perfil.audiencia.genero)}<small>Género mayoritario · Estimado</small></p>}</div><div><h4>Rango de edad</h4>{conEdadGenero ? <BarrasEdad distribucion={estimacion.edad_genero} /> : edades && Object.keys(edades).length > 0 ? <DonaEdades distribucion={edades} /> : <p className="perfil-mayoria">{perfil.audiencia.edad || '—'}<small>Edad mayoritaria · Estimada</small></p>}</div></div>
    {conLugares && <Lugares paises={estimacion.pais} ciudades={estimacion.ciudad} />}
    {(conEdadGenero || conLugares) && <p className="perfil-texto-estimado perfil-nota-probabilidad">Los porcentajes de edad y lugares son la probabilidad que la IA da a cada opción de ser la mayoritaria según el contenido del perfil, no el porcentaje de seguidores.</p>}
    <div className="perfil-audiencia-pie"><span><MapPin size={15} />{perfil.audiencia.ciudad || '—'}<small>Ciudad estimada</small></span><span>Calidad de audiencia <strong>{porcentaje(perfil.calidad_audiencia)}</strong></span></div>
    </section>
    <section className="perfil-seccion"><Etiqueta>Vínculos que cuentan</Etiqueta><h3>Marcas con las que trabajó</h3>{marcas.length ? <ol className="perfil-timeline" aria-label="Colaboraciones en orden cronológico">{marcas.map((marca, indice) => <li key={`${marca.nombre}-${marca.fecha}-${indice}`}><time dateTime={marca.fecha ?? undefined}>{fechaMarca(marca.fecha)}</time><a href={enlaceSeguro(marca.post_evidencia)} target="_blank" rel="noreferrer">{marca.nombre}<ArrowUpRight size={13} /><span className="sr-only"> · Ver evidencia (otra pestaña)</span></a><span>{marca.tipo === 'colab' ? 'Colaboración' : marca.tipo === 'canje' ? 'Canje' : 'Publicidad'}{marca.tamano ? ` · empresa ${marca.tamano === 'pequena' ? 'pequeña' : marca.tamano}` : ''}</span></li>)}</ol> : <p className="perfil-texto-secundario">No encontramos colaboraciones acreditadas.</p>}
    <p className="perfil-menciones-titulo">Menciones sin colaboración acreditada</p><div className="perfil-menciones">{perfil.menciones.length ? perfil.menciones.map((mencion, indice) => <span key={`${mencion.nombre}-${indice}`}>{mencion.nombre}</span>) : <span>Sin menciones adicionales.</span>}</div></section>
    {conBrief && <section className="perfil-seccion perfil-encaje"><div><Etiqueta>Encaje con el brief</Etiqueta><div className="perfil-puntuacion">{perfil.encaje === null ? '—' : <>{perfil.encaje}<span>/ 5</span></>}</div></div><p>{perfil.motivo_encaje || '—'}</p></section>}
    <footer className="perfil-notas">{perfil.notas.length > 0 && <p>{perfil.notas.join(' · ')}</p>}<p>Costo de este perfil: {formatearUSD(perfil.costo_usd)} · Las estimaciones de audiencia son orientativas.</p></footer>
    <Boton variante="secundaria" onClick={cerrar} className="perfil-cerrar-final">Cerrar ficha</Boton>
    </div></section></div>, document.body);
}

export function PerfilNoEncontrado({ cerrar }: { cerrar: () => void }) {
  const boton = useRef<HTMLButtonElement>(null);
  const enfoqueAnterior = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  const cerrarActual = useRef(cerrar);
  cerrarActual.current = cerrar;
  useEffect(() => {
    const anterior = enfoqueAnterior.current;
    const desborde = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    boton.current?.focus();
    function teclado(evento: KeyboardEvent) {
      if (evento.key === 'Escape') { evento.preventDefault(); cerrarActual.current(); }
      if (evento.key === 'Tab') { evento.preventDefault(); boton.current?.focus(); }
    }
    document.addEventListener('keydown', teclado);
    return () => { document.body.style.overflow = desborde; document.removeEventListener('keydown', teclado); requestAnimationFrame(() => anterior?.focus()); };
  }, []);
  return createPortal(<div className="perfil-fondo" onMouseDown={evento => { if (evento.target === evento.currentTarget) cerrar(); }}><div className="res-perfil-no-encontrado" role="dialog" aria-modal="true" aria-labelledby="perfil-no-encontrado-titulo"><h2 id="perfil-no-encontrado-titulo">No encontramos este perfil</h2><p>Puede que el usuario no pertenezca a esta lista.</p><button ref={boton} type="button" className="boton boton-primaria" onClick={cerrar}>Volver a la lista</button></div></div>, document.body);
}
