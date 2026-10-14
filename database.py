"""Operaciones de almacenamiento del sistema de casilleros.

Este módulo no depende de Kivy: se puede probar en PC antes de compilar.
Los préstamos y devoluciones se registran en una sola transacción SQLite.
"""

import os
import re
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DB_NAME = "casilleros.db"


class OperacionNoPermitida(Exception):
    """Regla de negocio que impide completar una operación."""


class BusquedaAmbigua(OperacionNoPermitida):
    """Se encontró más de una persona con el nombre indicado."""


def normalizar_rut(valor):
    """Permite buscar el mismo RUT con o sin puntos y guion."""
    return re.sub(r"[.\s-]", "", str(valor or "")).upper()


def validar_rut_chileno(valor):
    """Valida un RUT/RUN individual ingresado manualmente (módulo 11)."""
    rut = normalizar_rut(valor)
    if len(rut) < 2 or len(rut) > 10 or not rut[:-1].isdigit():
        return False
    suma = sum(int(d) * factor for d, factor in zip(reversed(rut[:-1]), [2, 3, 4, 5, 6, 7] * 2))
    digito = 11 - (suma % 11)
    verificador = "0" if digito == 11 else "K" if digito == 10 else str(digito)
    return rut[-1] == verificador


def obtener_ruta_db():
    """En Android, copia la base incluida al almacenamiento privado solo una vez.

    En desktop, usa el archivo junto al programa. Si no hay archivo inicial,
    el esquema se creará vacío para evitar un error al abrir la aplicación.
    """
    incluida = Path(__file__).resolve().parent / DB_NAME
    try:
        from kivy.utils import platform
    except ImportError:
        platform = "linux"
    if platform != "android":
        return str(incluida)
    from android.storage import app_storage_path
    privada = Path(app_storage_path()) / DB_NAME
    privada.parent.mkdir(parents=True, exist_ok=True)
    if not privada.exists() and incluida.is_file():
        shutil.copy2(str(incluida), str(privada))
    return str(privada)


class GestorCasilleros:
    def __init__(self, ruta_db):
        self.ruta_db = str(ruta_db)

    @contextmanager
    def conectar(self):
        conexion = sqlite3.connect(self.ruta_db, timeout=15)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.execute("PRAGMA busy_timeout = 15000")
        try:
            yield conexion
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    def inicializar(self):
        with self.conectar() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS alumnos (
                    rut TEXT PRIMARY KEY,
                    nombre TEXT,
                    carrera TEXT,
                    area TEXT,
                    sede TEXT,
                    periodo TEXT,
                    carga TEXT,
                    rol TEXT DEFAULT 'ESTUDIANTE'
                );
                CREATE TABLE IF NOT EXISTS candados (
                    id_candado TEXT PRIMARY KEY,
                    num_casillero TEXT,
                    estado TEXT DEFAULT 'disponible'
                );
                CREATE TABLE IF NOT EXISTS prestamos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut_alumno TEXT,
                    id_candado TEXT,
                    fecha_prestamo DATETIME DEFAULT CURRENT_TIMESTAMP,
                    fecha_devolucion DATETIME,
                    estado TEXT DEFAULT 'activo',
                    FOREIGN KEY (rut_alumno) REFERENCES alumnos(rut),
                    FOREIGN KEY (id_candado) REFERENCES candados(id_candado)
                );
                CREATE TABLE IF NOT EXISTS solicitudes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut TEXT,
                    nombre TEXT,
                    rol TEXT,
                    carrera TEXT,
                    accion TEXT,
                    id_candado TEXT,
                    num_casillero TEXT,
                    fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(alumnos)")}
            if "rol" not in columnas:
                con.execute("ALTER TABLE alumnos ADD COLUMN rol TEXT DEFAULT 'ESTUDIANTE'")
            con.execute("CREATE INDEX IF NOT EXISTS idx_prestamos_rut_estado ON prestamos(rut_alumno,estado)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_prestamos_candado_estado ON prestamos(id_candado,estado)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_solicitudes_fecha ON solicitudes(fecha_hora)")
            # Evita dos préstamos activos sobre el mismo candado/persona.
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_prestamo_activo_rut ON prestamos(rut_alumno) WHERE estado='activo'")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_prestamo_activo_candado ON prestamos(id_candado) WHERE estado='activo'")

    @staticmethod
    def _buscar_en_conexion(con, criterio):
        clave = str(criterio or "").strip()
        if not clave:
            return None
        rut = normalizar_rut(clave)
        persona = con.execute("""
            SELECT rut,nombre,carrera,area,COALESCE(rol,'ESTUDIANTE') AS rol
            FROM alumnos
            WHERE REPLACE(REPLACE(REPLACE(UPPER(rut),'.',''),'-',''),' ','') = ?
            LIMIT 1
        """, (rut,)).fetchone()
        if persona:
            return dict(persona)
        coincidencias = con.execute("""
            SELECT rut,nombre,carrera,area,COALESCE(rol,'ESTUDIANTE') AS rol
            FROM alumnos WHERE nombre LIKE ? COLLATE NOCASE LIMIT 2
        """, ("%" + clave + "%",)).fetchall()
        if len(coincidencias) > 1:
            raise BusquedaAmbigua("Hay varias personas con ese nombre. Ingrese su RUT para continuar.")
        return dict(coincidencias[0]) if coincidencias else None

    def buscar_persona(self, criterio):
        with self.conectar() as con:
            return self._buscar_en_conexion(con, criterio)

    def registrar_persona(self, rut, nombre, carrera):
        rut = normalizar_rut(rut)
        nombre, carrera = nombre.strip(), carrera.strip()
        if not validar_rut_chileno(rut):
            raise OperacionNoPermitida("El RUT ingresado no es válido. Verifique el dígito verificador.")
        if not nombre or not carrera:
            raise OperacionNoPermitida("Ingrese nombre y carrera/departamento.")
        with self.conectar() as con:
            existe = con.execute("""
                SELECT rut FROM alumnos
                WHERE REPLACE(REPLACE(UPPER(rut),'.',''),'-','') = ?
            """, (rut,)).fetchone()
            if existe:
                raise OperacionNoPermitida("La persona ya está registrada en la base de datos.")
            con.execute("""
                INSERT INTO alumnos(rut,nombre,carrera,area,sede,periodo,carga,rol)
                VALUES(?,?,?,'INSTITUCIONAL','','','', 'PERSONAL')
            """, (rut, nombre, carrera))
        return rut

    def estadisticas(self):
        with self.conectar() as con:
            disponibles = con.execute("SELECT COUNT(*) FROM candados WHERE estado='disponible'").fetchone()[0]
            prestados = con.execute("SELECT COUNT(*) FROM candados WHERE estado='prestado'").fetchone()[0]
            hoy = con.execute("""
                SELECT COUNT(*) FROM solicitudes
                WHERE DATE(fecha_hora) = DATE('now','localtime')
            """).fetchone()[0]
            return {"disponibles": disponibles, "prestados": prestados, "movimientos_hoy": hoy}

    @staticmethod
    def _prestamo_activo(con, rut):
        return con.execute("""
            SELECT p.id, p.id_candado, c.num_casillero
            FROM prestamos p JOIN candados c ON p.id_candado=c.id_candado
            WHERE p.rut_alumno=? AND p.estado='activo' ORDER BY p.id LIMIT 1
        """, (rut,)).fetchone()

    def solicitar(self, rut):
        with self.conectar() as con:
            con.execute("BEGIN IMMEDIATE")
            alumno = self._buscar_en_conexion(con, rut)
            if not alumno or normalizar_rut(alumno["rut"]) != normalizar_rut(rut):
                raise OperacionNoPermitida("No se encontró el RUT registrado.")
            anterior = self._prestamo_activo(con, alumno["rut"])
            if anterior:
                raise OperacionNoPermitida(
                    "Ya tiene asignado el candado {} (casillero {}).".format(
                        anterior["id_candado"], anterior["num_casillero"]
                    )
                )
            candado = con.execute("""
                SELECT id_candado,num_casillero FROM candados
                WHERE estado='disponible' ORDER BY num_casillero,id_candado LIMIT 1
            """).fetchone()
            if not candado:
                raise OperacionNoPermitida("No quedan candados disponibles.")
            con.execute("""
                UPDATE candados SET estado='prestado'
                WHERE id_candado=? AND estado='disponible'
            """, (candado["id_candado"],))
            if con.execute("SELECT changes()").fetchone()[0] != 1:
                raise OperacionNoPermitida("El candado ya fue asignado. Reintente.")
            con.execute("""
                INSERT INTO prestamos(rut_alumno,id_candado,fecha_prestamo,estado)
                VALUES(?,?,datetime('now','localtime'),'activo')
            """, (alumno["rut"], candado["id_candado"]))
            con.execute("""
                INSERT INTO solicitudes
                (rut,nombre,rol,carrera,accion,id_candado,num_casillero,fecha_hora)
                VALUES(?,?,?,?,'SOLICITUD',?,?,datetime('now','localtime'))
            """, (alumno["rut"], alumno["nombre"], alumno["rol"],
                  alumno["carrera"], candado["id_candado"], candado["num_casillero"]))
            return {**alumno, "id_candado": candado["id_candado"],
                    "num_casillero": candado["num_casillero"]}

    def devolver(self, rut):
        with self.conectar() as con:
            con.execute("BEGIN IMMEDIATE")
            alumno = self._buscar_en_conexion(con, rut)
            if not alumno or normalizar_rut(alumno["rut"]) != normalizar_rut(rut):
                raise OperacionNoPermitida("No se encontró el RUT registrado.")
            activo = self._prestamo_activo(con, alumno["rut"])
            if not activo:
                raise OperacionNoPermitida("No registra ningún candado prestado.")
            con.execute("""
                UPDATE prestamos SET fecha_devolucion=datetime('now','localtime'),
                estado='devuelto' WHERE id=? AND estado='activo'
            """, (activo["id"],))
            con.execute("UPDATE candados SET estado='disponible' WHERE id_candado=?",
                        (activo["id_candado"],))
            con.execute("""
                INSERT INTO solicitudes
                (rut,nombre,rol,carrera,accion,id_candado,num_casillero,fecha_hora)
                VALUES(?,?,?,?,'DEVOLUCIÓN',?,?,datetime('now','localtime'))
            """, (alumno["rut"], alumno["nombre"], alumno["rol"],
                  alumno["carrera"], activo["id_candado"], activo["num_casillero"]))
            return {**alumno, "id_candado": activo["id_candado"],
                    "num_casillero": activo["num_casillero"]}

    def ocupados(self):
        with self.conectar() as con:
            datos = con.execute("""
                SELECT a.rut,a.nombre,a.carrera,COALESCE(a.rol,'ESTUDIANTE') AS rol,
                       p.id_candado,c.num_casillero,p.fecha_prestamo
                FROM prestamos p JOIN alumnos a ON p.rut_alumno=a.rut
                JOIN candados c ON p.id_candado=c.id_candado
                WHERE p.estado='activo' ORDER BY p.fecha_prestamo, p.id
            """).fetchall()
            return [dict(fila) for fila in datos]

    def informe_texto(self):
        stats = self.estadisticas()
        lineas = ["INFORME DE CONTROL DE CANDADOS", "",
                  "Disponibles: {}".format(stats["disponibles"]),
                  "Prestados: {}".format(stats["prestados"]),
                  "Movimientos hoy: {}".format(stats["movimientos_hoy"]), "",
                  "CANDADOS PRESTADOS:"]
        ocupados = self.ocupados()
        if not ocupados:
            lineas.append("Sin préstamos activos.")
        for p in ocupados:
            lineas.append("Casillero {} | Candado {} | {} | {} | {}".format(
                p["num_casillero"], p["id_candado"], p["nombre"],
                p["carrera"], p["fecha_prestamo"]))
        return "\n".join(lineas)
