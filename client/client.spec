# PyInstaller spec for BP Timer standalone client (optional helper).
# Usage (Windows):
#   pyinstaller client/client.spec
# Ensure WinDivert DLL/SYS files are copied alongside the built executable.

block_cipher = None

a = Analysis([
    'client/run.py',
],
    pathex=[],
    binaries=[],
    datas=[('data/bptimer/boss_mapping.json', 'data/bptimer')],
    hiddenimports=[
        'bpsr_labs.packet_decoder.decoder.combat_decode',
        'bpsr_labs.packet_decoder.decoder.framing',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='bptimer_client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bptimer_client'
)
