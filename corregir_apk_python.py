#!/usr/bin/env python3
"""Diagnóstico v27: reconstruye el Python bundle del APK y vuelve a firmarlo.

* stdlib.zip => entradas ZIP_STORED (Python inicializa en Lenovo TB336FU).
* Extensiones con PyInit_* y referencias Py* => DT_NEEDED libpython3.12.so.
* APK => re-alineado y re-firmado con la misma clave debug del build.

Requiere: patchelf, readelf, zipalign, apksigner, debug.keystore.
Solo debe utilizarse con APK debug propio y respaldo de fuentes/datos.
"""
import argparse
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

LIBPY = "libpython3.12.so"
ARCH = "arm64-v8a"
PYBUNDLE_PATH = f"lib/{ARCH}/libpybundle.so"
PYTHON_PATH = f"lib/{ARCH}/{LIBPY}"


def call(*cmd):
    print("$", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def output(*cmd):
    return subprocess.check_output([str(x) for x in cmd], text=True)


def find_android_tool(name):
    roots = [Path.home()/".buildozer/android/platform/android-sdk/build-tools"]
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env):
            roots.append(Path(os.environ[env])/"build-tools")
    candidates = [p for root in roots if root.is_dir() for p in root.glob(f"*/{name}")]
    if candidates:
        return sorted(candidates, key=lambda p: tuple(int(x) for x in re.findall(r'\d+', p.parent.name)), reverse=True)[0]
    found = shutil.which(name)
    if found:
        return Path(found)
    raise RuntimeError(f"No se encuentra {name}; comprueba Android SDK build-tools")


def has_export(symbol_table, name):
    return any(re.search(rf"\b{re.escape(name)}\b", line) and " UND " not in line
               for line in symbol_table.splitlines())


def relink_extension(content, filename, tmpdir):
    """Solo añadir DT_NEEDED a módulos CPython que realmente utilicen su C-API."""
    path = tmpdir / "extension.so"
    path.write_bytes(content)
    try:
        symbols = output("readelf", "--dyn-syms", "--wide", path)
    except subprocess.CalledProcessError:
        return content, False
    has_init = any("PyInit_" in line and " UND " not in line for line in symbols.splitlines())
    refs_python = any(re.search(r"\bUND\s+(_?Py[A-Za-z_0-9]+)(?:@|\s|$)", line)
                      for line in symbols.splitlines())
    if not (has_init and refs_python):
        return content, False
    current = output("patchelf", "--print-needed", path).splitlines()
    if LIBPY not in current:
        call("patchelf", "--add-needed", LIBPY, path)
    updated = output("patchelf", "--print-needed", path).splitlines()
    if LIBPY not in updated:
        raise RuntimeError(f"No se pudo enlazar {filename}")
    return path.read_bytes(), True


def uncompress_stdlib(content):
    src = io.BytesIO(content)
    dst = io.BytesIO()
    with zipfile.ZipFile(src) as original, zipfile.ZipFile(dst, "w") as updated:
        if original.testzip():
            raise RuntimeError("stdlib.zip con CRC incorrecto")
        names = set(original.namelist())
        if not {'encodings/__init__.pyc', 'codecs.pyc'}.issubset(names):
            raise RuntimeError("stdlib.zip no contiene encodings y codecs; detener")
        for info in original.infolist():
            updated.writestr(info, original.read(info.filename), compress_type=zipfile.ZIP_STORED)
        count = len(original.infolist())
    with zipfile.ZipFile(io.BytesIO(dst.getvalue())) as z:
        assert z.testzip() is None
        assert all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())
    print(f"  stdlib.zip: {count} archivos sin compresión", flush=True)
    return dst.getvalue()


def patch_python_bundle(binary, tmpdir):
    gzipped = binary[:2] == b'\x1f\x8b'
    archive_mode = 'w:gz' if gzipped else 'w'
    stdlib_count, patched_names = 0, []
    result = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(binary), mode="r:*") as src:
        with tarfile.open(fileobj=result, mode=archive_mode) as dst:
            for member in src.getmembers():
                name = member.name[2:] if member.name.startswith('./') else member.name
                # Evitar rutas de traversal y miembros desconocidos con ruta absoluta
                normalized = Path(name)
                if member.name.startswith('/') or '..' in normalized.parts:
                    raise RuntimeError(f"Ruta insegura en el bundle: {member.name}")
                if not member.isfile():
                    dst.addfile(member)
                    continue
                input_file = src.extractfile(member)
                if input_file is None:
                    raise RuntimeError(f"No se pudo leer {member.name}")
                blob = input_file.read()
                if name == '_python_bundle/stdlib.zip':
                    blob = uncompress_stdlib(blob)
                    stdlib_count += 1
                elif name.startswith('_python_bundle/') and name.endswith('.so'):
                    blob, changed = relink_extension(blob, name, tmpdir)
                    if changed:
                        patched_names.append(name)
                member.size = len(blob)
                dst.addfile(member, io.BytesIO(blob))
    if stdlib_count != 1:
        raise RuntimeError(f"No se encontró stdlib.zip una sola vez: {stdlib_count}")
    for required in ('_datetime', 'math'):
        if not any(Path(x).name.startswith(required + '.') for x in patched_names):
            raise RuntimeError(f"No se corrigió {required}.so; detener, no publicar APK")
    print(f"  Extensiones enlazadas con {LIBPY}: {len(patched_names)}", flush=True)
    for name in patched_names:
        print('    -', name, flush=True)
    return result.getvalue()


def drop_old_signature(name):
    upper = name.upper()
    return upper.startswith('META-INF/') and (upper.endswith(('.SF', '.RSA', '.DSA', '.EC')) or upper == 'META-INF/MANIFEST.MF')


def patch_apk(original, output_file):
    with tempfile.TemporaryDirectory(prefix="casilleros_v27_") as t:
        temp = Path(t)
        unsigned = temp / "unsigned.apk"
        aligned = temp / "aligned.apk"
        with zipfile.ZipFile(original) as apk:
            names = set(apk.namelist())
            for required in (PYBUNDLE_PATH, PYTHON_PATH):
                if required not in names:
                    raise RuntimeError(f"No se encontró {required}; NO es el formato esperado del APK")
            libpython = temp / LIBPY
            libpython.write_bytes(apk.read(PYTHON_PATH))
            sym = output("readelf", "--dyn-syms", "--wide", libpython)
            for exported in ('PyTuple_Type', 'PyExc_ValueError'):
                if not has_export(sym, exported):
                    raise RuntimeError(f"{LIBPY} no exporta {exported}; parche de enlace no aplicable")
            print('  libpython3.12.so exporta los dos símbolos verificados', flush=True)
            replacement = patch_python_bundle(apk.read(PYBUNDLE_PATH), temp)
            with zipfile.ZipFile(unsigned, 'w', allowZip64=True) as out:
                out.comment = apk.comment
                for info in apk.infolist():
                    if drop_old_signature(info.filename):
                        continue
                    blob = replacement if info.filename == PYBUNDLE_PATH else apk.read(info.filename)
                    out.writestr(info, blob, compress_type=info.compress_type)
        zipalign = find_android_tool('zipalign')
        apksigner = find_android_tool('apksigner')
        # SDK antiguos no conocen -P; alternativa compatible con API 26.
        try:
            call(zipalign, '-P', '16', '-f', '4', unsigned, aligned)
        except subprocess.CalledProcessError:
            print('zipalign sin -P 16; usando alineación tradicional', flush=True)
            call(zipalign, '-f', '4', unsigned, aligned)
        keystore = Path.home()/'.android/debug.keystore'
        if not keystore.is_file():
            raise RuntimeError('No se encuentra ~/.android/debug.keystore de esta compilación')
        output_file.parent.mkdir(parents=True, exist_ok=True)
        call(apksigner, 'sign', '--ks', keystore, '--ks-key-alias', 'androiddebugkey',
             '--ks-pass', 'pass:android', '--key-pass', 'pass:android',
             '--out', output_file, aligned)
        call(apksigner, 'verify', '--verbose', output_file)
        with zipfile.ZipFile(output_file) as check:
            if check.testzip():
                raise RuntimeError('APK reparado con CRC inválido')
        print(f'APK experimental v27 generado: {output_file} ({output_file.stat().st_size} bytes)', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path, default=Path('bin/casilleros-v27-debug.apk'))
    opts = parser.parse_args()
    source = opts.input
    if source is None:
        candidates = [x for x in Path('bin').glob('*.apk') if x != opts.output]
        if len(candidates) != 1:
            raise RuntimeError(f'Esperaba 1 APK original en bin/, encontré {len(candidates)}')
        source = candidates[0]
    if source.resolve() == opts.output.resolve():
        raise RuntimeError('El archivo de origen y salida no pueden ser iguales')
    print(f'Procesando APK debug original: {source}', flush=True)
    patch_apk(source, opts.output)

if __name__ == '__main__':
    main()
