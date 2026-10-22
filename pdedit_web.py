#!/usr/bin/env python3
"""Pacific Drive save editor — game-style UI in the browser (Windows / Linux).

  PDSaveEditor [SAVE_DIR_OR_FILE] [--port 8765] [--no-browser] [--data DIR]

On first start it finds the installed game and extracts names, icons and layouts
from its .pak files into the user data folder (nothing from the game is shipped).
Everything runs locally; the server listens on 127.0.0.1 only.
"""
import argparse
import glob
import json
import os
import posixpath
import re
import shutil
import sys
import threading
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
RES = getattr(sys, '_MEIPASS', HERE)            # bundled resources (PyInstaller) or the source tree
sys.path.insert(0, os.path.join(RES, 'extract'))

import build_gamedata  # noqa: E402  (extract/, also pulls upak/uasset/utexture into the bundle)
import pdmodel  # noqa: E402
from version import __version__  # noqa: E402

STEAM_APPID = '1458140'
GAME_FOLDER = 'Pacific Drive'
SAVE_SUBDIR = os.path.join('PenDriverPro', 'Saved', 'SaveGames')


# ---------------------------------------------------------------- locations
def user_data_dir():
    if os.environ.get('PDSAVE_DATA'):
        return os.environ['PDSAVE_DATA']
    if os.name == 'nt':
        return os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'PDSaveEditor')
    return os.path.join(os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share'), 'pdsave-editor')


def steam_roots():
    roots = []
    if os.name == 'nt':
        try:
            import winreg
            for hive, key, val in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                   (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
                                   (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam', 'InstallPath')):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        roots.append(winreg.QueryValueEx(k, val)[0])
                except OSError:
                    pass
        except ImportError:
            pass
        roots += [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    else:
        home = os.path.expanduser('~')
        roots += [os.path.join(home, p) for p in ('.local/share/Steam', '.steam/steam', '.steam/root',
                                                    '.var/app/com.valvesoftware.Steam/.local/share/Steam',
                                                    'snap/steam/common/.local/share/Steam')]
    out = []
    for r in roots:
        r = os.path.normpath(r)
        if os.path.isdir(r) and os.path.realpath(r) not in [os.path.realpath(x) for x in out]:
            out.append(r)
    return out


def steam_libraries():
    libs = []
    for root in steam_roots():
        libs.append(root)
        vdf = os.path.join(root, 'steamapps', 'libraryfolders.vdf')
        try:
            with open(vdf, encoding='utf-8', errors='replace') as f:
                for path in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                    libs.append(path.replace('\\\\', '\\'))
        except OSError:
            pass
    seen, out = set(), []
    for lib in libs:
        real = os.path.realpath(lib)
        if real not in seen and os.path.isdir(lib):
            seen.add(real)
            out.append(lib)
    return out


def find_game_dirs():
    cands = [os.path.join(lib, 'steamapps', 'common', GAME_FOLDER) for lib in steam_libraries()]
    if os.name == 'nt':
        cands += [r'C:\Program Files\Epic Games\PacificDrive', r'C:\Program Files (x86)\GOG Galaxy\Games\Pacific Drive']
    out = []
    for c in cands:
        try:
            build_gamedata.find_paks(c)
        except (FileNotFoundError, OSError):
            continue
        if os.path.realpath(c) not in [os.path.realpath(x) for x in out]:
            out.append(c)
    return out


def default_save_dirs():
    dirs = []
    if os.name == 'nt':
        dirs.append(os.path.join(os.environ.get('LOCALAPPDATA', ''), SAVE_SUBDIR))
    for lib in steam_libraries():
        dirs.append(os.path.join(lib, 'steamapps', 'compatdata', STEAM_APPID, 'pfx', 'drive_c', 'users', 'steamuser',
                                 'AppData', 'Local', SAVE_SUBDIR))
    out = []
    for d in dirs:
        if os.path.isdir(d) and os.path.realpath(d) not in [os.path.realpath(x) for x in out]:
            out.append(d)
    return out


# ---------------------------------------------------------------- application state
class App:
    def __init__(self, save_dir, data_dir):
        self.lock = threading.Lock()
        self.data_dir = data_dir
        self.gamedata = os.path.join(data_dir, 'gamedata')
        pdmodel.GAMEDATA = self.gamedata
        self.dir = save_dir
        self.model = None
        self.setup = {'running': False, 'log': [], 'error': None}
        self.server = None
        self.window = None
        self.page_loaded = False     # set when the UI asked for /api/gamedata (proves the window works)
        self.settings_path = os.path.join(data_dir, 'settings.json')
        try:
            with open(self.settings_path, encoding='utf-8') as f:
                self.settings = json.load(f)
        except (OSError, ValueError):
            self.settings = {}
        self.load_gamedata()

    def apply_settings(self, model):
        owned = self.settings.get('ownedPacks')
        model.owned_packs = set(owned) if owned is not None else None

    def gamedata_ready(self):
        try:
            with open(os.path.join(self.gamedata, 'meta.json')) as f:
                return json.load(f).get('version') == build_gamedata.DATA_VERSION
        except (OSError, ValueError):
            return False

    def load_gamedata(self):
        self.gd = pdmodel.load_gamedata() if self.gamedata_ready() else None
        self.game_version = self.read_game_version() if self.gd else {}

    def read_game_version(self):
        # data extracted by older editors has no version -> read it from the game once and remember it
        path = os.path.join(self.gamedata, 'meta.json')
        try:
            with open(path) as f:
                meta = json.load(f)
            if 'gameVersion' not in meta:
                import upak
                meta['gameVersion'], meta['gameBuild'] = build_gamedata.game_version(upak.PakSet(build_gamedata.find_paks(meta['game'])))
                with open(path, 'w') as f:
                    json.dump(meta, f)
            return {'version': meta['gameVersion'], 'build': meta.get('gameBuild', '')}
        except Exception:  # noqa: BLE001 - game moved or unreadable: version unknown
            return {}

    def saves(self):
        out = []
        dirs = [self.dir] if self.dir else default_save_dirs()
        for d in dirs:
            for p in sorted(glob.glob(os.path.join(d, '*.sav'))):
                if '-backup-' in os.path.basename(p):
                    continue
                out.append({'path': p, 'name': os.path.basename(p), 'size': os.path.getsize(p),
                            'mtime': os.path.getmtime(p)})
        return {'dirs': dirs, 'saves': out}

    # -------------------------------------------------- first-run extraction
    def setup_status(self):
        return {'ready': self.gd is not None, 'candidates': find_game_dirs(), 'running': self.setup['running'],
                'log': self.setup['log'][-30:], 'error': self.setup['error'], 'dataDir': self.gamedata,
                'version': __version__}

    def setup_start(self, game):
        if self.setup['running']:
            return self.setup_status()
        try:
            build_gamedata.find_paks(game)
        except (FileNotFoundError, OSError) as e:
            raise pdmodel.EditError(str(e))
        self.setup = {'running': True, 'log': [], 'error': None}

        def log(*args):
            self.setup['log'].append(' '.join(str(a) for a in args))

        def run():
            tmp = self.gamedata + '.new'
            try:
                shutil.rmtree(tmp, ignore_errors=True)
                os.makedirs(tmp, exist_ok=True)
                build_gamedata.build(game, tmp, log)
                shutil.rmtree(self.gamedata, ignore_errors=True)
                os.replace(tmp, self.gamedata)
                with self.lock:
                    self.load_gamedata()
                    if self.model is not None:
                        self.model.gd = self.gd
            except Exception as e:  # noqa: BLE001 - shown in the UI
                traceback.print_exc()
                self.setup['error'] = '%s: %s' % (type(e).__name__, e)
            finally:
                self.setup['running'] = False
        threading.Thread(target=run, daemon=True).start()
        return self.setup_status()

    # -------------------------------------------------- editing API
    def call(self, op, a):
        if op == 'setup_status':
            return self.setup_status()
        if op == 'setup_build':
            return self.setup_start(a['game'])
        if op == 'quit':
            if self.window is not None:
                threading.Timer(0.3, self.window.destroy).start()    # closing the window stops everything
            elif self.server:
                threading.Timer(0.3, self.server.shutdown).start()   # let the response go out first
            return {'bye': True}
        if self.gd is None:
            raise pdmodel.EditError('game data is not extracted yet')
        m = self.model
        if op == 'open':
            self.model = pdmodel.Model(a['path'], self.gd)
            self.apply_settings(self.model)
            return self.model.state()
        if op == 'packs_set':
            self.settings['ownedPacks'] = list(a['owned'])
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=1)
            if m is not None:
                self.apply_settings(m)
                return m.state()
            return {'ok': True}
        if op == 'setdir':
            self.dir = a['dir']
            return self.saves()
        if m is None:
            raise pdmodel.EditError('no save is open')
        if op == 'state':
            return m.state()
        if op == 'place':
            m.place_item(a['cont'], a['arche'], int(a['x']), int(a['y']), bool(a.get('rot')),
                         int(a.get('count', 1)), bool(a.get('force')))
        elif op == 'count':
            m.set_slot_count(a['slot'], int(a['count']), bool(a.get('force')))
        elif op == 'move':
            m.move_slot(a['cont'], a['slot'], int(a['x']), int(a['y']), bool(a.get('rot')))
        elif op == 'delete':
            m.delete_slot(a['cont'], a['slot'])
        elif op == 'total':
            m.set_list_total(a['cont'], a['arche'], int(a['total']))
        elif op == 'currency':
            m.set_currency(a['arche'], int(a['value']))
        elif op == 'resource':
            m.set_resource(a['name'], float(a['value']))
        elif op == 'settings':
            m.set_settings(a.get('preset'), a.get('overrides'))
        elif op == 'slotinfo':
            return {'instances': m.slot_info(a['slot'])}
        elif op == 'prop':
            m.set_instance_prop(a['item'], a['ip'], a['field'], a['value'])
        elif op == 'repair':
            m.repair_instance(a['item'])
        elif op == 'effect_add':
            m.add_effect(a['item'], a['cls'])
        elif op == 'effect_remove':
            m.remove_effect(a['item'], a['effect'])
        elif op == 'tint':
            m.set_tint(a['item'], a['kind'], a.get('palette'))
        elif op == 'carpart':
            m.set_car_part(a['slot'], a['arche'])
        elif op == 'carrepair':
            m.repair_car()
        elif op == 'named':
            m.named_set(a['slot'], a.get('arche'), int(a.get('count', 1)))
        elif op == 'research':
            m.set_research(a['node'], a['state'])
        elif op == 'log':
            m.set_log(a['path'], bool(a['on']))
        elif op == 'logmany':
            m.set_log_many(a['paths'], bool(a['on']))
        elif op == 'logack':
            m.set_log_ack(a['path'], bool(a['on']))
        elif op == 'wb':
            m.set_whiteboard(a['tag'], a.get('value'))
        elif op == 'quirk_diag':
            m.quirk_diagnose(a['quirk'], bool(a['on']))
        elif op == 'quirk_cure':
            m.quirk_cure(a['quirk'])
        elif op == 'quirk_curelist':
            m.quirk_set_cure(a['quirk'], a['cure'])
        elif op == 'quirk_add':
            m.quirk_add(a['condition'], a['behavior'], bool(a.get('diagnosed')))
        elif op == 'quirk_grave_del':
            m.quirk_grave_remove(a['condition'], a['behavior'])
        elif op == 'quirk_flag':
            m.quirk_flag(a['name'], bool(a['on']))
        elif op == 'map_flag':
            m.map_leg_flag(a['leg'], a['flag'], bool(a['on']))
        elif op == 'map_anchors':
            m.map_leg_anchors(a['leg'], int(a['value']))
        elif op == 'map_wb':
            m.map_leg_wb(a['leg'], a['tag'], a.get('value'))
        elif op == 'map_mod':
            m.map_leg_modifier(a['leg'], a['rm'], bool(a['on']))
        elif op == 'map_pool':
            m.map_leg_pool(a['leg'], a['kind'], a['cls'], bool(a['on']))
        elif op == 'map_current':
            m.map_set_current(a['leg'])
        elif op == 'map_reveal_all':
            m.map_reveal_all()
        elif op == 'map_instability':
            m.map_instability(float(a['value']))
        elif op == 'install':
            m.set_installed(a['node'], bool(a['on']))
        elif op == 'save':
            bak = m.write()
            st = m.state()
            st['backup'] = bak
            return st
        elif op == 'packs_clean':
            owned = self.settings.get('ownedPacks')
            if owned is None:
                raise pdmodel.EditError('mark the packs you own first')
            st = m.state()
            st['cleaned'] = m.clean_packs(owned)
            st.update(m.state())
            return st
        elif op == 'packs_preview':
            return {'report': m.pack_report(a.get('owned', self.settings.get('ownedPacks') or []))}
        elif op == 'add_all':
            n = m.add_all(a['cont'])
            st = m.state()
            st['added'] = n
            return st
        elif op == 'reload':
            self.model = pdmodel.Model(m.path, self.gd)
            self.apply_settings(self.model)
            return self.model.state()
        else:
            raise pdmodel.EditError('unknown operation %s' % op)
        return m.state()


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    app = None
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map, **{
        '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png',
        '.ttf': 'font/ttf', '.otf': 'font/otf', '.html': 'text/html'})

    def log_message(self, fmt, *args):
        if os.environ.get('PDSAVE_DEBUG'):
            sys.stderr.write('%s\n' % (fmt % args))

    def translate_path(self, path):
        p = urlparse(path).path
        if p.startswith('/gamedata/'):
            base, rel = self.app.gamedata, p[len('/gamedata/'):]
        else:
            base, rel = RES, p.lstrip('/')
        rel = posixpath.normpath(unquote(rel))
        if rel.startswith('..') or rel.startswith('/'):
            return os.path.join(RES, '__forbidden__')
        return os.path.join(base, *rel.split('/'))

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            self.path = '/web/index.html'
        elif path == '/api/saves':
            return self.send_json(200, self.app.saves())
        elif path == '/api/gamedata':
            self.app.page_loaded = True
            gd = self.app.gd
            return self.send_json(200, dict(gd, version=__version__, game=self.app.game_version) if gd else {'missing': True, 'version': __version__})
        elif not (path.startswith('/web/') or path.startswith('/gamedata/')):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith('/api/'):
            return self.send_error(404)
        # only accept requests from our own page
        origin = self.headers.get('Origin')
        if origin and not origin.startswith(('http://127.0.0.1:', 'http://localhost:')):
            return self.send_error(403)
        n = int(self.headers.get('Content-Length') or 0)
        try:
            a = json.loads(self.rfile.read(n) or b'{}')
            op = unquote(path[5:])
            if op.startswith('setup_') or op == 'quit':
                res = self.app.call(op, a)
            else:
                with self.app.lock:
                    res = self.app.call(op, a)
            self.send_json(200, res)
        except pdmodel.EditError as e:
            self.send_json(400, {'error': str(e)})
        except Exception as e:  # noqa: BLE001 - report to the UI instead of dropping the connection
            traceback.print_exc()
            self.send_json(500, {'error': '%s: %s' % (type(e).__name__, e)})


def clean_child_env():
    """PyInstaller points LD_LIBRARY_PATH at its bundled libs; restore the user's value so the
    browser started by webbrowser.open (xdg-open) uses the system libraries."""
    if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
        orig = os.environ.get('LD_LIBRARY_PATH_ORIG')
        if orig:
            os.environ['LD_LIBRARY_PATH'] = orig
        else:
            os.environ.pop('LD_LIBRARY_PATH', None)


def make_server(port):
    for p in [port] + list(range(port + 1, port + 20)):
        try:
            return ThreadingHTTPServer(('127.0.0.1', p), Handler), p
        except OSError:
            continue
    return ThreadingHTTPServer(('127.0.0.1', 0), Handler), None


WINDOW_TEXT = {
    'ru': ('Есть несохранённые изменения', 'Закрыть редактор без сохранения?'),
    'en': ('Unsaved changes', 'Close the editor without saving?'),
}


def open_window(url, app):
    """Show the editor in its own window (WebView2 on Windows, Qt WebEngine on Linux).
    Blocks until the window is closed. Returns False when no native window is available."""
    try:
        import webview
    except ImportError:
        return False
    if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
        # bundled Chromium cannot always set up its sandbox inside an AppImage; the page is our own localhost UI
        os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
    lang = 'ru' if (os.environ.get('LANG', '') + os.environ.get('LANGUAGE', '')).lower().startswith(('ru', 'uk')) else 'en'
    try:
        import locale
        if os.name == 'nt' and (locale.getdefaultlocale()[0] or '').lower().startswith(('ru', 'uk')):
            lang = 'ru'
    except Exception:  # noqa: BLE001
        pass
    win = webview.create_window('PD Save Editor %s' % __version__, url, width=1500, height=950,
                                min_size=(1000, 680), background_color='#121513', text_select=True)
    app.window = win

    def on_closing():
        m = app.model
        if m is not None and m.dirty:
            title, text = WINDOW_TEXT[lang]
            return bool(win.create_confirmation_dialog(title, text))
        return True
    win.events.closing += on_closing

    def watchdog():
        # a window that never loads the page (broken WebView2 / GPU stack) -> close it, the caller opens the browser
        for _ in range(50):
            if app.page_loaded or app.window is None:
                return
            threading.Event().wait(0.5)
        print('The app window did not load the editor in 25 s; switching to the web browser.')
        try:
            win.destroy()
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=watchdog, daemon=True).start()
    gui = 'qt' if sys.platform.startswith('linux') else None
    # WinForms only accepts .ico here and kills the process on a .png (uncatchable .NET exception);
    # on Windows the window takes the icon embedded in the exe anyway
    icon = None if os.name == 'nt' else os.path.join(RES, 'web', 'icon.png')
    try:
        webview.start(gui=gui, private_mode=False, storage_path=os.path.join(app.data_dir, 'webview-cache'),
                      icon=icon)
    except Exception as e:  # noqa: BLE001 - fall back to the browser
        print('Native window is not available (%s); using the web browser instead.' % e)
        app.window = None
        return False
    app.window = None
    if not app.page_loaded:
        print('The app window closed without loading the editor; using the web browser instead.')
        return False
    return True


class _Tee:
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:  # noqa: BLE001
                pass

    def flush(self):
        pass


def log_path():
    return os.path.join(user_data_dir(), 'pdsave-editor.log')


def setup_log_file():
    """Packaged builds: keep a log next to the user data (the Windows build has no console)."""
    try:
        os.makedirs(user_data_dir(), exist_ok=True)
        if os.path.exists(log_path()) and os.path.getsize(log_path()) > 2_000_000:
            os.replace(log_path(), log_path() + '.old')
        log = open(log_path(), 'a', encoding='utf-8', buffering=1)
        import datetime
        log.write('\n==== %s  PD Save Editor %s  %s\n' % (datetime.datetime.now().isoformat(' ', 'seconds'),
                                                        __version__, sys.platform))
        sys.stdout = _Tee(sys.stdout, log)
        sys.stderr = _Tee(sys.stderr, log)
    except OSError:
        pass


def report_fatal(exc_text):
    """Last-resort error report: log file + a message box on Windows (no console there)."""
    try:
        os.makedirs(user_data_dir(), exist_ok=True)
        with open(log_path(), 'a', encoding='utf-8') as f:
            f.write(exc_text)
    except OSError:
        pass
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'PD Save Editor failed to start:\n\n%s\n\nLog: %s'
                                             % (exc_text[-1500:], log_path()), 'PD Save Editor', 0x10)
        except Exception:  # noqa: BLE001
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', nargs='?', help='save folder or .sav file')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true', help='only start the server (no window, no browser)')
    ap.add_argument('--browser', action='store_true', help='open in the web browser instead of an app window')
    ap.add_argument('--data', help='folder for extracted game data (default: user data folder)')
    ap.add_argument('--debug', action='store_true', help='verbose log (also PDSAVE_DEBUG=1)')
    ap.add_argument('--version', action='version', version=__version__)
    a = ap.parse_args()
    if a.debug:
        os.environ['PDSAVE_DEBUG'] = '1'
    if getattr(sys, 'frozen', False) or sys.stdout is None:
        setup_log_file()
    if os.environ.get('PDSAVE_DEBUG'):
        import logging
        import platform
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format='%(asctime)s %(name)s %(levelname)s %(message)s')
        logging.getLogger('pywebview').setLevel(logging.DEBUG)
        print('debug: python %s, %s, frozen=%s, exe=%s' % (platform.python_version(), platform.platform(),
                                                          getattr(sys, 'frozen', False), sys.executable))
        try:
            import webview
            print('debug: pywebview %s' % getattr(webview, '__version__', '?'))
        except Exception as e:  # noqa: BLE001
            print('debug: pywebview import failed: %r' % e)
    # running from a source checkout with gamedata/ next to the code keeps using it
    data_dir = a.data or (HERE if not getattr(sys, 'frozen', False) and os.path.isfile(os.path.join(HERE, 'gamedata', 'meta.json'))
                          else user_data_dir())
    target = a.target
    app = App(os.path.dirname(target) if target and target.endswith('.sav') else target, data_dir)
    if target and target.endswith('.sav') and app.gd:
        app.call('open', {'path': target})
    Handler.app = app
    srv, _ = make_server(a.port)
    app.server = srv
    url = 'http://127.0.0.1:%d/' % srv.server_address[1]
    print('Pacific Drive save editor %s: %s' % (__version__, url))
    print('Game data: %s' % app.gamedata)
    server_thread = threading.Thread(target=srv.serve_forever, daemon=True)
    server_thread.start()
    if not a.no_browser and not a.browser and open_window(url, app):
        srv.shutdown()          # the window was closed
        return
    print('Close this window (or press "Exit" in the editor) to stop.')
    if not a.no_browser:
        clean_child_env()
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        while server_thread.is_alive():
            server_thread.join(0.5)
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - make startup failures visible in the windowed build
        report_fatal(traceback.format_exc())
        raise
