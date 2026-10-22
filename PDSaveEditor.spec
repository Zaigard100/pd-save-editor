# PyInstaller spec: one-file build of the web editor for Windows and Linux.
#   pyinstaller --noconfirm PDSaveEditor.spec
# Game data is NOT bundled; the app extracts it from the user's own game install on first start.

a = Analysis(
    ['pdedit_web.py'],
    pathex=['.', 'extract'],
    datas=[('web', 'web')],
    hiddenimports=['PIL.DdsImagePlugin', 'PIL.PngImagePlugin'],
    excludes=['tkinter', 'unittest', 'pydoc_data'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDSaveEditor',
    console=True,
    upx=False,
    strip=False,
    debug=False,
)
