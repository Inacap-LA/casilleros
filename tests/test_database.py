import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import GestorCasilleros, OperacionNoPermitida, validar_rut_chileno


class PruebasCasilleros(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = GestorCasilleros(os.path.join(self.tmp.name, 'pruebas.db'))
        self.db.inicializar()
        with self.db.conectar() as con:
            con.execute("INSERT INTO alumnos (rut,nombre,carrera) VALUES ('12345678-5','Persona Prueba','Construcción')")
            con.execute("INSERT INTO candados (id_candado,num_casillero) VALUES ('C01','001')")

    def test_solicitud_y_devolucion(self):
        p = self.db.solicitar('12.345.678-5')
        self.assertEqual(p['id_candado'], 'C01')
        self.assertEqual(self.db.estadisticas()['prestados'], 1)
        self.db.devolver('12345678-5')
        self.assertEqual(self.db.estadisticas()['disponibles'], 1)
        with self.db.conectar() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM solicitudes').fetchone()[0], 2)
            self.assertEqual(c.execute("SELECT estado FROM prestamos").fetchone()[0], 'devuelto')

    def test_no_permite_doble_prestamo(self):
        self.db.solicitar('12345678-5')
        with self.assertRaises(OperacionNoPermitida):
            self.db.solicitar('12345678-5')
        self.assertEqual(len(self.db.ocupados()), 1)

    def test_no_permite_devolucion_sin_prestamo(self):
        with self.assertRaises(OperacionNoPermitida):
            self.db.devolver('12345678-5')

    def test_registro_personal_nuevo(self):
        self.assertTrue(validar_rut_chileno('12.345.678-5'))
        with self.assertRaises(OperacionNoPermitida):
            self.db.registrar_persona('12345678-9', 'Persona', 'Administración')
        with self.assertRaises(OperacionNoPermitida):
            self.db.registrar_persona('12.345.678-5', 'Persona', 'Administración')
        nuevo = self.db.registrar_persona('11.111.111-1', 'Personal Prueba', 'Administración')
        persona = self.db.buscar_persona(nuevo)
        self.assertEqual(persona['rol'], 'PERSONAL')
        self.assertEqual(persona['nombre'], 'Personal Prueba')

    def test_informe(self):
        self.db.solicitar('12345678-5')
        txt = self.db.informe_texto()
        self.assertIn('Prestados: 1', txt)
        self.assertIn('Casillero 001', txt)


if __name__ == '__main__':
    unittest.main()
