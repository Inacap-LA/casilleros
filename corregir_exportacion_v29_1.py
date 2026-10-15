"""Parche puntual de la exportación CSV para Android 14 / PyJNIus.

Uso: python3 corregir_exportacion_v29_1.py
Modifica únicamente registro_diario.py y la versión de buildozer.spec.
No modifica casilleros.db, main.py, la cámara ni la firma digital.
"""
from pathlib import Path
import sys


def sustituir(codigo, antes, despues, repeticiones):
    encontradas = codigo.count(antes)
    if encontradas != repeticiones:
        raise RuntimeError("Se esperaban {} apariciones de {!r} y hay {}. No se modifica el proyecto."
                           .format(repeticiones, antes, encontradas))
    return codigo.replace(antes, despues)


def main():
    raiz = Path.cwd()
    modulo = raiz / "registro_diario.py"
    spec = raiz / "buildozer.spec"
    if not modulo.is_file() or not spec.is_file():
        raise RuntimeError("Ejecuta este script dentro de ~/Proyectos/casilleros")
    codigo = modulo.read_text(encoding="utf-8")
    configuracion = spec.read_text(encoding="utf-8")
    if 'autoclass("android.provider.MediaStore$MediaColumns")' in codigo:
        print("La corrección de exportación ya está aplicada. Sin cambios.")
        return
    codigo = sustituir(
        codigo,
        '    MediaStore = autoclass("android.provider.MediaStore")\n',
        '    MediaColumns = autoclass("android.provider.MediaStore$MediaColumns")\n'
        '    Downloads = autoclass("android.provider.MediaStore$Downloads")\n'
        '    Integer = autoclass("java.lang.Integer")\n',
        1,
    )
    codigo = sustituir(codigo, "MediaStore.MediaColumns.", "MediaColumns.", 5)
    codigo = sustituir(codigo, "MediaStore.Downloads.EXTERNAL_CONTENT_URI", "Downloads.EXTERNAL_CONTENT_URI", 1)
    codigo = sustituir(codigo, "valores.put(MediaColumns.IS_PENDING, 1)",
                       "valores.put(MediaColumns.IS_PENDING, Integer(1))", 1)
    codigo = sustituir(codigo, "confirmacion.put(MediaColumns.IS_PENDING, 0)",
                       "confirmacion.put(MediaColumns.IS_PENDING, Integer(0))", 1)
    configuracion = sustituir(configuracion, "version = 1.0.4", "version = 1.0.5", 1)
    compile(codigo, str(modulo), "exec")
    modulo.write_text(codigo, encoding="utf-8")
    spec.write_text(configuracion, encoding="utf-8")
    print("OK: se corrigió el acceso a MediaStore.MediaColumns y Downloads.")
    print("OK: versión 1.0.5 (V29.1); se mantienen el lector QR y la firma estable.")
    print("OK: no se modificó casilleros.db.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, SyntaxError) as error:
        sys.exit("ERROR: " + str(error))
