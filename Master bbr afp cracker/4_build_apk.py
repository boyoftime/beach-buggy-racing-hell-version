"""
Build a signed, installable APK from `output/Assets.apf` + `output/Expansion.apf`.

Usage
-----
  python 4_build_apk.py path/to/source.apk
  python 4_build_apk.py path/to/source.apk --install
  python 4_build_apk.py path/to/source.apk --no-sign        (just produce unsigned)
  python 4_build_apk.py path/to/source.apk --keystore ks.p12

What it does
------------
  1. Clones the source APK as a zip — copies every entry verbatim except
     replaces `assets/Assets.apf` and `assets/Expansion.apf` with the freshly-
     packed copies in `output/`.
  2. Strips v1 jar-signature files from META-INF (apksigner regenerates).
  3. zipaligns the new APK on 4-byte boundaries (required for v2 signing).
  4. Signs with v1 + v2 + v3 schemes using a debug keystore (auto-generated
     on first run if missing).
  5. Optionally installs onto the connected ADB device (--install).

Tools needed
------------
  - Android SDK build-tools (apksigner, zipalign) — looked up via
    %LOCALAPPDATA%\\Android\\Sdk\\build-tools\\<latest>\\
    or $ANDROID_HOME / $ANDROID_SDK_ROOT.
  - JDK with `keytool` on PATH (only for first-run keystore generation).
  - adb (only if --install).
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE       = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / 'output'
BUILD_DIR  = HERE / 'build'

REPLACE = {
    'assets/Assets.apf':    OUTPUT_DIR / 'Assets.apf',
    'assets/Expansion.apf': OUTPUT_DIR / 'Expansion.apf',
}


def is_signature_file(name):
    n = name.upper()
    return (n.startswith('META-INF/') and
            (n == 'META-INF/MANIFEST.MF'
             or n.endswith('.SF') or n.endswith('.RSA')
             or n.endswith('.DSA') or n.endswith('.EC')))


def find_build_tools():
    """Locate the latest Android SDK build-tools that has apksigner + zipalign."""
    candidates = []
    for env in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        p = os.environ.get(env)
        if p:
            candidates.append(Path(p) / 'build-tools')
    local = os.environ.get('LOCALAPPDATA')
    if local:
        candidates.append(Path(local) / 'Android' / 'Sdk' / 'build-tools')
    for bt_root in candidates:
        if bt_root.is_dir():
            versions = sorted([d for d in bt_root.iterdir() if d.is_dir()],
                              key=lambda x: x.name)
            for v in reversed(versions):  # newest first
                if (v / 'apksigner.bat').exists() and (v / 'zipalign.exe').exists():
                    return v
    return None


def clone_apk_with_modded_apfs(src_apk, dst_apk):
    """Copy entries from src_apk to dst_apk, swapping in modded APFs and
    stripping v1 signature files."""
    n_in = n_out = n_swap = n_strip = 0
    with zipfile.ZipFile(src_apk, 'r') as zin, \
         zipfile.ZipFile(dst_apk, 'w', allowZip64=True) as zout:
        for info in zin.infolist():
            n_in += 1
            if is_signature_file(info.filename):
                n_strip += 1
                continue
            if info.filename in REPLACE:
                payload_path = REPLACE[info.filename]
                if not payload_path.exists():
                    raise FileNotFoundError(
                        f'Modded {payload_path.name} missing — run 3_pack.py first.'
                    )
                with open(payload_path, 'rb') as f:
                    payload = f.read()
                ni = zipfile.ZipInfo(info.filename, info.date_time)
                ni.compress_type = zipfile.ZIP_STORED
                ni.external_attr = info.external_attr
                zout.writestr(ni, payload)
                n_swap += 1
                n_out += 1
                continue
            with zin.open(info, 'r') as src:
                data = src.read()
            ni = zipfile.ZipInfo(info.filename, info.date_time)
            ni.compress_type = info.compress_type
            ni.external_attr = info.external_attr
            zout.writestr(ni, data)
            n_out += 1
    return n_in, n_out, n_swap, n_strip


def gen_debug_keystore(path):
    """Use the JDK's keytool to create a self-signed debug keystore."""
    print(f'  generating debug keystore at {path}')
    subprocess.run([
        'keytool', '-genkey', '-v', '-keystore', str(path),
        '-storepass', 'android', '-keypass', 'android',
        '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048',
        '-validity', '36500',
        '-dname', 'CN=BBR Mod Debug, O=Modder, C=US',
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source_apk', help='original APK file to base the build on')
    ap.add_argument('--out', default=None,
                    help='output APK path (default: build/modded-signed.apk)')
    ap.add_argument('--keystore', default=None,
                    help='path to .keystore (default: build/debug.keystore, '
                         'auto-generated if missing)')
    ap.add_argument('--storepass', default='android',
                    help='keystore store/key password (default: android)')
    ap.add_argument('--no-sign', action='store_true',
                    help='skip signing (produces unsigned APK only — uninstallable)')
    ap.add_argument('--install', action='store_true',
                    help='adb install -r the signed APK on connected device')
    args = ap.parse_args()

    src_apk = Path(args.source_apk).resolve()
    if not src_apk.exists():
        sys.exit(f'Source APK not found: {src_apk}')

    BUILD_DIR.mkdir(exist_ok=True)
    unsigned   = BUILD_DIR / 'unsigned.apk'
    aligned    = BUILD_DIR / 'aligned.apk'
    signed     = Path(args.out).resolve() if args.out else BUILD_DIR / 'modded-signed.apk'
    keystore   = Path(args.keystore).resolve() if args.keystore else BUILD_DIR / 'debug.keystore'

    print(f'Source APK : {src_apk}')
    print(f'Modded APFs: {OUTPUT_DIR}')
    for tgt, payload in REPLACE.items():
        size = payload.stat().st_size if payload.exists() else 0
        marker = 'OK' if size else 'MISSING'
        print(f'  {tgt:<22} {size:>12,}  {marker}')

    print(f'\n[1/4] Building unsigned APK with modded APFs...')
    n_in, n_out, n_swap, n_strip = clone_apk_with_modded_apfs(src_apk, unsigned)
    print(f'  in: {n_in} entries  out: {n_out}  swapped: {n_swap}  stripped: {n_strip}')
    print(f'  -> {unsigned}  ({unsigned.stat().st_size:,} bytes)')

    if args.no_sign:
        print('\nSkipped sign step (--no-sign). Done.')
        return

    bt = find_build_tools()
    if bt is None:
        sys.exit('Could not find Android SDK build-tools (looked in '
                 'ANDROID_HOME, ANDROID_SDK_ROOT, %LOCALAPPDATA%\\Android\\Sdk).')

    print(f'\n[2/4] zipalign 4-byte boundaries...')
    print(f'  using {bt / "zipalign.exe"}')
    if aligned.exists():
        aligned.unlink()
    subprocess.run([str(bt / 'zipalign.exe'), '-p', '4', str(unsigned), str(aligned)],
                   check=True)

    print(f'\n[3/4] Signing (v1 + v2 + v3)...')
    if not keystore.exists():
        gen_debug_keystore(keystore)
    if signed.exists():
        signed.unlink()
    subprocess.run([
        str(bt / 'apksigner.bat'), 'sign',
        '--ks', str(keystore), '--ks-pass', f'pass:{args.storepass}', '--key-pass', f'pass:{args.storepass}',
        '--v1-signing-enabled', 'true',
        '--v2-signing-enabled', 'true',
        '--v3-signing-enabled', 'true',
        '--out', str(signed),
        str(aligned),
    ], check=True)
    subprocess.run([str(bt / 'apksigner.bat'), 'verify', str(signed)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f'  -> {signed}  ({signed.stat().st_size:,} bytes)')

    if args.install:
        print(f'\n[4/4] adb install -r ...')
        adb = shutil.which('adb')
        if adb is None:
            local = os.environ.get('LOCALAPPDATA')
            cand = Path(local) / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe'
            if cand.exists():
                adb = str(cand)
        if adb is None:
            sys.exit('adb not on PATH and not in default Android Sdk location.')
        subprocess.run([adb, 'install', '-r', str(signed)], check=True)
        print('  install OK')

    print('\nDone.')


if __name__ == '__main__':
    main()
