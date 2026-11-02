import { useState } from 'react';
import { ChevronDown, Clock, Coins, ShieldCheck } from 'lucide-react';
import { Campo, Chip, Etiqueta, Tarjeta } from './componentes';
import { formatearUSD } from './utilidades';
import { calcular, confiabilidad, formatearSoles, formatearTiempo, NIVELES, revisarNecesarios, seguidoresNecesarios, SUPUESTOS, type Supuestos } from './calculo';

// Calculadora interna (/calculadora): no está en el menú. Costos (soles y USD), tiempo y la confiabilidad que dan
// los valores que se escriban. Los niveles solo recomiendan: al tocarlos llenan los campos.
const pct = (valor: number) => `${Math.round(valor * 100)} %`;
const num = (valor: string) => Number(valor) || 0;

const ETIQUETAS_SUPUESTOS: [keyof Supuestos, string][] = [
  ['reparto', 'Audiencia de referencia (% del género mayoritario)'], ['tasaPublicidad', '% de posts que son publicidad'],
  ['revisarBase', 'Reels a revisar si no se exige encontrar publicidad'], ['cambio', 'Tipo de cambio (S/ por USD)'],
  ['apifySeguidores', 'Apify seguidores (USD / 1,000)'], ['apifyReels', 'Apify reels (USD / 1,000)'], ['apifyPerfiles', 'Apify perfiles (USD / 1,000)'],
  ['groqHora', 'Groq (USD / hora de audio)'], ['segundosReel', 'Segundos de audio por reel'], ['jevMillon', 'Jev (USD / millón de tokens)'],
  ['tokensPerfil', 'Tokens de Jev por perfil'], ['loteGroq', 'Transcripciones por lote de Groq'], ['segundosLote', 'Segundos por lote de Groq'],
  ['arranque', 'Arranque de Apify (s)'], ['segundosPerfil', 'Análisis por perfil (s, 4 hilos)'],
];

function Monto({ usd, cambio, decimales = 3 }: { usd: number; cambio: number; decimales?: number }) {
  return <>{formatearSoles(usd * cambio, decimales)} <span className="monto-soles">· {formatearUSD(usd, decimales)}</span></>;
}

function nivelDe(valor: number) {
  return valor >= 0.99 ? 'Máximo' : valor >= 0.95 ? 'Costo-beneficio' : valor >= 0.9 ? 'Bueno' : valor >= 0.8 ? 'Decente' : 'Bajo';
}

export default function Calculadora() {
  const [seguidores, establecerSeguidores] = useState('50');
  const [reels, establecerReels] = useState('5');
  const [revisar, establecerRevisar] = useState('10');
  const [perfiles, establecerPerfiles] = useState('100');
  const [perfilesMes, establecerPerfilesMes] = useState('1000');
  const [conPublicidad, establecerConPublicidad] = useState(false);
  const [supuestos, establecerSupuestos] = useState<Record<keyof Supuestos, string>>(() => Object.fromEntries(Object.entries(SUPUESTOS).map(([clave, valor]) => [clave, String(valor)])) as Record<keyof Supuestos, string>);
  const s = Object.fromEntries(Object.entries(supuestos).map(([clave, valor]) => [clave, num(valor)])) as Supuestos;
  const recomendado = (confianza: number) => ({ seguidores: seguidoresNecesarios(confianza, s.reparto / 100) ?? 0, reels: num(reels) || 5,
    revisar: conPublicidad ? revisarNecesarios(confianza, s.tasaPublicidad / 100) : s.revisarBase });
  const costo = calcular(num(perfiles), num(seguidores), num(reels), num(revisar), s);
  const real = confiabilidad(num(seguidores), num(reels), num(revisar), s);
  const niveles = NIVELES.map((nivel) => { const opciones = recomendado(nivel.confianza); return { ...nivel, ...opciones, costo: calcular(num(perfiles), opciones.seguidores, opciones.reels, opciones.revisar, s) }; });
  const elegido = (nivel: typeof niveles[number]) => num(seguidores) === nivel.seguidores && num(reels) === nivel.reels && num(revisar) === nivel.revisar;
  function aplicar(opciones: { seguidores: number; reels: number; revisar: number }) { establecerSeguidores(String(opciones.seguidores)); establecerReels(String(opciones.reels)); establecerRevisar(String(opciones.revisar)); }
  return <main id="contenido" tabIndex={-1} className="contenedor pagina-validacion pagina-calculadora">
    <div className="titulo-validacion"><Etiqueta>Uso interno de Praxia</Etiqueta><h1>¿Cuánto cuesta<br />un dato confiable<span className="punto-lila">?</span></h1><p>Escribe los valores que quieras: arriba ves la confiabilidad que dan y abajo cuánto cuestan, en soles y en dólares.</p></div>
    <div className="calculadora-rejilla">
      <Tarjeta className="calculadora-panel">
        <h2><Coins size={18} /> Tu lista</h2>
        <div className="dos-campos calculadora-campos">
          <Campo etiqueta="Seguidores en la muestra" type="number" min="0" ayuda="Con menos de 25 (y más de 0), el motor pide 25." value={seguidores} onChange={(evento) => establecerSeguidores(evento.target.value)} />
          <Campo etiqueta="Reels recientes a revisar" type="number" min="0" max="100" value={revisar} onChange={(evento) => establecerRevisar(evento.target.value)} />
          <Campo etiqueta="Reels de publicidad a transcribir" type="number" min="0" max="50" ayuda="Los más recientes; 0 = sin transcripción." value={reels} onChange={(evento) => establecerReels(evento.target.value)} />
          <Campo etiqueta="Perfiles en la lista" type="number" min="1" value={perfiles} onChange={(evento) => establecerPerfiles(evento.target.value)} />
          <Campo etiqueta="Perfiles al mes" type="number" min="0" value={perfilesMes} onChange={(evento) => establecerPerfilesMes(evento.target.value)} />
        </div>
        <h2 className="calculadora-subtitulo"><ShieldCheck size={18} /> Recomendar por confiabilidad</h2>
        <div className="calculadora-presets cuatro" role="group" aria-label="Recomendar por confiabilidad">{niveles.map((nivel) => <button type="button" key={nivel.nombre} aria-pressed={elegido(nivel)} onClick={() => aplicar(nivel)}>{pct(nivel.confianza)}<small>{nivel.nombre}</small></button>)}</div>
        <label className="control-check"><input type="checkbox" checked={conPublicidad} onChange={(evento) => establecerConPublicidad(evento.target.checked)} /> Que la recomendación también asegure encontrar la publicidad</label>
        <p className="ayuda">Género: probabilidad de acertar el género mayoritario de una audiencia {s.reparto}/{100 - s.reparto}. Publicidad: probabilidad de encontrar al menos un reel de publicidad entre los revisados, si el creador hace publicidad en el {s.tasaPublicidad} % de sus posts. Followers, ER, categoría y ciudad no dependen de estas opciones; la edad no mejora con más muestra.</p>
        <details className="plegable"><summary><span>Supuestos y tarifas</span><ChevronDown size={17} /></summary><div className="plegable-interior dos-campos">{ETIQUETAS_SUPUESTOS.map(([clave, etiqueta]) => <Campo key={clave} etiqueta={etiqueta} type="number" min="0" step="any" value={supuestos[clave]} onChange={(evento) => establecerSupuestos({ ...supuestos, [clave]: evento.target.value })} />)}<p className="ayuda ancho-completo">Tarifas de motor/precios.yaml, sin IGV. Tiempos medidos el 28-oct (8 perfiles nuevos en 111 s). El 8 % de publicidad se midió en 2,225 posts de la caché. Groq va en lotes de {s.loteGroq} cada {s.segundosLote} s.</p></div></details>
      </Tarjeta>

      <div className="calculadora-resultados">
        <Tarjeta className="calculadora-bloque">
          <div className="calculadora-cabeza"><h2><ShieldCheck size={18} /> Confiabilidad de tus valores</h2><Chip>{num(seguidores)} seg. · {num(revisar)} revisados · {num(reels)} a transcribir</Chip></div>
          <div className="calculadora-cifras">
            <div><span className="cifra-grande">{pct(real.genero)}</span><span className="cifra-etiqueta">género de la audiencia · {nivelDe(real.genero)}</span></div>
            <div><span className="cifra-grande">{pct(real.publicidad)}</span><span className="cifra-etiqueta">encuentra publicidad · {nivelDe(real.publicidad)}</span></div>
          </div>
        </Tarjeta>

        <Tarjeta className="calculadora-bloque">
          <div className="calculadora-cabeza"><h2><Coins size={18} /> Costo</h2></div>
          <div className="calculadora-cifras">
            <div><span className="cifra-grande">{formatearSoles(costo.porPerfil * s.cambio, 3)}</span><span className="cifra-etiqueta">por perfil · {formatearUSD(costo.porPerfil)}</span></div>
            <div><span className="cifra-grande">{formatearSoles(costo.porPerfil * num(perfilesMes) * s.cambio)}</span><span className="cifra-etiqueta">al mes por {num(perfilesMes).toLocaleString('es-PE')} perfiles · {formatearUSD(costo.porPerfil * num(perfilesMes), 2)}</span></div>
          </div>
          <dl className="calculadora-detalle">
            <div><dt>La lista de {num(perfiles).toLocaleString('es-PE')} perfiles</dt><dd><Monto usd={costo.porLista} cambio={s.cambio} decimales={2} /></dd></div>
            <div><dt>Reels de publicidad transcritos (promedio por perfil)</dt><dd>{costo.transcritos.toLocaleString('es-PE', { maximumFractionDigits: 1 })}</dd></div>
            <div><dt><Clock size={13} /> Tiempo de la lista ({costo.lotes} lotes de Groq)</dt><dd>{formatearTiempo(costo.tiempo)}{costo.cuelloGroq ? ' · manda Groq' : ''}</dd></div>
          </dl>
          <ul className="calculadora-barras">{Object.entries(costo.pasos).map(([paso, monto]) => <li key={paso}><span>{paso}</span><i style={{ width: `${monto / Math.max(...Object.values(costo.pasos), 1e-9) * 100}%` }} /><b><Monto usd={monto} cambio={s.cambio} decimales={4} /></b></li>)}</ul>
        </Tarjeta>

        <Tarjeta className="calculadora-bloque">
          <div className="calculadora-cabeza"><h2>Lo que recomienda cada nivel</h2><span className="texto-secundario">Toca una fila para usarla</span></div>
          <div className="tabla-calculadora" role="region" aria-label="Recomendación por nivel de confiabilidad" tabIndex={0}><table>
            <thead><tr><th scope="col">Nivel</th><th scope="col">Muestra</th><th scope="col">Por perfil</th><th scope="col">Al mes</th><th scope="col">Tiempo</th></tr></thead>
            <tbody>{niveles.map((nivel) => <tr key={nivel.nombre} className={elegido(nivel) ? 'fila-elegida' : undefined} onClick={() => aplicar(nivel)}>
              <th scope="row">{nivel.nombre}<small>{pct(nivel.confianza)}</small></th>
              <td>{nivel.seguidores} seg. · {nivel.revisar} reels revisados</td>
              <td>{formatearSoles(nivel.costo.porPerfil * s.cambio, 3)}<small>{formatearUSD(nivel.costo.porPerfil)}</small></td>
              <td>{formatearSoles(nivel.costo.porPerfil * num(perfilesMes) * s.cambio, 0)}<small>{formatearUSD(nivel.costo.porPerfil * num(perfilesMes), 0)}</small></td>
              <td>{formatearTiempo(nivel.costo.tiempo)}</td>
            </tr>)}</tbody>
          </table></div>
        </Tarjeta>
      </div>
    </div>
  </main>;
}
