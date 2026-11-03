import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Plus, RotateCcw, Sparkles } from 'lucide-react';
import NuevaLista from './NuevaLista';
import Historial from './Historial';
import Validacion from './Validacion';
import Calculadora from './Calculadora';
import Proceso from './Proceso';
import { Resultados } from './Resultados';
import { Acuarela, Boton, Chip, Esqueleto, Etiqueta, Monograma, Tarjeta } from './componentes';
import { PRODUCTO } from './config';
import { useSondeo } from './useSondeo';
import { crearLista } from './api';
import { formatearUSD, parametrosParaReintentar } from './utilidades';
import type { EstadoLista } from './tipos';

function Lista({ id, usuario, navegar }: { id: string; usuario?: string; navegar: (ruta: string) => void }) {
  const { lista, error, cargando, recargar } = useSondeo(id);
  const [reintentando, establecerReintentando] = useState(false);
  const [errorReintento, establecerErrorReintento] = useState('');
  async function reintentar(estado: EstadoLista) {
    const parametros = parametrosParaReintentar(estado.corrida);
    if (!parametros) { navegar('/'); return; }
    establecerReintentando(true); establecerErrorReintento('');
    try { const nueva = await crearLista(parametros); navegar(`/listas/${nueva.id}`); }
    catch (fallo) { establecerErrorReintento(fallo instanceof Error ? fallo.message : 'No pudimos reintentar la lista.'); }
    finally { establecerReintentando(false); }
  }
  if (cargando) return <main id="contenido" tabIndex={-1} className="contenedor pagina-cargando" role="status" aria-label="Cargando lista"><Esqueleto className="esqueleto-titulo" /><Esqueleto className="esqueleto-hero" />{[0, 1, 2].map((fila) => <Esqueleto className="esqueleto-fila" key={fila} />)}</main>;
  if (error) return <main id="contenido" tabIndex={-1} className="contenedor pagina-cargando"><Tarjeta className="estado-vacio"><h1>No pudimos abrir esta lista</h1><p role="alert">{error}</p><div className="acciones-centradas"><Boton variante="secundaria" onClick={() => navegar('/listas')}><ArrowLeft size={16} /> Mis listas</Boton><Boton onClick={recargar}><RotateCcw size={16} /> Volver a intentar</Boton></div></Tarjeta></main>;
  if (!lista) return null;
  if (['pendiente', 'en_proceso'].includes(lista.estado)) return <Proceso lista={lista} navegar={navegar} />;
  if (lista.estado === 'error' || lista.estado === 'interrumpida') return <main id="contenido" tabIndex={-1} className="contenedor pagina-cargando"><button className="enlace-texto" onClick={() => navegar('/listas')}><ArrowLeft size={15} /> Mis listas</button><Tarjeta className="estado-vacio estado-interrumpido"><Acuarela variante="lila" /><div><Chip className="estado-error">{lista.estado === 'error' ? 'Necesita otro intento' : 'Lista interrumpida'}</Chip><h1>Retomemos la conexión.</h1><p>{lista.nota || 'No pudimos completar esta lista. Puedes intentarlo otra vez.'}</p>{errorReintento && <p role="alert" className="mensaje-error">{errorReintento}</p>}<Boton disabled={reintentando} onClick={() => void reintentar(lista)}><RotateCcw size={16} />{reintentando ? 'Reintentando…' : 'Reintentar'}</Boton></div></Tarjeta></main>;
  if (lista.estado === 'estimada') return <main id="contenido" tabIndex={-1} className="contenedor pagina-cargando"><Tarjeta className="estado-vacio"><Acuarela variante="lima" /><div><Etiqueta>Una idea del costo, antes de empezar</Etiqueta><h1>Tu próxima lista,<br />en números.</h1><p>{lista.estimacion?.perfiles ?? '—'} perfiles · {formatearUSD(lista.estimacion?.costo_total_usd, 2)} en total · {formatearUSD(lista.estimacion?.costo_por_perfil_usd)} por perfil.</p><Boton onClick={() => navegar('/')}>Armar nueva lista<ArrowRight size={17} /></Boton></div></Tarjeta></main>;
  return <Resultados lista={lista} usuario={usuario} navegar={navegar} />;
}

export default function App() {
  const [ruta, establecerRuta] = useState(window.location.pathname);
  const anterior = useRef(ruta);
  const navegar = useCallback((destino: string) => { if (window.location.pathname !== destino) window.history.pushState({}, '', destino); establecerRuta(destino); }, []);
  useEffect(() => { const actualizar = () => establecerRuta(window.location.pathname); window.addEventListener('popstate', actualizar); return () => window.removeEventListener('popstate', actualizar); }, []);
  useEffect(() => {
    document.title = `${PRODUCTO.nombre} · Aventura PR`;
    const base = (valor: string) => valor.split('/perfil/')[0];
    if (base(anterior.current) !== base(ruta)) { window.scrollTo({ top: 0, behavior: 'instant' }); document.getElementById('contenido')?.focus({ preventScroll: true }); }
    anterior.current = ruta;
  }, [ruta]);
  const coincidencia = /^\/listas\/([^/]+)(?:\/perfil\/([^/]+))?\/?$/.exec(ruta);
  function enlace(evento: React.MouseEvent<HTMLAnchorElement>, destino: string) { if (!evento.metaKey && !evento.ctrlKey && !evento.shiftKey && evento.button === 0) { evento.preventDefault(); navegar(destino); } }
  return <div className="aplicacion"><a href="#contenido" className="saltar-contenido">Saltar al contenido</a><header className="cabecera"><div className="contenedor cabecera-interior"><a className="marca" href="/" onClick={(evento) => enlace(evento, '/')}><span className="marca-circulo" aria-hidden="true"><Monograma /></span><span className="marca-nombre">{PRODUCTO.nombre}<small>{PRODUCTO.subtitulo}</small></span></a><nav aria-label="Navegación principal">{[{ destino: '/', texto: 'Nueva lista' }, { destino: '/listas', texto: 'Mis listas' }, { destino: '/validacion', texto: 'Validación' }].map(({ destino, texto }) => <a key={destino} href={destino} aria-current={ruta === destino || destino === '/listas' && ruta.startsWith('/listas/') ? 'page' : undefined} onClick={(evento) => enlace(evento, destino)}>{texto}</a>)}</nav><div className="cabecera-derecha"><span><Sparkles size={14} /> Hecho para conectar</span><Boton variante="secundaria" onClick={() => navegar('/')}><Plus size={16} /> Armar lista</Boton></div></div></header>
    {ruta === '/' ? <NuevaLista navegar={navegar} /> : ruta === '/calculadora' ? <Calculadora /> : ruta === '/sin-limites' ? <NuevaLista navegar={navegar} sinLimites /> : ruta === '/listas' ? <Historial navegar={navegar} /> : ruta === '/validacion' ? <Validacion navegar={navegar} /> : coincidencia ? <Lista id={decodeURIComponent(coincidencia[1])} usuario={coincidencia[2] ? decodeURIComponent(coincidencia[2]) : undefined} navegar={navegar} /> : <main id="contenido" tabIndex={-1} className="contenedor pagina-cargando"><Tarjeta className="estado-vacio"><Etiqueta>Nos salimos un poquito del camino</Etiqueta><h1>Esta página no está aquí.</h1><p>Tu próxima conexión te espera en una nueva lista.</p><Boton onClick={() => navegar('/')}>Volver al inicio <ArrowRight size={16} /></Boton></Tarjeta></main>}
    <footer className="pie"><div className="contenedor pie-interior"><p>{PRODUCTO.firma}</p><span>#HistoriasQueConecten <span className="punto-lila">✳</span></span></div></footer></div>;
}
