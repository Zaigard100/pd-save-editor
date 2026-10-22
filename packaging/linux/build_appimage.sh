#!/usr/bin/env bash
# Build dist/PDSaveEditor-x86_64.AppImage from a PyInstaller onedir build.
#   PDSAVE_ONEDIR=1 pyinstaller --noconfirm PDSaveEditor.spec
#   APPIMAGETOOL=/path/to/appimagetool packaging/linux/build_appimage.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

TOOL="${APPIMAGETOOL:-appimagetool}"
APPDIR=build/AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/pdsave-editor" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -a dist/PDSaveEditor/. "$APPDIR/usr/lib/pdsave-editor/"
install -m 755 packaging/linux/AppRun "$APPDIR/AppRun"
install -m 644 packaging/linux/pdsave-editor.desktop "$APPDIR/pdsave-editor.desktop"
install -m 644 packaging/linux/pdsave-editor.desktop "$APPDIR/usr/share/applications/pdsave-editor.desktop"
install -m 644 packaging/icon.png "$APPDIR/pdsave-editor.png"
install -m 644 packaging/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/pdsave-editor.png"
ln -sf pdsave-editor.png "$APPDIR/.DirIcon"

# appimagetool is itself an AppImage; extract-and-run avoids needing FUSE (CI containers)
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" dist/PDSaveEditor-x86_64.AppImage
chmod +x dist/PDSaveEditor-x86_64.AppImage
ls -la dist/PDSaveEditor-x86_64.AppImage
