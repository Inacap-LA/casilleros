"""Exportación local del historial de candados a CSV.

No modifica SQLite. Android 10+ usa MediaStore Downloads sin permisos amplios.
"""
import csv
from datetime import date
import io
import os
from pathlib import Path
import sqlite3

ENCABEZADOS = (
    "ID movimiento", "Fecha", "Hora", "Operación", "RUT", "Nombre",
    "Tipo de usuario", "Carrera o departamento", "ID candado", "Casillero",
)


def _celda_segura(valor):
    """Evita que Excel interprete como fórmula un campo de texto."""
    contenido = "" if valor is None else str(valor)
    if contenido.lstrip().startswith(("=", "+", "-", "@")) or contenido.startswith(("\t", "\r", "\n")):
        return "'" + contenido
    return contenido


def crear_csv_diario(ruta_db, fecha=None):
    """Devuelve (bytes CSV UTF-8 BOM, resumen) para una fecha local.

    La aplicación escribe solicitudes.fecha_hora con datetime('now','localtime').
    """
    fecha = fecha or date.today()
    fecha_str = fecha.isoformat() if isinstance(fecha, date) else str(fecha)
    ruta = Path(ruta_db).resolve()
    if not ruta.is_file():
        raise FileNotFoundError("No se encontró la base de datos local")
    with sqlite3.connect(ruta.as_uri() + "?mode=ro", uri=True) as conexion:
        movimientos = conexion.execute("""
            SELECT id, fecha_hora, accion, rut, nombre, rol, carrera,
                   id_candado, num_casillero
            FROM solicitudes
            WHERE DATE(fecha_hora) = ?
            ORDER BY fecha_hora ASC, id ASC
        """, (fecha_str,)).fetchall()
    buffer = io.StringIO(newline="")
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    escritor.writerow(ENCABEZADOS)
    resumen = {"total": 0, "entregas": 0, "devoluciones": 0}
    for fila in movimientos:
        mid, fechahora, accion, rut, nombre, rol, carrera, candado, casillero = fila
        estampilla = str(fechahora or "")
        dia, _, hora = estampilla.partition(" ")
        escritor.writerow([
            _celda_segura(mid), _celda_segura(dia), _celda_segura(hora),
            _celda_segura(accion), _celda_segura(rut), _celda_segura(nombre),
            _celda_segura(rol), _celda_segura(carrera),
            _celda_segura(candado), _celda_segura(casillero),
        ])
        resumen["total"] += 1
        if str(accion or "").upper() == "SOLICITUD":
            resumen["entregas"] += 1
        elif str(accion or "").upper() in ("DEVOLUCIÓN", "DEVOLUCION"):
            resumen["devoluciones"] += 1
    return buffer.getvalue().encode("utf-8-sig"), resumen


def guardar_en_descargas(nombre, contenido):
    """Guarda en Descargas/CasillerosINACAP, sin permisos extra en Android 10+."""
    nombre = Path(nombre).name
    if not nombre.lower().endswith(".csv"):
        raise ValueError("El archivo debe tener extensión .csv")
    try:
        from kivy.utils import platform
    except ImportError:
        platform = "linux"
    if platform != "android":
        destino = Path.home() / "Downloads" / "CasillerosINACAP"
        destino.mkdir(parents=True, exist_ok=True)
        ruta = destino / nombre
        ruta.write_bytes(contenido)
        return str(ruta)

    from jnius import autoclass
    BuildVersion = autoclass("android.os.Build$VERSION")
    if int(BuildVersion.SDK_INT) < 29:
        raise RuntimeError("Exportación a Descargas disponible desde Android 10.")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ContentValues = autoclass("android.content.ContentValues")
    MediaStore = autoclass("android.provider.MediaStore")
    Environment = autoclass("android.os.Environment")
    resolver = PythonActivity.mActivity.getContentResolver()
    valores = ContentValues()
    valores.put(MediaStore.MediaColumns.DISPLAY_NAME, nombre)
    valores.put(MediaStore.MediaColumns.MIME_TYPE, "text/csv")
    valores.put(MediaStore.MediaColumns.RELATIVE_PATH,
                Environment.DIRECTORY_DOWNLOADS + "/CasillerosINACAP/")
    valores.put(MediaStore.MediaColumns.IS_PENDING, 1)
    uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, valores)
    if uri is None:
        raise OSError("Android no permitió crear el CSV en Descargas")
    descriptor = None
    try:
        descriptor = resolver.openFileDescriptor(uri, "w")
        if descriptor is None:
            raise OSError("No se pudo escribir el CSV")
        fd = os.dup(descriptor.getFd())
        with os.fdopen(fd, "wb") as archivo:
            archivo.write(contenido)
        descriptor.close()
        descriptor = None
        confirmacion = ContentValues()
        confirmacion.put(MediaStore.MediaColumns.IS_PENDING, 0)
        resolver.update(uri, confirmacion, None, None)
    except Exception:
        if descriptor is not None:
            descriptor.close()
        resolver.delete(uri, None, None)
        raise
    return "Descargas/CasillerosINACAP/" + nombre
