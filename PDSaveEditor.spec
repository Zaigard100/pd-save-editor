# PyInstaller spec for the web editor.
#   pyinstaller --noconfirm PDSaveEditor.spec                     -> dist/PDSaveEditor(.exe)   one file
#   PDSAVE_ONEDIR=1 pyinstaller --noconfirm PDSaveEditor.spec      -> dist/PDSaveEditor/         folder (AppImage)
# Game data is NOT bundled; the app extracts it from the user's own game install on first start.
import os

ONEDIR = os.environ.get('PDSAVE_ONEDIR') == '1'
ICON = os.path.join('packaging', 'icon.png')

a = Analysis(
    ['pdedit_web.py'],
    pathex=['.', 'extract'],
    datas=[('web', 'web')],
    hiddenimports=['PIL.DdsImagePlugin', 'PIL.PngImagePlugin'],
    excludes=['tkinter', 'unittest', 'pydoc_data'],
    noarchive=False,
)
pyz = PYZ(a.pure)

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PDSaveEditor',
              console=True, upx=False, strip=False, debug=False, icon=ICON)
    coll = COLLECT(exe, a.binaries, a.datas, name='PDSaveEditor', upx=False, strip=False)
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='PDSaveEditor',
              console=True, upx=False, strip=False, debug=False, icon=ICON)
