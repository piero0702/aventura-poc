import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { obtenerListas } from './api';
import Historial from './Historial';

vi.mock('./api', () => ({ obtenerListas: vi.fn() }));
afterEach(cleanup);

describe('historial de corridas en proceso', () => {
  it('conserva el costo medido y muestra rayas cuando no hay duración ni cantidad final', async () => {
    vi.mocked(obtenerListas).mockResolvedValue([{
      id: 'corrida-sintetica', estado: 'en_proceso', fecha: 'fecha-invalida', fuente: '@cuenta.sintetica',
      perfiles_procesados: null, duracion_segundos: null, costo_total_usd: .12, marca: '',
    }]);
    render(<Historial navegar={vi.fn()} />);
    const tabla = await screen.findByRole('region', { name: 'Historial de listas' });
    const celdas = within(within(tabla).getAllByRole('row')[1]).getAllByRole('cell');
    expect(celdas[1]).toHaveTextContent('—');
    expect(celdas[3]).toHaveTextContent('—');
    expect(celdas[4]).toHaveTextContent('USD 0.12');
    expect(celdas[5]).toHaveTextContent('—');
  });
});
