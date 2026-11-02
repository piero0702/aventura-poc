import { useCallback, useEffect, useState } from 'react';
import { obtenerLista } from './api';
import type { EstadoLista } from './tipos';

export function useSondeo(id: string) {
  const [lista, cambiarLista] = useState<EstadoLista | null>(null);
  const [error, cambiarError] = useState<string | null>(null);
  const [cargando, cambiarCargando] = useState(true);
  const [intento, cambiarIntento] = useState(0);
  const recargar = useCallback(() => cambiarIntento((actual) => actual + 1), []);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    cambiarLista(null);
    cambiarError(null);
    cambiarCargando(true);

    async function consultar() {
      try {
        const estado = await obtenerLista(id, controlador.signal);
        if (!vigente) return;
        cambiarLista(estado);
        cambiarError(null);
        cambiarCargando(false);
        if (estado.estado === 'pendiente' || estado.estado === 'en_proceso') temporizador = setTimeout(() => { void consultar(); }, 3000);
      } catch (problema) {
        if (!vigente || controlador.signal.aborted) return;
        cambiarError(problema instanceof Error ? problema.message : 'No pudimos actualizar la lista. Vuelve a intentarlo.');
        cambiarCargando(false);
      }
    }

    void consultar();
    return () => {
      vigente = false;
      controlador.abort();
      clearTimeout(temporizador);
    };
  }, [id, intento]);

  return { lista, error, cargando, recargar };
}
