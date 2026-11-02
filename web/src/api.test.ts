import { afterEach, describe, expect, it, vi } from 'vitest';
import { obtenerListas } from './api';

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe('conexión con el motor local', () => {
  it('explica que falta token y no hace la solicitud', async () => {
    vi.stubEnv('VITE_MOTOR_TOKEN', '');
    const solicitud = vi.fn();
    vi.stubGlobal('fetch', solicitud);
    await expect(obtenerListas()).rejects.toThrow('Falta el token del motor');
    expect(solicitud).not.toHaveBeenCalled();
  });

  it('envía el token configurado al motor', async () => {
    vi.stubEnv('VITE_MOTOR_TOKEN', 'token-local');
    const solicitud = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }));
    vi.stubGlobal('fetch', solicitud);
    expect(await obtenerListas()).toEqual([]);
    const opciones = solicitud.mock.calls[0][1] as RequestInit;
    expect(new Headers(opciones.headers).get('Authorization')).toBe('Bearer token-local');
  });

  it.each(['red', 'proxy'])('explica que el motor está apagado ante un fallo de %s', async (tipo) => {
    vi.stubEnv('VITE_MOTOR_TOKEN', 'token-local');
    vi.stubGlobal('fetch', tipo === 'red' ? vi.fn().mockRejectedValue(new TypeError('Failed to fetch')) : vi.fn().mockResolvedValue(new Response('', { status: 500 })));
    await expect(obtenerListas()).rejects.toThrow('El motor no está encendido');
  });
});
