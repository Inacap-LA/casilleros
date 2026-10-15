"""Pruebas sintéticas: no usa documentos ni RUN de estudiantes."""
import unittest

from lector_carnet import extraer_run


class TestLectorCarnet(unittest.TestCase):
    def test_rut_plano(self):
        self.assertEqual(extraer_run("12.345.678-5"), "123456785")

    def test_rut_etiquetado(self):
        self.assertEqual(extraer_run("Nombre Demo; RUN: 12.345.678-5; sede"), "123456785")

    def test_json(self):
        self.assertEqual(extraer_run('{"run":"12.345.678-5"}'), "123456785")

    def test_url_etiquetada(self):
        self.assertEqual(extraer_run("https://ejemplo.invalid/verificar?run=123456785"), "123456785")

    def test_url_opaca_no_confundir_con_rut(self):
        self.assertIsNone(extraer_run("https://ejemplo.invalid/seguridad/123456785"))

    def test_token_opaco(self):
        self.assertIsNone(extraer_run("eyJhbGciOiJIUzI1NiJ9.OTk4Nw.signature"))

    def test_digito_invalido(self):
        self.assertIsNone(extraer_run("RUN: 12.345.678-9"))

    def test_datos_no_etiquetados(self):
        self.assertIsNone(extraer_run("Identificador 123456785 token"))


if __name__ == "__main__":
    unittest.main()
