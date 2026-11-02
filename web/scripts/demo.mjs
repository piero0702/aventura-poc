import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// Las rutas dependen de este archivo, incluso si la carpeta se mueve o tiene espacios.
const carpetaWeb = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const procesos = [];
let terminando = false;

function enviarSenal(proceso, senal) {
  if (!proceso.pid) return;
  // El grupo puede conservar hijos aunque su proceso principal ya haya salido.
  if (process.platform !== 'win32') process.kill(-proceso.pid, senal);
  else if (proceso.exitCode === null && proceso.signalCode === null) proceso.kill(senal);
}

function detener(codigo = 0) {
  if (terminando) return;
  terminando = true;
  process.exitCode = codigo;
  for (const proceso of procesos) {
    try {
      enviarSenal(proceso, 'SIGTERM');
    } catch (error) {
      if (error.code !== 'ESRCH') process.exitCode = 1;
    }
  }
  const limite = setTimeout(() => {
    for (const proceso of procesos) {
      try {
        enviarSenal(proceso, 'SIGKILL');
      } catch { /* Ya terminó. */ }
    }
  }, 5000);
  limite.unref();
}

function iniciar(comando, argumentos, carpeta) {
  const proceso = spawn(comando, argumentos, {
    cwd: carpeta,
    stdio: 'inherit',
    detached: process.platform !== 'win32',
  });
  procesos.push(proceso);
  proceso.once('error', () => {
    console.error(`No pudimos iniciar ${comando}. Comprueba que esté instalado y disponible en PATH.`);
    detener(1);
  });
  proceso.once('exit', (codigo, senal) => {
    if (!terminando) {
      console.error(`${comando} terminó${senal ? ` (${senal})` : ` con código ${codigo}`}. Cerrando la demo.`);
      detener(codigo || 1);
    }
  });
}

process.once('SIGINT', () => detener());
process.once('SIGTERM', () => detener());
console.log('Radar local · http://127.0.0.1:5173 · Ctrl+C cierra motor y web.');
iniciar('uv', ['run', 'uvicorn', 'motor.http:crear_app', '--factory', '--host', '127.0.0.1', '--port', '8000', '--workers', '1'], resolve(carpetaWeb, '..', 'motor'));
iniciar(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'dev'], carpetaWeb);
