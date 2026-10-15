[app]
# Control de Casilleros - INACAP Los Ángeles.
title = Casilleros Inacap
package.name = casilleros
package.domain = cl.inacap
source.dir = .

# CRÍTICO: incluir DB para que el APK encuentre el padrón de alumnos y candados.
# Advertencia: el APK NO cifra la DB. No distribuir un padrón de RUT personales
# sin controles institucionales adecuados de privacidad/acceso.
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,db
source.exclude_dirs = tests,bin,venv,.venv,__pycache__
source.exclude_patterns = test_*.py,corregir_apk_python.py
version = 1.0.3

# Python-for-Android compila su PROPIO Python. No basta con setup-python del CI.
# Kivy 2.3.0 soporta Python hasta 3.12: impedir que p4a elija 3.14.
requirements = python3==3.12.9,hostpython3==3.12.9,kivy==2.3.0,kivymd==1.1.1,pyjnius,pillow

orientation = portrait
fullscreen = 0
log_level = 2

# Se genera APK debug de instalación directa. Mantener API 33 reduce cambios
# respecto al proyecto original; actualizar a API 35+ para publicar en Play.
android.api = 33
# API 26 (Android 8.0) habilita getgrent/setgrent/endgrent requeridas por CPython 3.12.9.
android.minapi = 26
android.ndk = 25b
android.accept_sdk_license = True
android.skip_update = False
android.archs = arm64-v8a

# Escáner de QR/PDF417 de Google Play Services. Cámara gestionada por Google.
# No es necesario solicitar android.permission.CAMERA a Casilleros.
android.gradle_dependencies = com.google.android.gms:play-services-code-scanner:16.1.0
android.enable_androidx = True

# Ya no se requieren permisos de red: los informes se comparten mediante
# las aplicaciones instaladas, sin alojar contraseñas SMTP en el APK.
# android.permissions =

[buildozer]
log_level = 2
warn_on_root = 1
