import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import Calculadora from './Calculadora';
import { aciertoMayoria, calcular, confiabilidad, formatearTiempo, revisarNecesarios, seguidoresNecesarios } from './calculo';

afterEach(cleanup);

describe('calculadora', () => {
  it('la muestra crece con la confiabilidad (audiencia 65/35, publicidad en el 8 % de los posts)', () => {
    expect(seguidoresNecesarios(0.8, 0.65)).toBe(25);
    expect(seguidoresNecesarios(0.95, 0.65)).toBe(47);
    expect(seguidoresNecesarios(0.99, 0.65)).toBe(84);
    expect(revisarNecesarios(0.95, 0.08)).toBe(36);
    expect(revisarNecesarios(0.99, 0.08)).toBe(56);
  });

  it('revisa 20 reels y transcribe solo los de publicidad (8 % → 1.6 por perfil)', () => {
    const r = calcular(100, 50, 5, 20);
    expect(r.transcritos).toBeCloseTo(1.6, 5);
    expect(r.pasos.Reels).toBeCloseTo(0.02, 5);
    expect(r.porPerfil).toBeCloseTo(0.0425 + 0.02 + 0.0026 + 1.6 * 40 * 0.04 / 3600 + 0.00126, 5);
    expect(confiabilidad(50, 5, 20).genero).toBeCloseTo(aciertoMayoria(38, 0.65), 5);
    expect(confiabilidad(50, 5, 20).publicidad).toBeCloseTo(1 - 0.92 ** 20, 5);
  });

  it('sin reels a transcribir no se revisa ninguno', () => {
    const r = calcular(100, 50, 0, 20);
    expect(r.pasos.Reels).toBe(0);
    expect(r.transcritos).toBe(0);
    expect(confiabilidad(50, 0, 20).publicidad).toBe(0);
  });

  it('Groq va en lotes de 20 por minuto; con pocas transcripciones manda el análisis', () => {
    const r = calcular(100, 50, 5, 20);
    expect(r.lotes).toBe(8);
    expect(r.cuelloGroq).toBe(false);
    expect(formatearTiempo(r.tiempo)).toBe('11 min');
  });

  it('los niveles llenan los campos y los campos se pueden editar libremente', () => {
    render(<Calculadora />);
    fireEvent.click(screen.getByLabelText('Que la recomendación también asegure encontrar la publicidad'));
    fireEvent.click(screen.getByRole('button', { name: /99 %/ }));
    expect(screen.getByLabelText('Seguidores en la muestra')).toHaveValue(84);
    expect(screen.getByLabelText('Reels recientes a revisar')).toHaveValue(56);
    fireEvent.change(screen.getByLabelText('Reels recientes a revisar'), { target: { value: '36' } });
    expect(screen.getByText('encuentra publicidad · Costo-beneficio')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Seguidores en la muestra'), { target: { value: '0' } });
    expect(screen.getByText('género de la audiencia · Bajo')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Recomendación por nivel de confiabilidad' })).getAllByText(/^S\/ /).length).toBeGreaterThan(0);
  });
});
