[app]
title = Control Casilleros
package.name = casilleros
package.domain = cl.duoc.casilleros
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db
version = 1.0.0

requirements = python3,kivy==2.3.0,kivymd==1.1.1,requests,urllib3,pillow,openssl

orientation = landscape
fullscreen = 1

android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, CAMERA
android.api = 33
android.minapi = 21
android.accept_sdk_license = True
android.archs = arm64-v8a
android.ndk = 25b

[buildozer]
# Nivel de detalle del registro:
# 0 = Solo errores
# 1 = Información general (Recomendado para GitHub Actions)
# 2 = Depuración completa (genera demasiado texto y recorta el log)
log_level = 2

# (int) Mostrar advertencia si buildozer se ejecuta como root (0 = no, 1 = sí)
warn_on_root = 1
