import { Fragment, useEffect, useState } from 'react';
import { ArrowRight, Check, ChevronDown, FlaskConical, Search } from 'lucide-react';
import { ErrorAPI, obtenerValidacion } from './api';
import { Acuarela, Boton, Chip, Esqueleto, Etiqueta, Monograma, Tarjeta } from './componentes';
import { formatearER, formatearFecha, formatearFollowers, formatearUSD, formatearDuracion, generoTexto } from './utilidades';
import { PRODUCTO } from './config';
import type { MedidasValidacion, Validacion as DatosValidacion } from './tipos';

const medidas: { id: keyof MedidasValidacion; nombre: string }[] = [{ id: 'followers', nombre: 'Followers' }, { id: 'er', nombre: 'ER' }, { id: 'edad', nombre: 'Edad' }, { id: 'genero', nombre: 'Género' }, { id: 'ciudad', nombre: 'Ciudad' }];
function valorMedida(datos: MedidasValidacion, id: keyof MedidasValidacion) {
  if (id === 'followers') return formatearFollowers(datos.followers);
  if (id === 'er') return formatearER(datos.er);
  if (id === 'genero') return generoTexto(datos.genero);
  return datos[id] ?? '—';
}

export default function Validacion({ navegar }: { navegar: (ruta: string) => void }) {
  const [datos, establecerDatos] = useState<DatosValidacion | null>(null);
  const [error, establecerError] = useState('');
  const [vacia, establecerVacia] = useState(false);
  const [diferencias, establecerDiferencias] = useState(false);
  const [busqueda, establecerBusqueda] = useState('');
  const [intento, establecerIntento] = useState(0);
  useEffect(() => { const controlador = new AbortController(); establecerError(''); establecerVacia(false); void obtenerValidacion(controlador.signal).then(establecerDatos).catch((fallo: unknown) => { if (!controlador.signal.aborted) { if (fallo instanceof ErrorAPI && fallo.estado === 404) establecerVacia(true); else establecerError(fallo instanceof Error ? fallo.message : 'No pudimos cargar la validación.'); } }); return () => controlador.abort(); }, [intento]);
  const pasan = datos?.criterios.filter((criterio) => criterio.pasa).length ?? 0;
  const filas = datos?.filas.filter((fila) => (!diferencias || Object.values(fila.coincide).some((valor) => !valor)) && fila.usuario.toLowerCase().includes(busqueda.toLowerCase().replace(/^@/, '')));
  return <main id="contenido" tabIndex={-1} className="contenedor pagina-validacion"><div className="titulo-validacion"><Etiqueta>Los datos, sobre la mesa</Etiqueta><h1>¿Funciona? La comparamos<br />con {PRODUCTO.referenciaValidacion}<span className="punto-lila">.</span></h1><p>La misma lista. Dos miradas. Así medimos qué tan cerca estamos.</p></div>
    {vacia ? <Tarjeta className="estado-vacio"><Acuarela variante="mar" /><div><FlaskConical size={32} /><h2>Aún no corremos la validación</h2><p>Cuando esté lista, verás aquí los resultados de cada criterio.</p><Boton variante="secundaria" onClick={() => navegar('/')}>Armar una lista<ArrowRight size={16} /></Boton></div></Tarjeta> : error ? <Tarjeta className="estado-vacio"><h2>No pudimos cargar la validación</h2><p role="alert">{error}</p><Boton variante="secundaria" onClick={() => establecerIntento(intento + 1)}>Volver a intentar</Boton></Tarjeta> : !datos ? <div role="status" aria-label="Cargando validación"><Esqueleto className="esqueleto-hero" /><div className="criterios-rejilla">{[0, 1, 2, 3].map((indice) => <Esqueleto className="esqueleto-tarjeta" key={indice} />)}</div></div> : <>
      <section className="veredicto"><Acuarela variante="lima" /><div><Etiqueta>Validación · {formatearFecha(datos.fecha)}</Etiqueta><h2>Pasan <span>{pasan} de {datos.criterios.length}</span> criterios.</h2><p>{datos.perfiles} perfiles comparados con {PRODUCTO.referenciaValidacion}. Revisa el resultado y la cobertura de cada criterio.</p></div><div className="veredicto-sello"><span><Check size={22} />{pasan}/{datos.criterios.length}</span><small>criterios</small></div><Monograma /></section>
      <div className="seccion-cabecera"><div><Etiqueta>01 / El resultado, criterio por criterio</Etiqueta><h2>Qué está listo y qué sigue.</h2></div><span className="texto-secundario">Metas definidas antes de comparar</span></div>
      <section className="criterios-rejilla" aria-label="Criterios de validación">{datos.criterios.map((criterio) => <Tarjeta className="criterio" key={criterio.id}><div className="criterio-superior"><h3>{criterio.nombre}</h3><Chip className={criterio.pasa ? 'estado-completa' : 'estado-error'}>{criterio.pasa ? <><Check size={12} /> Pasa</> : 'Todavía no'}</Chip></div><strong className="resultado-criterio">{criterio.resultado == null ? '—' : criterio.formato === 'porcentaje' ? `${Math.round(criterio.resultado * 100)} %` : criterio.formato === 'usd' ? formatearUSD(criterio.resultado) : formatearDuracion(criterio.resultado * 60)}</strong><p className="meta-criterio">Meta: {criterio.meta}</p><p className="detalle-criterio">{criterio.detalle}</p></Tarjeta>)}</section>
      <div className="seccion-cabecera comparacion-cabecera"><div><Etiqueta>02 / Mira el detalle</Etiqueta><h2>Perfil por perfil.</h2></div><div className="controles-comparacion"><label className="control-check"><input type="checkbox" checked={diferencias} onChange={(evento) => establecerDiferencias(evento.target.checked)} /> Solo diferencias</label><label className="buscador-historial"><Search size={16} /><input aria-label="Buscar perfil en validación" placeholder="Busca un usuario" value={busqueda} onChange={(evento) => establecerBusqueda(evento.target.value)} /></label></div></div>
      <p className="leyenda-validacion"><span><i className="punto-coincide" />Coincide con la meta</span><span><i className="punto-diferencia" />Diferencia por revisar</span><span>{filas?.length} de {datos.perfiles} perfiles <ChevronDown size={12} /></span></p>
      <div className="tabla-validacion" role="region" aria-label={`Comparación del motor y ${PRODUCTO.referenciaValidacion}`} tabIndex={0}><table><thead><tr><th rowSpan={2} scope="col">Perfil</th>{medidas.map((medida) => <th colSpan={2} key={medida.id} scope="colgroup">{medida.nombre}</th>)}</tr><tr>{medidas.map((medida) => <Fragment key={medida.id}><th scope="col">Motor</th><th scope="col">{PRODUCTO.referenciaValidacion}</th></Fragment>)}</tr></thead><tbody>{filas?.map((fila) => <tr key={fila.usuario}><th scope="row">@{fila.usuario}{fila.nota && <small>{fila.nota}</small>}</th>{medidas.map((medida) => <Fragment key={medida.id}><td><span className="valor-comparado"><i className={fila.coincide[medida.id] ? 'punto-coincide' : 'punto-diferencia'} role="img" aria-label={fila.coincide[medida.id] ? 'Coincide' : 'Diferencia'} />{valorMedida(fila.motor, medida.id)}</span></td><td>{valorMedida(fila.referencia, medida.id)}</td></Fragment>)}</tr>)}</tbody></table>{filas?.length === 0 && <div className="sin-diferencias"><h3>No hay perfiles con estos filtros</h3><p>Prueba con otro usuario o muestra todos los perfiles.</p><Boton variante="secundaria" onClick={() => { establecerBusqueda(''); establecerDiferencias(false); }}>Limpiar filtros</Boton></div>}</div><p className="validacion-nota">Edad, género y ciudad son estimaciones. Esta comparación ayuda a evaluar su utilidad; no las convierte en datos oficiales.</p>
    </>}
  </main>;
}
