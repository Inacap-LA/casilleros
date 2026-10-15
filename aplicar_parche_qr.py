"""Añade escaneo QR a Casilleros, preservando la versión funcional V27.1.

Uso: python3 aplicar_parche_qr.py desde la raíz del repositorio.
Nunca modifica la base de datos, workflow ni corregir_apk_python.py.
"""
from pathlib import Path
import sys


VALIDAR = {
    "main.py": [
        "from database import (",
        "id: txt_rut",
        "on_text_validate: app.procesar_escaneo(self.text)",
        "    def procesar_escaneo(self, texto):",
        "        self.dialog_ocupados = None\n\n    def build(self):",
    ],
    "buildozer.spec": [
        "requirements = python3==3.12.9",
        "android.api = 33",
        "android.minapi = 26",
        "version = 1.0.2",
    ],
}


BLOQUE_UI = """
                    MDRaisedButton:
                        text: 'ESCANEAR CARNET (QR)'
                        size_hint_y: None
                        height: '44dp'
                        on_release: app.abrir_camara_carnet()
"""


METODOS = '''    def abrir_camara_carnet(self):
        """Abre el escáner nativo (QR y PDF417) sin sustituir el lector USB."""
        if platform != "android":
            self.mostrar_resultado(
                "ESCÁNER SOLO EN ANDROID",
                "Puede ingresar el RUN manualmente en este dispositivo.",
                [0.9, 0.29, 0.23, 1],
            )
            return
        if self._lector_qr_activo:
            return
        self._lector_qr_activo = True
        self.root.ids.txt_rut.focus = False
        try:
            self._referencias_lector_qr = iniciar_escaneo_android(
                al_leer=lambda dato: Clock.schedule_once(
                    lambda _dt: self._codigo_carnet_leido(dato), 0
                ),
                al_error=lambda aviso: Clock.schedule_once(
                    lambda _dt: self._error_lector_qr(aviso), 0
                ),
                al_cancelar=lambda: Clock.schedule_once(
                    lambda _dt: self._cancelar_lector_qr(), 0
                ),
            )
        except Exception:
            self._error_lector_qr(
                "No fue posible iniciar el lector. Verifique que Google Play Services esté actualizado."
            )

    def _cerrar_lector_qr(self):
        self._lector_qr_activo = False
        self._referencias_lector_qr = None

    def _codigo_carnet_leido(self, contenido):
        self._cerrar_lector_qr()
        rut = extraer_run(contenido)
        if rut is None:
            self.mostrar_resultado(
                "CÓDIGO LEÍDO SIN RUN UTILIZABLE",
                "Se pudo leer el código, pero no contiene un RUN accesible en "
                "un formato reconocido. Ingrese el RUN manualmente. No se "
                "guardó el contenido del QR.",
                [0.9, 0.29, 0.23, 1],
            )
            self._enfocar_rut()
            return
        # Solo se entrega el RUN validado al flujo actual de préstamo/devolución.
        self.procesar_escaneo(rut)

    def _error_lector_qr(self, aviso):
        self._cerrar_lector_qr()
        self.mostrar_resultado(
            "ESCÁNER NO DISPONIBLE", aviso, [0.9, 0.29, 0.23, 1]
        )
        self._enfocar_rut()

    def _cancelar_lector_qr(self):
        self._cerrar_lector_qr()
        self._enfocar_rut()

'''


def reemplazar_una_vez(texto, viejo, nuevo, archivo):
    n = texto.count(viejo)
    if n != 1:
        raise ValueError(f"{archivo}: se esperaba una única coincidencia para {viejo!r}, hay {n}")
    return texto.replace(viejo, nuevo, 1)


def main():
    raiz = Path.cwd()
    fuentes = {}
    for archivo, anclas in VALIDAR.items():
        ruta = raiz / archivo
        if not ruta.is_file():
            sys.exit(f"ERROR: no existe {archivo}. Ejecutar desde ~/Proyectos/casilleros")
        texto = ruta.read_text(encoding="utf-8")
        if "def abrir_camara_carnet(self):" in texto or "android.gradle_dependencies = com.google.android.gms:play-services-code-scanner" in texto:
            sys.exit("El lector QR parece estar instalado; se detiene para no duplicar cambios.")
        for ancla in anclas:
            if ancla not in texto:
                sys.exit(f"ERROR: {archivo} cambió desde V27.1: no se halló {ancla!r}. No se modificó nada.")
        fuentes[archivo] = texto

    script = fuentes["main.py"]
    script = reemplazar_una_vez(
        script, "from datetime import datetime\n", "from datetime import datetime\nfrom lector_carnet import extraer_run, iniciar_escaneo_android\n", "main.py"
    )
    script = reemplazar_una_vez(
        script, "                    height: '122dp'\n", "                    height: '184dp'\n", "main.py"
    )
    script = reemplazar_una_vez(
        script,
        "                        on_text_validate: app.procesar_escaneo(self.text)\n",
        "                        on_text_validate: app.procesar_escaneo(self.text)\n" + BLOQUE_UI,
        "main.py",
    )
    script = reemplazar_una_vez(
        script,
        "        self.dialog_ocupados = None\n\n    def build(self):",
        "        self.dialog_ocupados = None\n" + "        self._lector_qr_activo = False\n        self._referencias_lector_qr = None\n\n    def build(self):",
        "main.py",
    )
    script = reemplazar_una_vez(
        script, "    def procesar_escaneo(self, texto):\n",
        METODOS + "    def procesar_escaneo(self, texto):\n",
        "main.py",
    )

    spec = fuentes["buildozer.spec"]
    spec = reemplazar_una_vez(spec, "version = 1.0.2", "version = 1.0.3", "buildozer.spec")
    spec = reemplazar_una_vez(
        spec,
        "android.archs = arm64-v8a\n",
        "android.archs = arm64-v8a\n\n"
        "# Escáner de QR/PDF417 de Google Play Services. Cámara gestionada por Google.\n"
        "# No es necesario solicitar android.permission.CAMERA a Casilleros.\n"
        "android.gradle_dependencies = com.google.android.gms:play-services-code-scanner:16.1.0\n"
        "android.enable_androidx = True\n",
        "buildozer.spec",
    )

    # Comprobar sintaxis antes de escribir (nunca deja el repositorio a medias).
    compile(script, str(raiz / "main.py"), "exec")
    (raiz / "main.py").write_text(script, encoding="utf-8")
    (raiz / "buildozer.spec").write_text(spec, encoding="utf-8")
    print("OK: Se agregó botón ESCANEAR CARNET (QR) y SDK Google Code Scanner.")
    print("OK: buildozer.spec actualizado a 1.0.3. No se modificó la base de datos.")
    print("Ejecute: python3 -m unittest -v test_lector_carnet")
    print("Revise: git diff --check && git diff --stat")


if __name__ == "__main__":
    main()
