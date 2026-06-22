# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app/prism-studio.py'],
    pathex=[],
    binaries=[],
    datas=[('app/templates', 'templates'), ('app/static', 'static'), ('app/schemas', 'schemas'), ('app/src', 'src'), ('src', 'backend_bundle/src'), ('official', 'official'), ('survey_library', 'survey_library'), ('examples', 'examples')],
    hiddenimports=['jsonschema', 'xml.etree.ElementTree', 'flask'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pyarrow', 'nibabel', 'pydicom', 'authlib', 'nltk', 'beautifulsoup4', 'bs4', 'pyedflib', 'sphinx', 'sphinx_rtd_theme', 'myst_parser', 'babel', 'docutils', 'pygments'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PrismStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
    icon=['PrismStudio.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PrismStudio',
)
app = BUNDLE(
    coll,
    name='PrismStudio.app',
    icon='PrismStudio.icns',
    bundle_identifier='at.ac.uni-graz.mri.prism-studio',
)
