"""Lectura de QR/PDF417 mediante Google Code Scanner (Android).

No guarda imágenes ni contenido completo del código. Solo entrega a la app
un RUN cuando se puede extraer explícitamente y validar con módulo 11.
"""

import json
import re
from urllib.parse import parse_qs, urlparse

from database import normalizar_rut, validar_rut_chileno

# RUN con guion y/o puntos o RUN compacto. Coincidencia completa: nunca
# deducir identidades desde números arbitrarios de un QR firmado/cifrado.
_RUN = r"(?:\d{1,2}(?:\.\d{3}){2}-?[\dkK]|\d{7,8}-?[\dkK])"
_ETIQUETA = re.compile(r"(?i)(?<!\w)(?:RUT|RUN)\s*[:=]\s*(" + _RUN + r")(?!\w)")
_SOLO_RUN = re.compile(r"^\s*(?:" + _RUN + r")\s*$")


def _run_valido(valor):
    rut = normalizar_rut(valor)
    return rut if validar_rut_chileno(rut) else None


def extraer_run(contenido):
    """Retorna RUN normalizado solo si el dato es inequívoco y módulo 11 válido.

    Apoya formatos explícitos comunes (texto simple, RUT:/RUN:, JSON y URLs
    con parámetro RUT/RUN). El QR oficial puede ser un token opaco: en tal
    caso retorna None y la UI solicita ingreso manual; no inventa un RUN.
    """
    if not isinstance(contenido, str):
        return None
    texto = contenido.strip()
    if not texto or len(texto) > 8192:
        return None

    if _SOLO_RUN.fullmatch(texto):
        return _run_valido(texto)

    # Estructura JSON, exclusivamente campos explícitos en el primer nivel.
    if texto.startswith("{"):
        try:
            obj = json.loads(texto)
            if isinstance(obj, dict):
                for clave, valor in obj.items():
                    if str(clave).lower() in ("run", "rut") and isinstance(valor, str):
                        if _SOLO_RUN.fullmatch(valor):
                            return _run_valido(valor)
        except (ValueError, TypeError):
            pass

    # En URL, buscar solo campos etiquetados, nunca sus identificadores u otros números.
    parsed = urlparse(texto)
    if parsed.scheme in ("https", "http") and parsed.netloc:
        for clave, valores in parse_qs(parsed.query, keep_blank_values=False).items():
            if clave.lower() in ("rut", "run"):
                for valor in valores:
                    if _SOLO_RUN.fullmatch(valor):
                        return _run_valido(valor)
        return None

    coincidencia = _ETIQUETA.search(texto)
    if coincidencia:
        return _run_valido(coincidencia.group(1))
    return None


def iniciar_escaneo_android(al_leer, al_error, al_cancelar):
    """Lanza el escáner nativo mediante Play Services, sin permiso CAMERA.

    Las tres funciones se llaman desde callbacks Java, posiblemente fuera del
    hilo principal. El llamador debe programar cualquier cambio visual con
    kivy.clock.Clock.schedule_once. Retorna referencias para evitar GC.
    """
    from jnius import PythonJavaClass, autoclass, cast, java_method

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    GmsBarcodeScanning = autoclass(
        "com.google.mlkit.vision.codescanner.GmsBarcodeScanning"
    )
    actividad = PythonActivity.mActivity

    class EscaneoCorrecto(PythonJavaClass):
        __javainterfaces__ = ["com/google/android/gms/tasks/OnSuccessListener"]
        __javacontext__ = "app"

        @java_method("(Ljava/lang/Object;)V")
        def onSuccess(self, resultado):
            try:
                barcode = cast("com.google.mlkit.vision.barcode.common.Barcode", resultado)
                contenido = barcode.getRawValue()
                al_leer(str(contenido) if contenido is not None else "")
            except Exception:
                al_error("No fue posible interpretar el código escaneado.")

    class EscaneoFallido(PythonJavaClass):
        __javainterfaces__ = ["com/google/android/gms/tasks/OnFailureListener"]
        __javacontext__ = "app"

        @java_method("(Ljava/lang/Exception;)V")
        def onFailure(self, _error):
            al_error("No se pudo abrir o utilizar el escáner. Compruebe Google Play Services y la conexión a Internet durante el primer uso.")

    class EscaneoCancelado(PythonJavaClass):
        __javainterfaces__ = ["com/google/android/gms/tasks/OnCanceledListener"]
        __javacontext__ = "app"

        @java_method("()V")
        def onCanceled(self):
            al_cancelar()

    escaner = GmsBarcodeScanning.getClient(actividad)
    correcto = EscaneoCorrecto()
    fallido = EscaneoFallido()
    cancelado = EscaneoCancelado()
    tarea = escaner.startScan()
    tarea.addOnSuccessListener(correcto)
    tarea.addOnFailureListener(fallido)
    tarea.addOnCanceledListener(cancelado)
    return escaner, tarea, correcto, fallido, cancelado
