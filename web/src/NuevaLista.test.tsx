import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { entradasUsuariosPrueba, etapasPrueba, estimacionPrueba, formularioPrueba } from '../mock/perfiles-prueba';
import { crearLista, obtenerLista } from './api';
import NuevaLista from './NuevaLista';

vi.mock('./api', () => ({ crearLista: vi.fn(), obtenerLista: vi.fn() }));
const crearSimulado = vi.mocked(crearLista);
const obtenerSimulado = vi.mocked(obtenerLista);

beforeEach(() => {
  vi.stubEnv('VITE_MOTOR_TOKEN', 'token-local');
  vi.stubEnv('VITE_PERMITIR_SIMULADO', 'false');
  crearSimulado.mockReset().mockResolvedValue({ id: 'lista-prueba', estado: 'pendiente' });
  obtenerSimulado.mockReset();
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllEnvs(); });

describe('nueva lista', () => {
  it('envía los parámetros internos sin pedírselos al usuario', async () => {
    render(<NuevaLista navegar={vi.fn()} />);
    expect(screen.queryByText('Opciones avanzadas')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.click(screen.getByRole('button', { name: 'Armar lista' }));
    await waitFor(() => expect(crearSimulado).toHaveBeenCalled());
    expect(crearSimulado.mock.calls[0][0]).toMatchObject({ reels: 5, reels_revisar: 10, muestra_seguidores: 50, limite: 200, presupuesto_usd: 15 });
  });

  it('en /sin-limites envía los parámetros que escribe Praxia', async () => {
    render(<NuevaLista navegar={vi.fn()} sinLimites />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.change(screen.getByLabelText('Reels de publicidad a transcribir (0–10)'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Reels recientes a revisar (0–100)'), { target: { value: '20' } });
    fireEvent.change(screen.getByLabelText('Seguidores en la muestra'), { target: { value: '300' } });
    fireEvent.change(screen.getByLabelText('Límite de perfiles'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Presupuesto (USD)'), { target: { value: '40' } });
    fireEvent.click(screen.getByRole('button', { name: 'Armar lista' }));
    await waitFor(() => expect(crearSimulado).toHaveBeenCalled());
    expect(crearSimulado.mock.calls[0][0]).toMatchObject({ reels: 2, reels_revisar: 20, muestra_seguidores: 300, presupuesto_usd: 40 });
    expect(crearSimulado.mock.calls[0][0]).not.toHaveProperty('limite');
  });

  it('omite el brief si no se completó y no ofrece modo prueba por defecto', async () => {
    render(<NuevaLista navegar={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    expect(screen.queryByLabelText('Modo prueba (sin costo)')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Armar lista' }));
    await waitFor(() => expect(crearSimulado).toHaveBeenCalledOnce());
    expect(crearSimulado.mock.calls[0][0]).not.toHaveProperty('brief');
    expect(crearSimulado.mock.calls[0][0].simulado).toBe(false);
  });

  it('envía simulado solo cuando se habilitó y se activó el interruptor', async () => {
    vi.stubEnv('VITE_PERMITIR_SIMULADO', 'true');
    render(<NuevaLista navegar={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.click(screen.getByLabelText('Modo prueba (sin costo)'));
    fireEvent.click(screen.getByRole('button', { name: 'Armar lista' }));
    await waitFor(() => expect(crearSimulado).toHaveBeenCalledOnce());
    expect(crearSimulado.mock.calls[0][0].simulado).toBe(true);
  });

  it('normaliza la referencia y envía la marca pendiente del brief al armar', async () => {
    const navegar = vi.fn();
    render(<NuevaLista navegar={navegar} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.change(screen.getByLabelText('Marca'), { target: { value: formularioPrueba.marca } });
    fireEvent.change(screen.getByLabelText('Marcas a evitar'), { target: { value: formularioPrueba.marcaPendiente } });
    fireEvent.click(screen.getByRole('button', { name: 'Armar lista' }));
    await waitFor(() => expect(navegar).toHaveBeenCalledWith('/listas/lista-prueba'));
    expect(crearSimulado).toHaveBeenCalledWith(expect.objectContaining({ referencia: 'casa.bruma', usuarios: null, estimar: false, brief: expect.objectContaining({ marca: formularioPrueba.marca, marcas_a_evitar: [formularioPrueba.marcaPendiente] }) }), expect.any(AbortSignal));
  });

  it('envía solo usuarios normalizados y únicos cuando eliges pegarlos', async () => {
    const navegar = vi.fn();
    render(<NuevaLista navegar={navegar} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Pegar usuarios' }));
    fireEvent.change(screen.getByLabelText('Usuarios, uno por línea'), { target: { value: entradasUsuariosPrueba.mixta } });
    fireEvent.click(screen.getByRole('button', { name: 'Armar lista' }));
    await waitFor(() => expect(navegar).toHaveBeenCalledOnce());
    expect(crearSimulado).toHaveBeenCalledWith(expect.objectContaining({ referencia: null, usuarios: entradasUsuariosPrueba.esperada }), expect.any(AbortSignal));
  });

  it('rechaza la ausencia de fuente antes de llamar al motor', async () => {
    render(<NuevaLista navegar={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Armar lista' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ingresa una cuenta de referencia válida');
    expect(crearSimulado).not.toHaveBeenCalled();
  });

  it('muestra el desglose de estimación sin navegar ni lanzar una corrida real', async () => {
    const navegar = vi.fn();
    obtenerSimulado.mockResolvedValue(estimacionPrueba);
    render(<NuevaLista navegar={navegar} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular costo' }));
    expect(await screen.findByRole('status')).toHaveTextContent('USD 9.80');
    expect(screen.getByRole('status')).toHaveTextContent('USD 0.049 por perfil');
    expect(crearSimulado).toHaveBeenCalledWith(expect.objectContaining({ estimar: true }), expect.any(AbortSignal));
    expect(navegar).not.toHaveBeenCalled();
  });

  it.each([
    ['Cuenta de referencia', entradasUsuariosPrueba.esperada[0]],
    ['Marca', formularioPrueba.marca],
    ['¿Con quién quieres conectar?', formularioPrueba.publico],
    ['Marcas a evitar', formularioPrueba.marcaPendiente],
    ['Followers mínimos', '15000'],
    ['Followers máximos', '250000'],
  ])('invalida el costo anterior al cambiar %s', async (etiqueta, valor) => {
    obtenerSimulado.mockResolvedValue(estimacionPrueba);
    render(<NuevaLista navegar={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular costo' }));
    expect(await screen.findByRole('status')).toHaveTextContent('USD 9.80');
    fireEvent.change(screen.getByLabelText(etiqueta), { target: { value: valor } });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('invalida el costo al cambiar la fuente con el teclado', async () => {
    obtenerSimulado.mockResolvedValue(estimacionPrueba);
    render(<NuevaLista navegar={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular costo' }));
    await screen.findByRole('status');
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Desde una cuenta de referencia' }), { key: 'ArrowRight' });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Pegar usuarios' })).toHaveFocus();
  });

  it('cancela una petición al editar los datos e ignora su respuesta tardía', async () => {
    let completar: ((valor: typeof estimacionPrueba) => void) | undefined;
    obtenerSimulado.mockImplementation(() => new Promise((resolver) => { completar = resolver; }));
    render(<NuevaLista navegar={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular costo' }));
    await waitFor(() => expect(obtenerSimulado).toHaveBeenCalledOnce());
    const senal = obtenerSimulado.mock.calls[0][1];
    fireEvent.change(screen.getByLabelText('Marca'), { target: { value: formularioPrueba.marca } });
    expect(senal?.aborted).toBe(true);
    expect(screen.getByRole('button', { name: 'Calcular costo' })).toBeEnabled();
    await act(async () => { completar?.(estimacionPrueba); });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('cancela la espera y el sondeo de estimación al salir de la pantalla', async () => {
    vi.useFakeTimers();
    obtenerSimulado.mockResolvedValue(etapasPrueba[0]);
    const { unmount } = render(<NuevaLista navegar={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Cuenta de referencia'), { target: { value: formularioPrueba.referencia } });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Calcular costo' })); });
    expect(obtenerSimulado).toHaveBeenCalledOnce();
    const senal = obtenerSimulado.mock.calls[0][1];
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(senal?.aborted).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(vi.getTimerCount()).toBe(0);
    expect(obtenerSimulado).toHaveBeenCalledOnce();
  });

});
