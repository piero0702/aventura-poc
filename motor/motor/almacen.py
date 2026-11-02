"""Caché y registro persistente con SQL y tipos portables a PostgreSQL.

SQLite es solo el adaptador local. No usa PRAGMA, AUTOINCREMENT, JSONB ni UPSERT;
al migrar, cambian el driver y los marcadores de parámetros, no las tablas.
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from motor.configuracion import ruta_local

ESQUEMA = (
    '''CREATE TABLE IF NOT EXISTS cache_pasos (
      usuario VARCHAR(30) NOT NULL, paso VARCHAR(40) NOT NULL, clave VARCHAR(64) NOT NULL,
      contenido TEXT NOT NULL, vence VARCHAR(40) NOT NULL,
      PRIMARY KEY (usuario, paso, clave))''',
    '''CREATE TABLE IF NOT EXISTS llamadas (
      id VARCHAR(36) PRIMARY KEY, corrida_id VARCHAR(36) NOT NULL,
      usuario VARCHAR(30) NOT NULL, paso VARCHAR(40) NOT NULL,
      unidades DOUBLE PRECISION NOT NULL, costo_usd DOUBLE PRECISION NOT NULL,
      estado VARCHAR(30) NOT NULL, fecha VARCHAR(40) NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS corridas (
      id VARCHAR(64) PRIMARY KEY, contenido TEXT NOT NULL)''',
)


class Almacen:
    def __init__(self, ruta: str | Path = '.motor/motor.sqlite', reloj=None):
        self.ruta = ruta_local(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.reloj = reloj or (lambda: datetime.now(timezone.utc))
        with self.conexion() as conexion:
            for sentencia in ESQUEMA:
                conexion.execute(sentencia)

    def conexion(self):
        return sqlite3.connect(self.ruta, timeout=30)

    def obtener(self, usuario: str, paso: str, clave: str = ''):
        with self.conexion() as conexion:
            fila = conexion.execute(
                'SELECT contenido, vence FROM cache_pasos WHERE usuario=? AND paso=? AND clave=?',
                (usuario, paso, clave)).fetchone()
        if fila is None or datetime.fromisoformat(fila[1]) <= self.reloj():
            return None
        return json.loads(fila[0])

    def guardar(self, usuario: str, paso: str, contenido, clave: str = ''):
        vence = (self.reloj() + timedelta(days=30)).isoformat()
        with self.conexion() as conexion:
            conexion.execute('DELETE FROM cache_pasos WHERE usuario=? AND paso=? AND clave=?', (usuario, paso, clave))
            conexion.execute('INSERT INTO cache_pasos (usuario,paso,clave,contenido,vence) VALUES (?,?,?,?,?)',
                             (usuario, paso, clave, json.dumps(contenido, ensure_ascii=False), vence))

    def registrar(self, corrida_id: str, usuario: str, paso: str, unidades: float, costo_usd: float, estado='reservado') -> str:
        identificador = str(uuid4())
        with self.conexion() as conexion:
            conexion.execute('INSERT INTO llamadas (id,corrida_id,usuario,paso,unidades,costo_usd,estado,fecha) VALUES (?,?,?,?,?,?,?,?)',
                             (identificador, corrida_id, usuario, paso, unidades, costo_usd, estado, self.reloj().isoformat()))
        return identificador

    def ajustar(self, identificador: str, unidades: float, costo_usd: float, estado='confirmado'):
        with self.conexion() as conexion:
            conexion.execute('UPDATE llamadas SET unidades=?, costo_usd=?, estado=? WHERE id=?',
                             (unidades, costo_usd, estado, identificador))

    def costos(self, corrida_id: str) -> list[dict]:
        with self.conexion() as conexion:
            filas = conexion.execute('SELECT usuario,paso,unidades,costo_usd,estado FROM llamadas WHERE corrida_id=?', (corrida_id,)).fetchall()
        return [dict(zip(('usuario', 'paso', 'unidades', 'costo_usd', 'estado'), fila)) for fila in filas]

    def guardar_corrida(self, corrida_id: str, contenido: dict):
        with self.conexion() as conexion:
            conexion.execute('DELETE FROM corridas WHERE id=?', (corrida_id,))
            conexion.execute('INSERT INTO corridas (id,contenido) VALUES (?,?)', (corrida_id, json.dumps(contenido, ensure_ascii=False)))

    def obtener_corrida(self, corrida_id: str) -> dict | None:
        with self.conexion() as conexion:
            fila = conexion.execute('SELECT contenido FROM corridas WHERE id=?', (corrida_id,)).fetchone()
        return json.loads(fila[0]) if fila else None

    def listar_corridas(self) -> list[dict]:
        """Instantáneas compartidas por CLI y HTTP, sin duplicar el registro interno.

        Cada operación abre su propia conexión, también desde BackgroundTasks.
        SQLite serializa las transacciones de escritura con timeout de 30 s;
        nunca se comparte una conexión entre hilos ni se lee durante un DELETE.
        """
        with self.conexion() as conexion:
            filas = conexion.execute("SELECT contenido FROM corridas WHERE id LIKE 'http:%'").fetchall()
        return sorted((json.loads(fila[0]) for fila in filas),
                      key=lambda datos: datos.get('fecha', ''), reverse=True)
