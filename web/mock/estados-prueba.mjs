// Variantes sintéticas del estado real del mock para revisar casos sin datos opcionales.
export function sinProgreso(estado) {
  const copia = { ...estado, estado: 'en_proceso' };
  delete copia.progreso;
  delete copia.corrida;
  delete copia.finalizada;
  delete copia.estimacion;
  return copia;
}
export const validacionPendiente = { detail: 'Aún no corremos la validación.' };
