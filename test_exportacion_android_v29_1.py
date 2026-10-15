"""Prueba simulada de MediaStore en Android. Sin acceso a carnets ni datos reales."""
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from registro_diario import guardar_en_descargas


class ContentValues:
    def __init__(self):
        self.valores = {}
    def put(self, clave, valor):
        self.valores[clave] = valor


class MediaColumns:
    DISPLAY_NAME = "_display_name"
    MIME_TYPE = "mime_type"
    RELATIVE_PATH = "relative_path"
    IS_PENDING = "is_pending"


class Downloads:
    EXTERNAL_CONTENT_URI = "content://media/external/downloads"


class BuildVersion:
    SDK_INT = 34


class Environment:
    DIRECTORY_DOWNLOADS = "Download"


class Descriptor:
    def __init__(self, archivo):
        self.archivo = archivo
        self.cerrado = False
    def getFd(self):
        return self.archivo.fileno()
    def close(self):
        self.cerrado = True


class Resolver:
    def __init__(self, archivo):
        self.archivo = archivo
        self.insertado = None
        self.actualizado = None
        self.borrado = False
        self.descriptor = Descriptor(archivo)
    def insert(self, coleccion, contenido):
        self.insertado = (coleccion, dict(contenido.valores))
        return "content://media/external/downloads/321"
    def openFileDescriptor(self, uri, modo):
        assert modo == "w"
        return self.descriptor
    def update(self, uri, contenido, cond, argumentos):
        self.actualizado = dict(contenido.valores)
        return 1
    def delete(self, uri, cond, argumentos):
        self.borrado = True
        return 1


class Actividad:
    def __init__(self, resolver):
        self.resolver = resolver
    def getContentResolver(self):
        return self.resolver


class PruebasAndroid(unittest.TestCase):
    def test_guarda_csv_con_clases_anidadas(self):
        with tempfile.TemporaryFile() as archivo:
            resolver = Resolver(archivo)
            actividad = types.SimpleNamespace(mActivity=Actividad(resolver))
            clases = {
                "android.os.Build$VERSION": BuildVersion,
                "org.kivy.android.PythonActivity": actividad,
                "android.content.ContentValues": ContentValues,
                "android.provider.MediaStore$MediaColumns": MediaColumns,
                "android.provider.MediaStore$Downloads": Downloads,
                "java.lang.Integer": int,
                "android.os.Environment": Environment,
            }
            jnius = types.ModuleType("jnius")
            jnius.autoclass = lambda nombre: clases[nombre]
            kivy = types.ModuleType("kivy")
            utils = types.ModuleType("kivy.utils")
            utils.platform = "android"
            with patch.dict(sys.modules, {"jnius": jnius, "kivy": kivy, "kivy.utils": utils}):
                resultado = guardar_en_descargas("reporte.csv", b"dato,ficticio\n")
            self.assertEqual(resultado, "Descargas/CasillerosINACAP/reporte.csv")
            archivo.seek(0)
            self.assertEqual(archivo.read(), b"dato,ficticio\n")
            self.assertEqual(resolver.insertado[0], Downloads.EXTERNAL_CONTENT_URI)
            self.assertEqual(resolver.insertado[1][MediaColumns.MIME_TYPE], "text/csv")
            self.assertEqual(resolver.insertado[1][MediaColumns.IS_PENDING], 1)
            self.assertEqual(resolver.insertado[1][MediaColumns.RELATIVE_PATH], "Download/CasillerosINACAP/")
            self.assertEqual(resolver.actualizado[MediaColumns.IS_PENDING], 0)
            self.assertTrue(resolver.descriptor.cerrado)
            self.assertFalse(resolver.borrado)


if __name__ == "__main__":
    unittest.main()
