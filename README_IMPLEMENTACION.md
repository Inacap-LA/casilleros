# Casilleros INACAP — archivos corregidos para APK

## Qué se corrigió

- Se fijó Python **3.12.9 tanto para `python3` como `hostpython3`**, para que Kivy 2.3.0 no sea compilado contra la API incompatible de Python 3.14.
- Se agregó `db` a `source.include_exts`: sin esta extensión, `casilleros.db` no se incluye en el APK.
- Se completaron las funciones ausentes de `main.py`: registro, préstamos, devoluciones, pantalla de ocupados y creación de informe.
- Se separó SQLite en `database.py` y se protegieron los préstamos y devoluciones con transacciones.
- Se reemplazó SMTP con contraseña incrustada por apertura de la aplicación de correo del dispositivo: el usuario debe revisar y confirmar el envío.
- Se añadieron pruebas locales y captura del log cuando GitHub Actions falla.

## Estructura necesaria en el repositorio

```text
casilleros/
├── main.py                     # reemplazar el original
├── database.py                 # archivo NUEVO e indispensable
├── buildozer.spec              # reemplazar el original
├── casilleros.db               # mantener o reemplazar por la copia migrada
├── tests/
│   └── test_database.py        # archivo NUEVO
└── .github/
    └── workflows/
        └── build.yml           # reemplazar el workflow existente
```

La carpeta `tests` corresponde a pruebas sintéticas: no usa datos personales del padrón.

## Instrucciones

1. Realice una **copia de seguridad** de los archivos actuales, especialmente `casilleros.db`.
2. Copie `main.py`, `database.py`, `buildozer.spec` y `tests/test_database.py` a los lugares mostrados.
3. Copie `build.yml` a `.github/workflows/build.yml` (no a la raíz del repositorio).
4. Conserve `casilleros.db` en la raíz o utilice la base migrada incluida en el paquete completo.
5. Configure la constante `DESTINATARIO_INFORME` en `main.py` con una dirección de correo institucional válida. **No agregue contraseñas al código.**
6. Realice commit a la rama `main`. Revise el resultado en **GitHub → Actions → Build Android APK**.
7. Si la compilación termina correctamente, descargue el artifact `Casilleros-Inacap-APK-Debug`.

## Advertencias importantes

- **Protección de datos**: la base entregada contiene identificadores y datos de alumnos. Una base SQLite dentro de un APK se puede extraer; **no es un almacenamiento seguro para distribuir un padrón personal**. Antes de desplegar fuera de un entorno controlado, sustituir este diseño por un servidor autenticado, con mínima información local y controles de acceso. No publique el repositorio ni el APK ni los artifacts que contienen la base de datos.
- **Sin sincronización**: cada instalación del APK utiliza su propia copia SQLite. Dos dispositivos tendrán movimientos diferentes. La copia inicial se realiza solo en la primera ejecución; las actualizaciones del archivo integrado no sobreescriben la DB que ya está en almacenamiento privado (protege el historial).
- **Desinstalar**: en Android, desinstalar o borrar datos puede eliminar el historial almacenado localmente. Implemente respaldos antes de su operación real.
- **Correo**: el botón abre un borrador de correo. No envía mensajes automáticamente y necesita una aplicación de correo instalada. En escritorio el borrador incluye solo un extracto, por limitaciones de `mailto:`.
- **Kivy UI**: las pruebas ejecutadas validan lógica Python y SQLite, no el funcionamiento de pantalla en un equipo Android real. Una compilación exitosa tampoco garantiza que todos los lectores de carnet funcionen sin ajustes.
- **Versión Android**: se mantuvo API 33 y NDK 25b para reducir cambios en la corrección inicial; revisar requisitos de API actuales si se prevé publicar en Google Play y modernizar el NDK tras estabilizar esta compilación.
- **Python-for-Android**: el proyecto sigue usando la rama por defecto elegida por Buildozer. La corrección de Python evita el error concreto observado pero otra dependencia podría requerir ajustes adicionales.

## Pruebas realizadas en este paquete

Ejecutar localmente (sin instalar Kivy):

```bash
python -m compileall -q main.py database.py
python -m unittest discover -s tests -v
```

No se ha ejecutado una compilación Android completa ni se ha instalado el APK en un teléfono; esa validación se debe completar mediante GitHub Actions.
