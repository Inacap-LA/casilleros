"""Pruebas con datos ficticios: exportación diaria de Casilleros."""
import csv
from datetime import date
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from registro_diario import crear_csv_diario, _celda_segura


class PruebasRegistroDiario(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "datos de prueba.db"
        with sqlite3.connect(self.ruta) as conn:
            conn.execute("""CREATE TABLE solicitudes (
                id INTEGER PRIMARY KEY, rut TEXT, nombre TEXT, rol TEXT,
                carrera TEXT, accion TEXT, id_candado TEXT,
                num_casillero TEXT, fecha_hora TEXT)""")
            conn.executemany("""INSERT INTO solicitudes
                (id, rut, nombre, rol, carrera, accion, id_candado,
                 num_casillero, fecha_hora) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", [
                (1, "11111111-1", "Persona Ficticia", "ESTUDIANTE", "Carrera A",
                 "SOLICITUD", "C001", "A01", "2026-10-15 09:12:33"),
                (2, "11111111-1", "Persona Ficticia", "ESTUDIANTE", "Carrera A",
                 "DEVOLUCIÓN", "C001", "A01", "2026-10-15 19:00:10"),
                (3, "22222222-2", "Persona de otro día", "PERSONAL", "Unidad B",
                 "SOLICITUD", "C002", "A02", "2026-10-14 15:00:00"),
            ])

    def tearDown(self):
        self.tmp.cleanup()

    def filas(self, contenido):
        self.assertTrue(contenido.startswith(b"\xef\xbb\xbf"))
        return list(csv.reader(io.StringIO(contenido.decode("utf-8-sig")), delimiter=";"))

    def test_exportar_dia_con_entregas_y_devoluciones(self):
        contenido, resumen = crear_csv_diario(self.ruta, date(2026, 10, 15))
        filas = self.filas(contenido)
        self.assertEqual(len(filas), 3)
        self.assertEqual(filas[1][3], "SOLICITUD")
        self.assertEqual(filas[2][3], "DEVOLUCIÓN")
        self.assertEqual(filas[1][1:3], ["2026-10-15", "09:12:33"])
        self.assertEqual(resumen, {"total": 2, "entregas": 1, "devoluciones": 1})

    def test_dia_vacio_genera_encabezados(self):
        contenido, resumen = crear_csv_diario(self.ruta, "2026-10-16")
        self.assertEqual(len(self.filas(contenido)), 1)
        self.assertEqual(resumen["total"], 0)

    def test_exportacion_no_modifica_base(self):
        crear_csv_diario(self.ruta, "2026-10-15")
        with sqlite3.connect(self.ruta) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM solicitudes").fetchone()[0], 3)

    def test_excel_formula_no_se_ejecuta(self):
        self.assertEqual(_celda_segura("=1+2"), "'=1+2")
        self.assertEqual(_celda_segura("@SUM(1)"), "'@SUM(1)")
        self.assertEqual(_celda_segura("Persona"), "Persona")

    def test_csv_caracteres_acentuados(self):
        contenido, _ = crear_csv_diario(self.ruta, "2026-10-15")
        self.assertIn("DEVOLUCIÓN", contenido.decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
