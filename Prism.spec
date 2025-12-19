# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['prism-studio.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static'), ('schemas', 'schemas'), ('src', 'src'), ('survey_library', 'survey_library')],
    hiddenimports=['jsonschema', 'xml.etree.ElementTree', 'pkg_resources.extern'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Prism',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Prism.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Prism',
)
app = BUNDLE(
    coll,
    name='Prism.app',
    icon='Prism.icns',
    bundle_identifier='at.ac.uni-graz.mri.prism',
)
