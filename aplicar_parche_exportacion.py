"""Instala exportación CSV V29 en el repositorio V28 de Casilleros INACAP.

Uso: python3 aplicar_parche_exportacion.py
No toca la base ni el archivo de clave digital.
"""
from pathlib import Path
import sys

BOTON = """
                    MDRaisedButton:
                        text: 'EXPORTAR REGISTRO DEL DÍA'
                        size_hint_y: None
                        height: '44dp'
                        on_release: app.exportar_registro_hoy()
"""

METODO = '''    def exportar_registro_hoy(self):
        """Guarda el CSV del día en Descargas/CasillerosINACAP."""
        fecha = datetime.now().date()
        nombre = "Casilleros_INACAP_{}_{}.csv".format(
            fecha.strftime("%Y-%m-%d"), datetime.now().strftime("%H%M%S")
        )
        try:
            contenido, resumen = crear_csv_diario(self.db.ruta_db, fecha)
            destino = guardar_en_descargas(nombre, contenido)
            mensaje = (
                "Archivo guardado en:\\n{}\\n\\n"
                "Movimientos: {}\\nEntregas: {}\\nDevoluciones: {}".format(
                    destino, resumen["total"], resumen["entregas"], resumen["devoluciones"]
                )
            )
            self.mostrar_resultado(
                "REGISTRO DIARIO EXPORTADO", mensaje, [0.15, 0.68, 0.37, 1]
            )
            self._aviso_exportacion("Registro diario exportado", mensaje)
        except Exception as error:
            texto = "No se pudo guardar el CSV: {}".format(error)
            self.mostrar_resultado(
                "ERROR AL EXPORTAR", texto, [0.9, 0.29, 0.23, 1]
            )
            self._aviso_exportacion("No se pudo exportar", texto)

    def _aviso_exportacion(self, titulo, mensaje):
        dialogo = MDDialog(title=titulo, text=mensaje)
        dialogo.buttons = [MDFlatButton(
            text="ENTENDIDO", on_release=lambda *_: dialogo.dismiss()
        )]
        dialogo.open()

'''


def cambiar_unico(codigo, buscar, reemplazo, nombre):
    n = codigo.count(buscar)
    if n != 1:
        raise RuntimeError(
            "{}: se esperaba una aparición de {!r}, encontramos {}. "
            "No se modificó ningún archivo.".format(nombre, buscar, n)
        )
    return codigo.replace(buscar, reemplazo, 1)


def main():
    raiz = Path.cwd()
    rutas = {nombre: raiz / nombre for nombre in (
        "main.py", "buildozer.spec", ".github/workflows/build.yml",
        "registro_diario.py", "test_registro_diario.py",
    )}
    faltan = [n for n, ruta in rutas.items() if not ruta.is_file()]
    if faltan:
        sys.exit("ERROR: faltan archivos: {}. Ejecutar desde ~/Proyectos/casilleros".format(", ".join(faltan)))
    codigo = rutas["main.py"].read_text(encoding="utf-8")
    spec = rutas["buildozer.spec"].read_text(encoding="utf-8")
    flujo = rutas[".github/workflows/build.yml"].read_text(encoding="utf-8")
    if "def exportar_registro_hoy(self):" in codigo:
        sys.exit("La función de exportación ya está instalada. No se duplicó.")
    if "from lector_carnet import extraer_run, iniciar_escaneo_android" not in codigo:
        sys.exit("ERROR: no se encontró el lector QR V28 en main.py")
    if "version = 1.0.3" not in spec:
        sys.exit("ERROR: versión inesperada en buildozer.spec; se esperaba 1.0.3")
    if "CASILLEROS_DEBUG_KEYSTORE_B64" not in flujo:
        sys.exit("ERROR: no aparece la firma persistente en el flujo GitHub")

    codigo = cambiar_unico(
        codigo, "from lector_carnet import extraer_run, iniciar_escaneo_android\n",
        "from lector_carnet import extraer_run, iniciar_escaneo_android\n"
        "from registro_diario import crear_csv_diario, guardar_en_descargas\n", "main.py"
    )
    codigo = cambiar_unico(
        codigo, "                    height: '184dp'\n",
        "                    height: '244dp'\n", "main.py")
    codigo = cambiar_unico(
        codigo, "                        on_release: app.abrir_camara_carnet()\n",
        "                        on_release: app.abrir_camara_carnet()\n" + BOTON,
        "main.py")
    codigo = cambiar_unico(
        codigo, "    def enviar_informe_manual(self):\n",
        METODO + "    def enviar_informe_manual(self):\n", "main.py")
    spec = cambiar_unico(spec, "version = 1.0.3", "version = 1.0.4", "buildozer.spec")
    flujo = cambiar_unico(flujo,
        "          python -m compileall -q main.py database.py corregir_apk_python.py\n",
        "          python -m compileall -q main.py database.py corregir_apk_python.py registro_diario.py\n"
        "          python -m unittest -v test_registro_diario\n",
        ".github/workflows/build.yml")
    # Renombrar el artefacto para reconocer fácilmente la nueva compilación.
    for anterior, nuevo in (
        ("Corregir biblioteca Python y firmar APK v28", "Corregir biblioteca Python y firmar APK v29"),
        ("bin/casilleros-v28-debug.apk", "bin/casilleros-v29-debug.apk"),
        ("Casilleros-Inacap-APK-v28-Firma-Estable", "Casilleros-Inacap-APK-v29-Firma-Estable"),
    ):
        if anterior not in flujo:
            raise RuntimeError("Workflow sin la marca esperada: {}".format(anterior))
        flujo = flujo.replace(anterior, nuevo)
    compile(codigo, "main.py", "exec")
    compile(rutas["registro_diario.py"].read_text(encoding="utf-8"), "registro_diario.py", "exec")
    # Todo validado: recién ahora se escribe en disco.
    rutas["main.py"].write_text(codigo, encoding="utf-8")
    rutas["buildozer.spec"].write_text(spec, encoding="utf-8")
    rutas[".github/workflows/build.yml"].write_text(flujo, encoding="utf-8")
    print("OK: añadido botón EXPORTAR REGISTRO DEL DÍA debajo del escáner QR.")
    print("OK: CSV a Descargas/CasillerosINACAP sin Internet ni alterar SQLite.")
    print("OK: versión 1.0.4; conserva firma permanente; CI prueba la exportación.")
    print("Siguiente: python3 -m unittest -v test_registro_diario test_lector_carnet")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        sys.exit("ERROR: " + str(e))
