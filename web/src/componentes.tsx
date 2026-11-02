import { useId, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react';
import { Info } from 'lucide-react';
import type { Perfil } from './tipos';

export function Boton({ variante = 'primaria', className = '', children, ...propiedades }: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: 'primaria' | 'secundaria' | 'fantasma' }) {
  return <button className={`boton boton-${variante} ${className}`} {...propiedades}>{children}</button>;
}

export function Campo({ etiqueta, ayuda, className = '', id, ...propiedades }: InputHTMLAttributes<HTMLInputElement> & { etiqueta: string; ayuda?: string }) {
  const generado = useId();
  const identificador = id || generado;
  return <div className={`campo-grupo ${className}`}><label htmlFor={identificador}>{etiqueta}</label><input id={identificador} aria-describedby={ayuda ? `${identificador}-ayuda` : undefined} {...propiedades} />{ayuda && <small id={`${identificador}-ayuda`}>{ayuda}</small>}</div>;
}

export function Chip({ children, className = '', ...propiedades }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={`chip ${className}`} {...propiedades}>{children}</span>;
}

export function Tarjeta({ children, className = '', ...propiedades }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`tarjeta ${className}`} {...propiedades}>{children}</div>;
}

export function Etiqueta({ children, className = '', ...propiedades }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={`etiqueta ${className}`} {...propiedades}>{children}</p>;
}

export function CifraGrande({ valor, etiqueta, className = '' }: { valor: ReactNode; etiqueta: string; className?: string }) {
  return <div className={`cifra-grupo ${className}`}><span className="cifra-grande">{valor}</span><span className="cifra-etiqueta">{etiqueta}</span></div>;
}

export function Monograma({ className = '' }: { className?: string }) {
  return <span className={`monograma ${className}`} aria-label="Aventura PR"><span>a</span><sup>pr</sup></span>;
}

export function Avatar({ perfil, tamano = 'normal' }: { perfil: Pick<Perfil, 'nombre' | 'numero'>; tamano?: 'normal' | 'grande' | string }) {
  const iniciales = (perfil.nombre ?? '').split(' ').slice(0, 2).map((parte) => parte[0]).join('');
  return <span aria-hidden="true" className={`avatar avatar-${tamano} avatar-color-${perfil.numero % 5}`}>{iniciales}</span>;
}

export function BadgeEstimado({ muestra, fuente }: { muestra: number; fuente?: string | null }) {
  const id = useId();
  const mensaje = fuente === 'contenido' ? 'Estimado por IA a partir del contenido del perfil; sin muestra de seguidores.' : fuente === 'seguidores' ? `Estimado por IA sobre una muestra de ${muestra} seguidores.` : 'Estimado por IA. La fuente y el tamaño de la muestra aparecen en cada ficha.';
  return <span className="estimado-contenedor"><button type="button" className="badge-estimado" aria-describedby={id}><Info size={11} aria-hidden="true" /> Estimado</button><span role="tooltip" id={id} className="tooltip">{mensaje}</span></span>;
}

export function Esqueleto({ className = '' }: { className?: string }) {
  return <div className={`esqueleto ${className}`} aria-hidden="true" />;
}

export function Acuarela({ variante = 'mar', className = '' }: { variante?: 'mar' | 'lila' | 'lima'; className?: string }) {
  const id = useId().replace(/:/g, '');
  const colores = variante === 'lila' ? ['#D59FFF', '#497CDD', '#69C9BB', '#D59FFF'] : variante === 'lima' ? ['#DFE270', '#69C9BB', '#3BDCE1', '#DFE270'] : ['#3BDCE1', '#48BBD8', '#497CDD', '#DFE270'];
  return <svg className={`acuarela ${className}`} viewBox="0 0 900 650" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <defs>
      <filter id={`${id}-agua`} x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".009 .014" numOctaves="3" seed="16" result="ruido" /><feDisplacementMap in="SourceGraphic" in2="ruido" scale="120" xChannelSelector="R" yChannelSelector="G" /><feGaussianBlur stdDeviation="17" /></filter>
      <filter id={`${id}-grano`}><feTurbulence type="fractalNoise" baseFrequency=".62" numOctaves="3" stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
      {colores.map((color, indice) => <radialGradient key={color + indice} id={`${id}-mancha-${indice}`}><stop offset="0" stopColor={color} stopOpacity=".82" /><stop offset=".55" stopColor={color} stopOpacity=".55" /><stop offset="1" stopColor={color} stopOpacity="0" /></radialGradient>)}
    </defs>
    <rect width="900" height="650" fill="#F2F0EC" />
    <g filter={`url(#${id}-agua)`}><ellipse cx="210" cy="400" rx="430" ry="330" fill={`url(#${id}-mancha-0)`} /><ellipse cx="490" cy="200" rx="430" ry="350" fill={`url(#${id}-mancha-1)`} /><ellipse cx="860" cy="480" rx="370" ry="320" fill={`url(#${id}-mancha-2)`} /><ellipse cx="90" cy="30" rx="400" ry="280" fill={`url(#${id}-mancha-3)`} /></g>
    <rect width="900" height="650" filter={`url(#${id}-grano)`} opacity=".08" style={{ mixBlendMode: 'multiply' }} />
  </svg>;
}
