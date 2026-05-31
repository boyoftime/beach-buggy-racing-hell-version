# Master BBR Toolkit

Clean command-line toolkit for extracting, editing, and repacking Beach Buggy Racing APF files.

## Supported Games

- Beach Buggy Racing 1 PC
- Beach Buggy Racing 1 Android
- Beach Buggy Racing 2 PC / Adventure Island
- Beach Buggy Racing 2 Android

Supported APF files include:

- `Assets.apf`
- `Expansion.apf`
- `HF.apf`
- `HW.apf`
- Other `.apf` files can also be tested

## Folder Layout

```text
Master bbr
  input\       Put original APF files here
  extracted\   Created by 1_extract.py
  output\      Repacked APF files appear here
  tools\       APF, JSON, texture, and audio encoders/decoders
```

## Extract APF Files

1. Copy your APF files into:

```powershell
C:\Users\someless\Desktop\Master bbr\input
```

2. Run:

```powershell
cd "C:\Users\someless\Desktop\Master bbr"
python .\1_extract.py
```

The editable files will appear in:

```powershell
C:\Users\someless\Desktop\Master bbr\extracted
```

## Edit Files

Common editable files:

- `.png` textures
- `.json` decoded game data
- `.wav` audio bank files
- `.mp3` music streams where available

For BBR2 JSON files, edit the `.bin.json` file. The pack script will encode it back into `.bin`.

## Repack APF Files

For texture/json edits only:

```powershell
cd "C:\Users\someless\Desktop\Master bbr"
python .\3_pack.py
```

For Android audio edits, run the audio prepack first:

```powershell
cd "C:\Users\someless\Desktop\Master bbr"
python .\2_prepack_android.py
python .\3_pack.py
```

Repacked APF files will be in:

```powershell
C:\Users\someless\Desktop\Master bbr\output
```

## Build Android Split APK

For BBR2 Android split APKs, rebuild the asset split using the original `split_asset_pack.apk` as the source.

Example:

```powershell
cd "C:\Users\someless\Desktop\Master bbr"
python .\4_build_apk.py "path\to\split_asset_pack.apk" --out "path\to\signed\split_asset_pack.apk" --keystore "path\to\bbr2-debug.keystore"
```

Install split APKs with:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install-multiple --no-incremental -r `
"path\to\signed\base.apk" `
"path\to\signed\split_asset_pack.apk" `
"path\to\signed\split_config.arm64_v8a.apk" `
"path\to\signed\split_config.en.apk" `
"path\to\signed\split_config.xxhdpi.apk"
```

Important: all split APKs must use the same signing keystore.

## Quick PC APF Use

For PC versions, copy the repacked APF files from `output\` back into the game folder after making a backup of the originals.

## Notes

- Always keep backups of original APF/APK files.
- If you edit audio, run `2_prepack_android.py` before `3_pack.py`.
- If the game uses split APKs, install all required splits together.
- If Android install says signatures are inconsistent, rebuild/sign the changed split with the same keystore used by the other splits.
