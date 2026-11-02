import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpDown, Check, ChevronDown, LayoutList, Search, SlidersHorizontal, Table2, X } from 'lucide-react';
import type { EstadoLista, Perfil as DatosPerfil } from './tipos';
import { descargarExcel, obtenerPerfiles } from './api';
import { Acuarela, BadgeEstimado, Boton, Chip, Etiqueta, Monograma } from './componentes';
import { filtrarPerfiles, filtrosIniciales, formatearDuracion, formatearER, formatearFecha, formatearFollowers, formatearUSD, generoTexto, ordenarPerfiles, tieneBrief } from './utilidades';
import type { FiltrosResultados } from './utilidades';
import { AvatarPerfil, Perfil, PerfilNoEncontrado } from './Perfil';
import './resultados.css';

type Props = { lista: EstadoLista; usuario?: string; navegar: (ruta: string) => void };
type Columna = { titulo: string; clave: string; valor: (perfil: DatosPerfil) => string | number };
const numero = (valor: number | null) => valor === null ? '—' : new Intl.NumberFormat('es-PE').format(valor);
const porcentaje = (valor: number | null) => valor === null ? '—' : `${Math.round(valor * 100)} %`;
const columnas: Columna[] = [
  { titulo: '#', clave: 'numero', valor: p => p.numero }, { titulo: '@username', clave: 'usuario', valor: p => `@${p.usuario}` },
  { titulo: 'Nombre / Marca', clave: 'nombre', valor: p => p.nombre || '—' }, { titulo: 'Descripción', clave: 'descripcion', valor: p => p.descripcion || '—' },
  { titulo: 'Categoría', clave: 'categoria', valor: p => p.categoria || '—' }, { titulo: 'Followers', clave: 'followers', valor: p => numero(p.followers) },
  { titulo: 'Quality Audience', clave: 'calidad_audiencia', valor: p => porcentaje(p.calidad_audiencia) }, { titulo: 'ER', clave: 'er', valor: p => formatearER(p.metricas.er) },
  { titulo: 'Aud. Age', clave: 'edad', valor: p => p.audiencia.edad || '—' }, { titulo: 'Aud. Gender', clave: 'genero', valor: p => generoTexto(p.audiencia.genero) },
  { titulo: 'Audience City', clave: 'ciudad', valor: p => p.audiencia.ciudad || '—' }, { titulo: 'Engagements', clave: 'engagements', valor: p => numero(p.metricas.engagements) },
  { titulo: 'Avg. Likes', clave: 'likes', valor: p => numero(p.metricas.likes) }, { titulo: 'Avg. Comments', clave: 'comentarios', valor: p => numero(p.metricas.comentarios) },
  { titulo: 'Avg. Reel Plays', clave: 'reel_plays', valor: p => numero(p.metricas.reel_plays) },
];

export function Resultados({ lista, usuario, navegar }: Props) {
  const [perfiles, establecerPerfiles] = useState<DatosPerfil[]>([]);
  const [cargando, establecerCargando] = useState(true);
  const [error, establecerError] = useState('');
  const [reintento, establecerReintento] = useState(0);
  const [filtros, establecerFiltros] = useState<FiltrosResultados>({ ...filtrosIniciales, categorias: [], marcasAEvitar: lista.corrida?.parametros.brief?.marcas_a_evitar || [] });
  const [vista, establecerVista] = useState<'filas' | 'tabla'>('filas');
  const [orden, establecerOrden] = useState(tieneBrief(lista.corrida?.parametros.brief) ? 'encaje' : 'er');
  const [direccion, establecerDireccion] = useState<'asc' | 'desc'>('desc');
  const [filtrosAbiertos, establecerFiltrosAbiertos] = useState(false);
  const [descargando, establecerDescargando] = useState(false);
  const [errorDescarga, establecerErrorDescarga] = useState('');
  const fondo = useRef<HTMLElement>(null);
  const controlFiltros = useRef<HTMLButtonElement>(null);
  const panelFiltros = useRef<HTMLElement>(null);
  const botonCerrarFiltros = useRef<HTMLButtonElement>(null);
  const controlPerfil = useRef<HTMLElement | null>(null);
  const parametros = lista.corrida?.parametros;
  const fuente = parametros?.referencia ? `@${parametros.referencia}` : 'Usuarios pegados';
  const marca = parametros?.brief?.marca || parametros?.nombre;
  const conBrief = tieneBrief(parametros?.brief);
  useEffect(() => {
    const control = new AbortController();
    establecerCargando(true); establecerError('');
    obtenerPerfiles(lista.id, control.signal).then(datos => { establecerPerfiles(datos); establecerCargando(false); }).catch((fallo: unknown) => { if (!control.signal.aborted) { establecerError(fallo instanceof Error ? fallo.message : 'No pudimos cargar los perfiles. Intenta de nuevo.'); establecerCargando(false); } });
    return () => control.abort();
  }, [lista.id, reintento]);
  useEffect(() => {
    const elementos = [usuario ? fondo.current : null, ...document.querySelectorAll<HTMLElement>('.cabecera,.pie,.saltar-contenido')].filter((elemento): elemento is HTMLElement => Boolean(elemento));
    const estados = elementos.map(elemento => elemento.inert);
    if (usuario || filtrosAbiertos) elementos.forEach(elemento => { elemento.inert = true; });
    return () => elementos.forEach((elemento, indice) => { elemento.inert = estados[indice]; });
  }, [usuario, filtrosAbiertos]);
  useEffect(() => {
    if (!filtrosAbiertos) return;
    const controlAnterior = controlFiltros.current;
    botonCerrarFiltros.current?.focus();
    const anterior = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    function teclado(evento: KeyboardEvent) {
      if (evento.key === 'Escape') establecerFiltrosAbiertos(false);
      if (evento.key !== 'Tab' || !panelFiltros.current) return;
      const controles = Array.from(panelFiltros.current.querySelectorAll<HTMLElement>('button:not([disabled]),input,select,[tabindex="0"]'));
      const primero = controles[0]; const ultimo = controles[controles.length - 1];
      if (evento.shiftKey && document.activeElement === primero) { evento.preventDefault(); ultimo?.focus(); }
      else if (!evento.shiftKey && document.activeElement === ultimo) { evento.preventDefault(); primero?.focus(); }
    }
    document.addEventListener('keydown', teclado);
    return () => { document.body.style.overflow = anterior; document.removeEventListener('keydown', teclado); controlAnterior?.focus(); };
  }, [filtrosAbiertos]);
  const filtrados = useMemo(() => ordenarPerfiles(filtrarPerfiles(perfiles, filtros), orden, direccion), [perfiles, filtros, orden, direccion]);
  const perfilElegido = perfiles.find(perfil => perfil.usuario.toLowerCase() === usuario?.toLowerCase());
  const categorias = [...new Set(perfiles.map(perfil => perfil.categoria).filter((categoria): categoria is string => Boolean(categoria)))].sort();
  const ciudades = [...new Set(perfiles.map(perfil => perfil.audiencia.ciudad).filter((ciudad): ciudad is string => Boolean(ciudad)))].sort();
  const edades = [...new Set(perfiles.map(perfil => perfil.audiencia.edad).filter((edad): edad is string => Boolean(edad)))].sort();
  const descartados = perfiles.filter(perfil => perfil.descartado).length;
  const procesados = lista.corrida?.perfiles_procesados ?? (cargando ? '—' : perfiles.length);
  const duracion = lista.corrida?.duracion_segundos;
  const cambiar = <K extends keyof FiltrosResultados>(clave: K, valor: FiltrosResultados[K]) => establecerFiltros(actuales => ({ ...actuales, [clave]: valor }));
  const limpiar = () => establecerFiltros({ ...filtrosIniciales, categorias: [], marcasAEvitar: parametros?.brief?.marcas_a_evitar || [] });
  const ordenar = (clave: string) => { if (orden === clave) establecerDireccion(direccion === 'asc' ? 'desc' : 'asc'); else { establecerOrden(clave); establecerDireccion(['nombre', 'usuario', 'categoria', 'bio', 'ciudad', 'genero', 'edad'].includes(clave) ? 'asc' : 'desc'); } };
  const abrirPerfil = (perfil: DatosPerfil, control: HTMLElement) => {
    controlPerfil.current = control;
    navegar(`/listas/${encodeURIComponent(lista.id)}/perfil/${encodeURIComponent(perfil.usuario)}`);
  };
  const cerrarPerfil = () => navegar(`/listas/${encodeURIComponent(lista.id)}`);
  async function descargar() {
    establecerDescargando(true); establecerErrorDescarga('');
    try { await descargarExcel(lista.id, parametros?.referencia || 'usuarios', lista.fecha); }
    catch (fallo) { establecerErrorDescarga(fallo instanceof Error ? fallo.message : 'No pudimos descargar el Excel. Intenta de nuevo.'); }
    finally { establecerDescargando(false); }
  }
  return <><main id="contenido" tabIndex={-1} className="contenedor resultados" ref={fondo} aria-hidden={usuario ? true : undefined}>
    <div className="res-migas"><button onClick={() => navegar('/listas')}><ArrowLeft size={14} />Mis listas</button><span>/</span><span>{marca || fuente}</span></div>
    <div className="res-cabecera"><div><Etiqueta>Tu próxima conexión empieza aquí</Etiqueta><h1>Tu lista está lista<span className="res-punto-final">.</span></h1><p>{fuente} <span>·</span> {formatearFecha(lista.fecha)} {marca && <><span>·</span> {marca}</>}</p></div><Chip>{lista.estado === 'parcial' ? 'Lista parcial' : 'Lista completada'}<Check size={12} /></Chip></div>
    {lista.estado === 'parcial' && <p className="res-nota-parcial">{lista.nota || lista.corrida?.notas.join(' · ') || 'Guardamos los perfiles procesados hasta donde alcanzó el presupuesto.'}</p>}
    {lista.corrida?.ejecucion_simulada && <p className="res-nota-parcial">Modo prueba: perfiles sintéticos y costo teórico; la duración corresponde a esta simulación.</p>}
    {!lista.corrida?.costos_confirmados && lista.corrida && <p className="res-nota-parcial">El costo incluye reservas pendientes de conciliación.</p>}
    <div className="res-resumen"><div className="res-resumen-acuarela"><Acuarela variante="mar" className="res-textura" /><div className="res-resumen-contenido"><Etiqueta>Menos tareas. Más conexiones.</Etiqueta><h2>{procesados} perfiles<br />en {formatearDuracion(duracion)}.</h2><Boton onClick={() => void descargar()} disabled={descargando}><ArrowDownToLine size={16} />{descargando ? 'Preparando Excel…' : 'Descargar Excel'}</Boton></div><span className="res-monograma"><Monograma /></span></div><div className="res-resumen-cifras"><div><span>Perfiles procesados</span><strong>{procesados}<small>/ {lista.corrida?.perfiles_solicitados ?? (cargando ? '—' : perfiles.length)}</small></strong><p>Todo en un solo lugar</p></div><div><span>Descartados</span><strong>{cargando ? '—' : descartados}</strong><p>Fuera de tus criterios</p></div><div><span>Tiempo de la lista</span><strong>{formatearDuracion(duracion)}</strong><p>Sin capturas ni copiar y pegar</p></div><div><span>Costo total</span><strong>{formatearUSD(lista.costo_total_usd, 2)}</strong><p>{formatearUSD(lista.corrida?.costo_por_perfil_usd ?? null)} por perfil</p></div></div></div>
    {errorDescarga && <p role="alert" className="res-error">{errorDescarga}</p>}
    <div className="res-explorar"><div><Etiqueta>Encuentra el encaje ideal</Etiqueta><h2>Perfiles, con contexto.</h2></div><p>Conoce a las personas detrás de los números.</p></div>
    <div className="res-distribucion">{filtrosAbiertos && <div className="res-filtro-fondo" onClick={() => establecerFiltrosAbiertos(false)} />}
    <section ref={panelFiltros} className={`res-filtros ${filtrosAbiertos ? 'res-filtros-abiertos' : ''}`} aria-label="Filtros de perfiles" role={filtrosAbiertos ? 'dialog' : undefined} aria-modal={filtrosAbiertos ? true : undefined}>
      <div className="res-filtro-titulo"><h3><SlidersHorizontal size={16} />Filtros</h3><button onClick={limpiar}>Limpiar filtros</button><button ref={botonCerrarFiltros} type="button" className="res-cerrar-filtros" aria-label="Cerrar filtros" onClick={() => establecerFiltrosAbiertos(false)}><X size={19} /></button></div>
      <label className="res-campo"><span>Nombre o usuario</span><span className="res-buscador"><Search size={15} /><input type="search" placeholder="Busca un perfil…" value={filtros.busqueda} onChange={evento => cambiar('busqueda', evento.target.value)} /></span></label>
      <fieldset className="res-grupo"><legend>Followers</legend><div className="res-dos-campos"><input aria-label="Followers mínimos" type="number" min="0" placeholder="Mínimo" value={filtros.followersMin} onChange={evento => cambiar('followersMin', evento.target.value)} /><span>—</span><input aria-label="Followers máximos" type="number" min="0" placeholder="Máximo" value={filtros.followersMax} onChange={evento => cambiar('followersMax', evento.target.value)} /></div></fieldset>
      <label className="res-campo"><span>ER mínimo</span><span className="res-input-unidad"><input type="number" min="0" max="100" step="0.1" placeholder="0" value={filtros.erMin} onChange={evento => cambiar('erMin', evento.target.value)} /><span>%</span></span></label>
      <fieldset className="res-grupo res-categorias"><legend>Categoría <span>Elige más de una</span></legend>{categorias.map(categoria => <label key={categoria}><input type="checkbox" checked={filtros.categorias.includes(categoria)} onChange={evento => cambiar('categorias', evento.target.checked ? [...filtros.categorias, categoria] : filtros.categorias.filter(valor => valor !== categoria))} /><span>{categoria}</span><small>{perfiles.filter(perfil => perfil.categoria === categoria).length}</small></label>)}</fieldset>
      <div className="res-filtro-subtitulo">Audiencia <BadgeEstimado muestra={0} /></div>
      <label className="res-campo"><span>Género mayoritario</span><select value={filtros.genero} onChange={evento => cambiar('genero', evento.target.value)}><option value="">Todos los géneros</option><option value="Female">Mujeres</option><option value="Male">Hombres</option></select></label>
      <label className="res-campo"><span>Edad mayoritaria</span><select value={filtros.edad} onChange={evento => cambiar('edad', evento.target.value)}><option value="">Todas las edades</option>{edades.map(edad => <option key={edad} value={edad}>{edad} años</option>)}</select></label>
      <label className="res-campo"><span>Ciudad</span><select value={filtros.ciudad} onChange={evento => cambiar('ciudad', evento.target.value)}><option value="">Todas las ciudades</option>{ciudades.map(ciudad => <option key={ciudad} value={ciudad}>{ciudad}</option>)}</select></label>
      {conBrief && <label className="res-campo"><span>Encaje mínimo con el brief</span><select value={filtros.encajeMin} onChange={evento => cambiar('encajeMin', evento.target.value)}><option value="">Cualquier encaje</option>{[1, 2, 3, 4, 5].map(valor => <option value={String(valor)} key={valor}>{valor} de 5</option>)}</select></label>}
      <div className="res-filtro-final"><label><input type="checkbox" checked={filtros.ocultarDescartados} onChange={evento => cambiar('ocultarDescartados', evento.target.checked)} /><span>Ocultar descartados</span></label><label><input type="checkbox" checked={filtros.excluirMarcas} onChange={evento => cambiar('excluirMarcas', evento.target.checked)} /><span>Excluir marcas a evitar</span></label>{filtros.marcasAEvitar.length > 0 && <small>{filtros.marcasAEvitar.join(' · ')}</small>}</div>
      <p className="res-filtros-conteo" aria-live="polite">{filtrados.length} de {perfiles.length} perfiles</p><Boton className="res-aplicar-filtros" onClick={() => establecerFiltrosAbiertos(false)}>Ver {filtrados.length} perfiles</Boton>
    </section>
    <div className="res-listado"><div className="res-herramientas"><div><button ref={controlFiltros} type="button" className="res-mostrar-filtros" onClick={() => establecerFiltrosAbiertos(true)}><SlidersHorizontal size={16} />Filtros</button><strong aria-live="polite">{cargando ? 'Cargando' : filtrados.length} <span>perfiles</span></strong><span className="res-total">de {perfiles.length} en tu lista</span></div><div className="res-vistas" role="group" aria-label="Vista de resultados"><button type="button" aria-pressed={vista === 'filas'} onClick={() => establecerVista('filas')}><LayoutList size={15} />Filas</button><button type="button" aria-pressed={vista === 'tabla'} onClick={() => establecerVista('tabla')}><Table2 size={15} />Tabla</button></div></div>
      <div className="res-orden"><span>Una buena conexión va más allá de los followers.</span><label>Ordenar por <select aria-label="Ordenar perfiles" value={`${orden}:${direccion}`} onChange={evento => { const [clave, sentido] = evento.target.value.split(':'); establecerOrden(clave); establecerDireccion(sentido as 'asc' | 'desc'); }}>{conBrief && <option value="encaje:desc">Mayor encaje</option>}<option value="er:desc">Mayor ER</option><option value="followers:desc">Más followers</option><option value="followers:asc">Menos followers</option><option value="nombre:asc">Nombre, A–Z</option><option value="calidad_audiencia:desc">Calidad de audiencia</option><option value="categoria:asc">Categoría</option><option value="edad:asc">Edad de audiencia</option><option value="genero:asc">Género de audiencia</option><option value="ciudad:asc">Ciudad</option><option value="marcas:asc">Marcas</option>{!['encaje:desc', 'er:desc', 'followers:desc', 'followers:asc', 'nombre:asc', 'calidad_audiencia:desc', 'categoria:asc', 'edad:asc', 'genero:asc', 'ciudad:asc', 'marcas:asc'].includes(`${orden}:${direccion}`) && <option value={`${orden}:${direccion}`}>Columna seleccionada</option>}</select><ChevronDown size={13} /></label></div>
      {cargando ? <div className="res-esqueletos" aria-label="Cargando perfiles">{[1, 2, 3, 4, 5].map(clave => <div className="res-esqueleto" key={clave}><span /><div><span /><span /></div><span /><span /></div>)}</div> : error ? <div role="alert" className="res-vacio"><h3>No pudimos cargar la lista</h3><p>{error}</p><Boton variante="secundaria" onClick={() => establecerReintento(valor => valor + 1)}>Volver a intentar</Boton></div> : filtrados.length === 0 ? <div className="res-vacio"><Search size={28} /><h3>Probemos con otros filtros</h3><p>Ningún perfil coincide con esta búsqueda.</p><Boton variante="secundaria" onClick={limpiar}>Limpiar filtros</Boton></div> : vista === 'tabla' ? <div className="res-tabla-contenedor" tabIndex={0} role="region" aria-label="Tabla de las 15 columnas de Aventura; desplázate horizontalmente"><table className="res-tabla"><thead><tr>{columnas.map(columna => <th scope="col" key={columna.clave} aria-sort={orden === columna.clave ? direccion === 'asc' ? 'ascending' : 'descending' : 'none'}><button onClick={() => ordenar(columna.clave)}>{columna.titulo}<ArrowUpDown size={12} /></button></th>)}</tr></thead><tbody>{filtrados.map(perfil => <tr key={perfil.usuario} className={perfil.descartado ? 'res-descartado' : ''}>{columnas.map(columna => <td key={columna.clave} title={columna.clave === 'descripcion' ? perfil.bio ?? undefined : undefined}>{columna.clave === 'usuario' ? <button className="res-tabla-perfil" onClick={evento => abrirPerfil(perfil, evento.currentTarget)}>{columna.valor(perfil)}</button> : ['edad', 'genero', 'ciudad'].includes(columna.clave) ? <span>{columna.valor(perfil)} <BadgeEstimado muestra={perfil.seguidores_muestra} fuente={perfil.audiencia.fuente} /></span> : columna.clave === 'nombre' ? <span>{perfil.nombre || '—'}{perfil.descartado && <small className="res-motivo">Descartado: {perfil.notas.join(' · ')}</small>}</span> : columna.valor(perfil)}</td>)}</tr>)}</tbody></table></div> : <div className="res-filas"><div className="res-fila-encabezado"><button onClick={() => ordenar('nombre')}>Perfil<ArrowUpDown size={11} /></button><button onClick={() => ordenar('followers')}>Followers<ArrowUpDown size={11} /></button><button onClick={() => ordenar('er')}>ER<ArrowUpDown size={11} /></button><button onClick={() => ordenar('edad')}>Audiencia<ArrowUpDown size={11} /></button><button onClick={() => ordenar('calidad_audiencia')}>Calidad<ArrowUpDown size={11} /></button>{conBrief ? <button onClick={() => ordenar('encaje')}>Encaje<ArrowUpDown size={11} /></button> : <span />}<span /></div>{filtrados.map(perfil => <article key={perfil.usuario} className={`res-fila${perfil.descartado ? ' res-descartado' : ''}`}><div className="res-identidad"><AvatarPerfil perfil={perfil} /><div><button className="res-nombre" onClick={evento => abrirPerfil(perfil, evento.currentTarget)}>{perfil.nombre || '—'}{perfil.verificada && <Check size={12} aria-label="Cuenta verificada" />}</button><span className="res-usuario">@{perfil.usuario}</span></div></div><div className="res-celda-numero"><small>Followers</small><strong>{formatearFollowers(perfil.followers)}</strong></div><div className="res-celda-numero"><small>ER</small><strong>{formatearER(perfil.metricas.er)}</strong></div><div className="res-audiencia"><span>{perfil.audiencia.edad || '—'} · {generoTexto(perfil.audiencia.genero)}</span><span>{perfil.audiencia.ciudad || '—'} <BadgeEstimado muestra={perfil.seguidores_muestra} fuente={perfil.audiencia.fuente} /></span></div><div className="res-calidad"><span>{porcentaje(perfil.calidad_audiencia)}</span><div aria-hidden="true">{perfil.calidad_audiencia !== null && <span style={{ width: `${perfil.calidad_audiencia * 100}%` }} />}</div></div><div className="res-encaje" aria-hidden={!conBrief} aria-label={conBrief ? `Encaje: ${perfil.encaje === null ? 'sin evaluación' : `${perfil.encaje} de 5`}` : undefined}>{conBrief && <><span className="res-puntos" aria-hidden="true">{perfil.encaje === null ? '—' : [1, 2, 3, 4, 5].map(valor => <i key={valor} className={valor <= perfil.encaje! ? 'res-punto-lleno' : ''} />)}</span><span>{perfil.encaje === null ? '—' : `${perfil.encaje} de 5`}</span></>}</div><button className="res-ver-ficha" onClick={evento => abrirPerfil(perfil, evento.currentTarget)}>Ver ficha<ArrowRight size={14} /><span className="sr-only"> de {perfil.nombre || '—'}</span></button><div className="res-marcas"><Chip>{perfil.categoria || '—'}</Chip>{perfil.marcas.slice(0, 3).map((marcaPerfil, indice) => <span key={`${marcaPerfil.nombre}-${indice}`}>{marcaPerfil.nombre}</span>)}{perfil.descartado && <small className="res-motivo">Descartado: {perfil.notas.join(' · ') || 'Fuera de los criterios'}</small>}</div></article>)}</div>}
      {!cargando && !error && filtrados.length > 0 && <p className="res-fin-lista">Llegaste al final de tu lista <span>·</span> {filtrados.length} perfiles para explorar</p>}
    </div></div>
    </main>{usuario && perfilElegido && <Perfil perfil={perfilElegido} conBrief={conBrief} agregacion={parametros?.metricas_agregacion} cerrar={cerrarPerfil} controlAnterior={controlPerfil.current} />}{usuario && !cargando && !perfilElegido && <PerfilNoEncontrado cerrar={cerrarPerfil} />}</>;
}
