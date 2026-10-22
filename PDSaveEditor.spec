# PyInstaller spec for the web editor.
#   pyinstaller --noconfirm PDSaveEditor.spec                     -> dist/PDSaveEditor(.exe)   one file
#   PDSAVE_ONEDIR=1 pyinstaller --noconfirm PDSaveEditor.spec      -> dist/PDSaveEditor/         folder (AppImage)
# Game data is NOT bundled; the app extracts it from the user's own game install on first start.
import os
import sys

ONEDIR = os.environ.get('PDSAVE_ONEDIR') == '1'
ICON = os.path.join('packaging', 'icon.png')
# Windows build is a windowed app (log goes to a file)
CONSOLE = sys.platform != 'win32'
NAME = 'PDSaveEditor'

# native window: WebView2 (Edge) on Windows, Qt WebEngine on Linux; the app falls back to the browser
WINDOW_IMPORTS = ['webview', 'webview.platforms.edgechromium', 'clr'] if sys.platform == 'win32' else [
    'webview', 'webview.platforms.qt', 'qtpy', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebChannel', 'PyQt6.QtNetwork', 'PyQt6.QtPrintSupport']

a = Analysis(
    ['pdedit_web.py'],
    pathex=['.', 'extract'],
    datas=[('web', 'web')],
    hiddenimports=['PIL.DdsImagePlugin', 'PIL.PngImagePlugin'] + WINDOW_IMPORTS,
    excludes=['tkinter', 'unittest', 'pydoc_data'],
    noarchive=False,
)


def slim_qt(toc):
    """Drop Qt parts the editor window never uses (3D, multimedia, QML modules, most translations, GTK theme)."""
    import re
    keep_libs = {'Core', 'DBus', 'Gui', 'Network', 'OpenGL', 'OpenGLWidgets', 'Positioning', 'PrintSupport', 'Qml',
                 'QmlMeta', 'QmlModels', 'QmlWorkerScript', 'Quick', 'QuickWidgets', 'WaylandClient',
                 'WlShellIntegration', 'WebChannel', 'WebEngineCore', 'WebEngineWidgets', 'Widgets', 'XcbQpa',
                 'EglFSDeviceIntegration', 'EglFsKmsSupport', 'Svg'}
    out = []
    for entry in toc:
        dest = entry[0].replace('\\', '/')
        m = re.search(r'PyQt6/Qt6/lib/libQt6(\w+?)\.so', dest)
        if m and m.group(1) not in keep_libs:
            continue
        if '/Qt6/qml/' in dest:
            continue
        if '/Qt6/translations/' in dest and not re.search(r'qtwebengine_locales/(en-US|ru)\.pak$', dest):
            continue
        if re.search(r'platformthemes/libqgtk3|position/libqtposition_nmea|lib(gtk-3|gdk-3|atk-1|atk-bridge|atspi|glycin|epoxy|cairo-gobject)\b', dest):
            continue
        out.append(entry)
    return out


# Libraries that must come from the user's system, not the build machine: the C++ runtime and the
# graphics/display stack have to match the host GPU drivers (an old bundled libstdc++ breaks Mesa/EGL
# and QtWebEngine aborts before the window appears). Same idea as the AppImage project's excludelist.
HOST_LIBS = r'^lib(stdc\+\+|gcc_s|EGL|GL|GLX|GLdispatch|OpenGL|gbm|drm|wayland-[a-z]+|X11|X11-xcb|Xext|Xrender|Xfixes|' \
            r'Xi|Xrandr|Xcursor|Xinerama|Xau|Xdmcp|xcb-[a-z0-9-]+|xkbcommon|xkbcommon-x11|xkbfile|fontconfig|freetype|' \
            r'harfbuzz|glib-2\.0|gio-2\.0|gobject-2\.0|gmodule-2\.0|gthread-2\.0|pcre2-8|dbus-1|asound|va|va-drm|' \
            r'udev|systemd|selinux|mount|blkid)\.so'


def drop_host_libs(toc):
    import re

    def is_host(name):
        # wheels vendor private copies with a hash in the name (libxcb-b8a56d01.so.1.1.0): keep those
        return re.match(HOST_LIBS, name) and not re.search(r'-[0-9a-f]{8}\.so', name)
    return [e for e in toc if not is_host(os.path.basename(e[0]))]


if sys.platform.startswith('linux'):
    a.binaries = drop_host_libs(slim_qt(a.binaries))
    a.datas = slim_qt(a.datas)

pyz = PYZ(a.pure)

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME,
              console=CONSOLE, upx=False, strip=False, debug=False, icon=ICON)
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False, strip=False)
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=NAME,
              console=CONSOLE, upx=False, strip=False, debug=False, icon=ICON)
