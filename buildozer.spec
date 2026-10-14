[app]

# (str) Title of your application
title = Casilleros Inacap

# (str) Package name
package.name = casilleros

# (str) Package domain (needed for android/ios packaging)
package.domain = cl.inacap

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# NOTA: Cython está fijado en el workflow. Aquí se definen los paquetes de Python.
requirements = python3,kivy==2.3.0,kivymd==1.1.1,requests,urllib3,pillow,openssl

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (int) Log level (0 = error only, 1 = info, 2 = debug (full output))
log_level = 2

#
# Android specific
#

# (list) Permissions
android.permissions = INTERNET, ACCESS_NETWORK_STATE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API required
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (bool) If True, then skip try to update the android sdk
android.skip_update = False

# (bool) If True, then accept all the licenses from android sdk tools
android.accept_sdk_license = True

# (list) The Android architectures to build for
android.archs = arm64-v8a, armeabi-v7a

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = disable, 1 = enable)
warn_on_root = 1
