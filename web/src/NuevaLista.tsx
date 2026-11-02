import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { ArrowRight, ArrowUpRight, AtSign, Check, ChevronDown, CircleHelp, Coins, Layers3, Plus, Sparkles, X } from 'lucide-react';
import { Acuarela, Boton, Campo, Chip, Etiqueta, Monograma, Tarjeta } from './componentes';
import { PRODUCTO } from './config';
import { crearLista, obtenerLista } from './api';
import { formatearUSD, normalizarUsuarios } from './utilidades';
import type { Estimacion, ParametrosLista } from './tipos';

function esperarActualizacion(senal: AbortSignal): Promise<void> {
  return new Promise((resolver, rechazar) => {
    if (senal.aborted) { rechazar(new DOMException('Solicitud cancelada', 'AbortError')); return; }
    const temporizador = setTimeout(() => {
      senal.removeEventListener('abort', cancelar);
      resolver();
    }, 3000);
    function cancelar() {
      clearTimeout(temporizador);
      rechazar(new DOMException('Solicitud cancelada', 'AbortError'));
    }
    senal.addEventListener('abort', cancelar, { once: true });
  });
}

// Parámetros internos de Praxia: Aventura no los ve ni los ajusta (se calculan en /calculadora).
// Costo-beneficio más bajo: 50 seguidores dan el género de la audiencia al ~96 % en una audiencia 65/35;
// de los 10 reels más recientes se transcriben solo los de publicidad (hasta 5). ~USD 0.057 por perfil.
const PARAMETROS = { reels: 5, reels_revisar: 10, muestra_seguidores: 50, limite: 200, presupuesto_usd: 15 };

export default function NuevaLista({ navegar }: { navegar: (ruta: string) => void }) {
  const [modo, establecerModo] = useState<'referencia' | 'usuarios'>('referencia');
  const [fuente, establecerFuente] = useState('');
  const [usuarios, establecerUsuarios] = useState('');
  const [marca, establecerMarca] = useState('');
  const [publico, establecerPublico] = useState('');
  const [marcaPendiente, establecerMarcaPendiente] = useState('');
  const [marcas, establecerMarcas] = useState<string[]>([]);
  const [minimo, establecerMinimo] = useState('');
  const [maximo, establecerMaximo] = useState('');
  const [simulado, establecerSimulado] = useState(false);
  const [ocupado, establecerOcupado] = useState<'estimar' | 'armar' | null>(null);
  const [error, establecerError] = useState('');
  const [estimacion, establecerEstimacion] = useState<Estimacion | null>(null);
  const peticion = useRef<AbortController | null>(null);
  const normalizados = normalizarUsuarios(usuarios);

  useEffect(() => {
    establecerEstimacion(null);
    establecerOcupado(null);
    establecerError('');
    return () => {
      peticion.current?.abort();
      peticion.current = null;
    };
  }, [modo, fuente, usuarios, marca, publico, marcaPendiente, marcas, minimo, maximo, simulado]);

  function agregarMarca() {
    if (marcaPendiente.trim()) establecerMarcas((actual) => [...new Set([...actual, marcaPendiente.trim()])]);
    establecerMarcaPendiente('');
  }
  function teclaMarca(evento: KeyboardEvent<HTMLInputElement>) {
    if (evento.key === 'Enter' || evento.key === ',') { evento.preventDefault(); agregarMarca(); }
  }
  async function enviar(evento: FormEvent, estimar = false) {
    evento.preventDefault();
    establecerError(''); establecerEstimacion(null);
    const referencias = normalizarUsuarios(fuente);
    if (modo === 'referencia' && referencias.length !== 1) { establecerError('Ingresa una cuenta de referencia válida. Puedes pegar su usuario o el enlace del perfil.'); return; }
    if (modo === 'usuarios' && normalizados.length === 0) { establecerError('Pega al menos un usuario válido, uno por línea.'); return; }
    if (minimo && maximo && Number(minimo) > Number(maximo)) { establecerError('El mínimo de followers debe ser menor o igual al máximo.'); return; }
    const parametros: ParametrosLista = {
      referencia: modo === 'referencia' ? referencias[0] : null,
      usuarios: modo === 'usuarios' ? normalizados : null,
      ...PARAMETROS,
      estimar, simulado: import.meta.env.VITE_PERMITIR_SIMULADO === 'true' && simulado,
      ...((marca.trim() || publico.trim() || marcas.length || marcaPendiente.trim() || minimo || maximo) && { brief: {
        marca: marca.trim(), publico_objetivo: publico.trim(),
        marcas_a_evitar: [...new Set([...marcas, ...(marcaPendiente.trim() ? [marcaPendiente.trim()] : [])])],
        ...(minimo && { followers_min: Number(minimo) }), ...(maximo && { followers_max: Number(maximo) }),
      } }),
    };
    peticion.current?.abort();
    const controlador = new AbortController();
    peticion.current = controlador;
    establecerOcupado(estimar ? 'estimar' : 'armar');
    try {
      const nueva = await crearLista(parametros, controlador.signal);
      if (controlador.signal.aborted) return;
      if (!estimar) { navegar(`/listas/${nueva.id}`); return; }
      let estado = await obtenerLista(nueva.id, controlador.signal);
      if (controlador.signal.aborted) return;
      for (let intento = 0; intento < 20 && ['pendiente', 'en_proceso'].includes(estado.estado); intento++) {
        await esperarActualizacion(controlador.signal);
        estado = await obtenerLista(nueva.id, controlador.signal);
        if (controlador.signal.aborted) return;
      }
      if (!estado.estimacion) throw new Error(estado.nota || 'No pudimos calcular el costo. Intenta de nuevo.');
      establecerEstimacion(estado.estimacion);
    } catch (fallo) {
      if (!controlador.signal.aborted) establecerError(fallo instanceof Error ? fallo.message : 'No pudimos armar la lista. Intenta de nuevo.');
    } finally {
      if (peticion.current === controlador && !controlador.signal.aborted) {
        peticion.current = null;
        establecerOcupado(null);
      }
    }
  }
  return <main id="contenido" tabIndex={-1} className="contenedor pagina-nueva">
    <div className="encabezado-pequeno"><span><span className="punto-vivo" /> Tu próxima campaña empieza aquí</span><a href="/listas" onClick={(evento) => { evento.preventDefault(); navegar('/listas'); }}>Explora tus listas <ArrowUpRight size={15} /></a></div>
    <div className="nueva-rejilla">
      <section className="presentacion">
        <div className="hero-acuarela">
          <Acuarela />
          <div className="hero-contenido"><Etiqueta>{PRODUCTO.nombre} · historias que conectan</Etiqueta><h1>Tu lista de influencers,<br /><em>sin copiar<br />y pegar.</em></h1><p>Encuentra los perfiles que hacen match con tu marca.<br className="solo-escritorio" /> Nosotros nos encargamos del resto.</p><div className="hero-tiempo"><span>Antes <s>2–3 horas</s></span><ArrowRight size={17} /><strong>Ahora, sin tocarla</strong></div><div className="hero-firma"><span>#HistoriasQueConecten</span><Monograma /></div></div>
        </div>
        <div className="presentacion-nota"><span className="icono-nota"><Sparkles size={19} /></span><div><strong>Más criterio. Menos trabajo manual.</strong><p>De una cuenta de referencia a una lista con métricas,<br className="solo-escritorio" /> audiencia estimada y el Excel que ya conoces.</p></div></div>
      </section>
      <Tarjeta className="formulario-nueva">
        <Etiqueta>01 / Arma tu lista</Etiqueta><h2>¿Por dónde empezamos?</h2>
        <form onSubmit={(evento) => void enviar(evento)}>
          <div className="pestanas-fuente" role="tablist" aria-label="Fuente de los perfiles">
            {(['referencia', 'usuarios'] as const).map((valor, indice) => <button type="button" role="tab" id={`pestana-${valor}`} aria-controls="panel-fuente" aria-selected={modo === valor} tabIndex={modo === valor ? 0 : -1} key={valor} onClick={() => establecerModo(valor)} onKeyDown={(evento) => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(evento.key)) { evento.preventDefault(); const proximo = evento.key === 'Home' ? 'referencia' : evento.key === 'End' ? 'usuarios' : indice === 0 ? 'usuarios' : 'referencia'; establecerModo(proximo); document.getElementById(`pestana-${proximo}`)?.focus(); } }}>{valor === 'referencia' ? 'Desde una cuenta de referencia' : 'Pegar usuarios'}</button>)}
          </div>
          <div id="panel-fuente" role="tabpanel" aria-labelledby={`pestana-${modo}`} className="panel-fuente">
            {modo === 'referencia' ? <><label htmlFor="referencia">Cuenta de referencia</label><div className="campo-con-icono"><AtSign size={17} aria-hidden="true" /><input id="referencia" placeholder="Ej. casa.bruma" value={fuente} onChange={(evento) => establecerFuente(evento.target.value)} autoComplete="off" aria-describedby="ayuda-referencia" /></div><p id="ayuda-referencia" className="ayuda"><CircleHelp size={13} /> Revisaremos los perfiles que sigue esta cuenta.</p></> : <><label htmlFor="usuarios">Usuarios, uno por línea</label><textarea id="usuarios" rows={4} placeholder={'@sol.alvica\nnilo.caminos\nhttps://instagram.com/vela.paleta'} value={usuarios} onChange={(evento) => establecerUsuarios(evento.target.value)} aria-describedby="ayuda-usuarios" /><p id="ayuda-usuarios" className="ayuda">{normalizados.length} usuarios únicos · Aceptamos @ y enlaces de perfil.</p></>}
          </div>
          <details className="plegable"><summary><span><Layers3 size={17} /> Brief de la marca <span className="opcional">Opcional</span></span><ChevronDown size={17} /></summary><div className="plegable-interior"><Campo etiqueta="Marca" placeholder="Ej. Bruma Estudio" value={marca} onChange={(evento) => establecerMarca(evento.target.value)} /><div className="campo-grupo"><label htmlFor="publico">¿Con quién quieres conectar?</label><textarea id="publico" rows={2} placeholder="Ej. mujeres de 25 a 34 años en Lima, interesadas en moda consciente" value={publico} onChange={(evento) => establecerPublico(evento.target.value)} /></div><div className="campo-grupo"><label htmlFor="evitar">Marcas a evitar</label><div className="entrada-chips">{marcas.map((nombre) => <Chip key={nombre}>{nombre}<button type="button" aria-label={`Quitar ${nombre}`} onClick={() => establecerMarcas(marcas.filter((otra) => otra !== nombre))}><X size={12} /></button></Chip>)}<input id="evitar" placeholder="Escribe una marca y presiona Enter" value={marcaPendiente} onChange={(evento) => establecerMarcaPendiente(evento.target.value)} onKeyDown={teclaMarca} /><button type="button" aria-label="Agregar marca a evitar" onClick={agregarMarca}><Plus size={16} /></button></div></div><div className="dos-campos"><Campo etiqueta="Followers mínimos" type="number" min="0" value={minimo} onChange={(evento) => establecerMinimo(evento.target.value)} /><Campo etiqueta="Followers máximos" type="number" min="0" value={maximo} onChange={(evento) => establecerMaximo(evento.target.value)} /></div></div></details>
          {import.meta.env.VITE_PERMITIR_SIMULADO === 'true' && <label className="control-check"><input type="checkbox" checked={simulado} onChange={(evento) => establecerSimulado(evento.target.checked)} /> Modo prueba (sin costo)</label>}
          {!import.meta.env.VITE_MOTOR_TOKEN?.trim() && <p role="status" className="mensaje-error">Falta el token del motor. Configura VITE_MOTOR_TOKEN en web/.env.local y reinicia la web.</p>}
          {error && <p role="alert" className="mensaje-error">{error}</p>}
          {estimacion && <div className="desglose-costo" role="status"><div><Etiqueta>Costo estimado · {estimacion.perfiles} perfiles</Etiqueta><strong>{formatearUSD(estimacion.costo_total_usd, 2)}</strong><small>{formatearUSD(estimacion.costo_por_perfil_usd)} por perfil</small></div><dl>{Object.entries(estimacion.costos_por_paso).map(([paso, costo]) => <div key={paso}><dt>{({ perfil: 'Perfiles', perfiles: 'Perfiles', reels: 'Reels', following: 'Seguidos', followers: 'Muestra de seguidores', transcripcion: 'Transcripción', transcripcion_local: 'Transcripción local', seguidores: 'Audiencia', clasificacion: 'Clasificación', jev: 'Clasificación', openrouter: 'Clasificación', openrouter_entrada: 'Clasificación (entrada)', openrouter_salida: 'Clasificación (salida)' } as Record<string, string>)[paso] || 'Otro paso'}</dt><dd>{formatearUSD(costo, 2)}</dd></div>)}</dl></div>}
          <div className="acciones-formulario"><Boton type="button" variante="secundaria" disabled={!!ocupado} onClick={(evento) => { const formulario = evento.currentTarget.form; if (formulario?.reportValidity()) void enviar(evento, true); }}><Coins size={16} />{ocupado === 'estimar' ? 'Calculando…' : 'Calcular costo'}</Boton><Boton type="submit" disabled={!!ocupado}>{ocupado === 'armar' ? 'Armando…' : 'Armar lista'}<ArrowRight size={17} /></Boton></div><p className="nota-formulario"><Check size={13} /> Tu lista, lista para descargar en Excel.</p>
        </form>
      </Tarjeta>
    </div>
    <section className="como-funciona" aria-label="Cómo funciona"><div><Etiqueta>De una referencia a una buena conexión</Etiqueta><h2>Tú pones el punto de partida.</h2></div><ol><li><span>01</span><div><strong>Encuentra</strong><p>Partimos de una cuenta<br />o de tus propios perfiles.</p></div></li><li><span>02</span><div><strong>Conoce</strong><p>Métricas, audiencia y marcas.<br />Todo en un solo lugar.</p></div></li><li><span>03</span><div><strong>Conecta</strong><p>Filtra, elige y descarga.<br />Tu próxima lista está lista.</p></div></li></ol></section>
  </main>;
}
