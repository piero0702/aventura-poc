import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { etapasPrueba } from '../mock/perfiles-prueba';
import { obtenerLista } from './api';
import { useSondeo } from './useSondeo';

vi.mock('./api', () => ({ obtenerLista: vi.fn() }));
const obtenerSimulado = vi.mocked(obtenerLista);

beforeEach(() => {
  vi.useFakeTimers();
  obtenerSimulado.mockReset();
});

afterEach(() => {
  cleanup();
  vi.clearAllTimers();
  vi.useRealTimers();
});

describe('sondeo de estado', () => {
  it('pasa de pendiente a en proceso y completa cada 3 segundos y deja de consultar', async () => {
    for (const etapa of etapasPrueba) obtenerSimulado.mockResolvedValueOnce(etapa);
    const { result } = renderHook(() => useSondeo(etapasPrueba[0].id));
    await act(async () => { await Promise.resolve(); });
    expect(result.current.lista?.estado).toBe('pendiente');
    expect(result.current.cargando).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(2999); });
    expect(obtenerSimulado).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(result.current.lista?.estado).toBe('en_proceso');
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(result.current.lista?.estado).toBe('completa');
    await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
    expect(obtenerSimulado).toHaveBeenCalledTimes(3);
  });

  it('cancela la solicitud y el temporizador al salir de la pantalla', async () => {
    obtenerSimulado.mockResolvedValue(etapasPrueba[0]);
    const { unmount } = renderHook(() => useSondeo(etapasPrueba[0].id));
    await act(async () => { await Promise.resolve(); });
    const señal = obtenerSimulado.mock.calls[0][1];
    unmount();
    expect(señal?.aborted).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(obtenerSimulado).toHaveBeenCalledTimes(1);
  });

  it('muestra el error y permite reintentar sin dejar sondeos duplicados', async () => {
    obtenerSimulado.mockRejectedValueOnce(new Error('No pudimos conectar con el motor.')).mockResolvedValueOnce(etapasPrueba[2]);
    const { result } = renderHook(() => useSondeo(etapasPrueba[0].id));
    await act(async () => { await Promise.resolve(); });
    expect(result.current.error).toBe('No pudimos conectar con el motor.');
    await act(async () => { result.current.recargar(); });
    expect(result.current.error).toBeNull();
    expect(result.current.lista?.estado).toBe('completa');
    expect(obtenerSimulado).toHaveBeenCalledTimes(2);
  });
});
