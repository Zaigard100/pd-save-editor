#!/usr/bin/env python3
"""Pacific Drive save editor (Tk GUI).  Usage: pdedit_gui.py [SAVE]"""
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import pdsave
import pdtools

CONTAINER = ':*>AM'
DEFAULT_DIR = os.path.expandvars(r'%LOCALAPPDATA%\PenDriverPro\Saved\SaveGames') if os.name == 'nt' else os.getcwd()


def preview(v, t):
    if isinstance(v, (dict, list)) and t and t[0] in CONTAINER:
        return '<%d>' % len(v)
    if t == '$' and v:
        kind = {'@': 'obj', '$': 'global', '*': 'asset'}.get(v[0], '?')
        return '%s %s' % (kind, pdtools.short_asset(v) if v[0] != '@' else v[1:33])
    if t in ('X', '#'):
        return '<%d bytes base64>' % len(v)
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v


class App:
    def __init__(self, root, path=None):
        self.root = root
        self.save = None
        self.dirty = False
        root.title('Pacific Drive save editor')
        root.geometry('1200x750')

        bar = ttk.Frame(root)
        bar.pack(fill='x')
        for text, cmd in (('Open…', self.open), ('Save', self.do_save), ('Save as…', self.save_as),
                          ('Export JSON…', self.export)):
            ttk.Button(bar, text=text, command=cmd).pack(side='left', padx=2, pady=2)
        ttk.Label(bar, text='  Search:').pack(side='left')
        self.q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.q, width=40)
        e.pack(side='left')
        e.bind('<Return>', lambda _: self.search())
        ttk.Button(bar, text='Find', command=self.search).pack(side='left', padx=2)
        self.status = tk.StringVar(value='Open a save (odsaveN.sav)')
        ttk.Label(root, textvariable=self.status, anchor='w').pack(fill='x', side='bottom')

        nb = ttk.Notebook(root)
        nb.pack(fill='both', expand=True)
        self.nb = nb

        # --- tree tab
        f = ttk.Frame(nb)
        nb.add(f, text='Tree')
        pw = ttk.PanedWindow(f, orient='vertical')
        pw.pack(fill='both', expand=True)
        tf = ttk.Frame(pw)
        self.tree = ttk.Treeview(tf, columns=('type', 'value'), selectmode='browse')
        self.tree.heading('#0', text='Field')
        self.tree.heading('type', text='Type')
        self.tree.heading('value', text='Value')
        self.tree.column('#0', width=420)
        self.tree.column('type', width=70, stretch=False)
        self.tree.column('value', width=650)
        ys = ttk.Scrollbar(tf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side='left', fill='both', expand=True)
        ys.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewOpen>>', self.on_open)
        self.tree.bind('<Double-1>', self.on_edit)
        self.tree.bind('<Button-3>', self.on_menu)
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.status.set(self.tree.focus()))
        pw.add(tf, weight=4)
        rf = ttk.Frame(pw)
        self.results = tk.Listbox(rf, height=8)
        self.results.pack(fill='both', expand=True)
        self.results.bind('<Double-1>', self.goto_result)
        pw.add(rf, weight=1)
        self.result_paths = []

        # --- quick tab
        self.quick = ttk.Frame(nb)
        nb.add(self.quick, text='Quick edit')

        if path:
            self.load(path)

    # ------------------------------------------------------------ file ops
    def open(self):
        p = filedialog.askopenfilename(initialdir=DEFAULT_DIR, filetypes=[('Pacific Drive save', '*.sav'), ('All', '*')])
        if p:
            self.load(p)

    def load(self, path):
        try:
            self.save = pdtools.Save(path)
        except Exception as e:  # noqa: BLE001 - show any decode failure to the user
            messagebox.showerror('Open failed', str(e))
            return
        self.dirty = False
        self.root.title('Pacific Drive save editor — %s' % path)
        self.tree.delete(*self.tree.get_children())
        for tag, doc in self.save.docs.items():
            if doc:
                self.add_node('', tag, tag, doc['root'], doc['type'])
        self.build_quick()
        self.status.set('Loaded %s' % path)

    def do_save(self, path=None):
        if not self.save:
            return
        try:
            bak = self.save.save(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror('Save failed', str(e))
            return
        self.dirty = False
        self.status.set('Saved %s%s' % (path or self.save.path, ('  (backup: %s)' % bak) if bak else ''))

    def save_as(self):
        p = filedialog.asksaveasfilename(defaultextension='.sav', initialdir=os.path.dirname(self.save.path) if self.save else DEFAULT_DIR)
        if p:
            self.do_save(p)

    def export(self):
        if not self.save:
            return
        p = filedialog.asksaveasfilename(defaultextension='.json')
        if p:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(self.save.docs, f, indent=1, ensure_ascii=False)
            self.status.set('Exported %s' % p)

    # ------------------------------------------------------------ tree
    def label_for(self, disp, v, t):
        if t == '>' and isinstance(v, dict):
            cls = v.get('_class|^', '').rsplit('.', 1)[-1]
            return '%s  [%s  %s]' % (disp.split('|')[0], cls, v.get('_name|N', ''))
        return disp.split('|')[0] if '|' in disp else disp

    def add_node(self, parent, iid, disp, v, t):
        is_cont = isinstance(v, (dict, list)) and t and t[0] in CONTAINER
        self.tree.insert(parent, 'end', iid=iid, text=self.label_for(disp, v, t),
                         values=(t, preview(v, t)), open=False)
        if is_cont and len(v):
            self.tree.insert(iid, 'end', iid=iid + '/::dummy', text='…')

    def on_open(self, _evt=None, iid=None):
        iid = iid or self.tree.focus()
        kids = self.tree.get_children(iid)
        if len(kids) == 1 and kids[0].endswith('/::dummy'):
            self.tree.delete(kids[0])
            _, _, v, t = pdtools.resolve(self.save, iid)
            for i, (step, disp, cv, ct) in enumerate(pdtools.children(v, t)):
                if t[0] == 'M':
                    key = v[i][0]
                    disp = pdtools.short_asset(key) if isinstance(key, str) and key[:1] in '*@$' else str(key)
                    step = '#%d' % i
                self.add_node(iid, iid + '/' + step, disp, cv, ct)

    def refresh_node(self, iid):
        _, _, v, t = pdtools.resolve(self.save, iid)
        self.tree.item(iid, values=(t, preview(v, t)))

    def on_edit(self, _evt):
        iid = self.tree.focus()
        if not iid or not self.save:
            return
        _, _, v, t = pdtools.resolve(self.save, iid)
        if isinstance(v, (dict, list)) and t[0] in CONTAINER:
            return
        if t in ('X', '#'):
            messagebox.showinfo('Not editable', 'FText / binary blobs are kept as raw base64; edit them via JSON export/import.')
            return
        init = json.dumps(v) if isinstance(v, (list, dict)) else ('' if v is None else str(v))
        new = simpledialog.askstring('Edit %s' % t, iid, initialvalue=init, parent=self.root)
        if new is None:
            return
        try:
            pdtools.set_value(self.save, iid, new)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror('Invalid value', str(e))
            return
        self.dirty = True
        self.refresh_node(iid)
        self.status.set('Changed %s (not saved yet)' % iid)

    def on_menu(self, evt):
        iid = self.tree.identify_row(evt.y)
        if not iid or not self.save:
            return
        self.tree.focus(iid)
        self.tree.selection_set(iid)
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label='Copy path', command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(iid)))
        _, _, v, t = pdtools.resolve(self.save, iid)
        if t == '>' and isinstance(v, dict) and v.get('_class|^', '').endswith('Slot') and v.get('_data|*', {}).get('Items|A$'):
            m.add_command(label='Add copies of this slot\'s item…', command=lambda: self.add_items(iid, v))
        if t == '$' and v and v.startswith('@'):
            m.add_command(label='Go to referenced object', command=lambda: self.goto_guid(v[1:33]))
        m.tk_popup(evt.x_root, evt.y_root)

    def add_items(self, iid, slot):
        n = simpledialog.askinteger('Add items', 'How many copies?', minvalue=1, maxvalue=999, parent=self.root)
        if not n:
            return
        guid = iid.rsplit('/', 1)[-1].split('|')[0]
        try:
            pdtools.add_items(self.save, guid, n)
        except ValueError as e:
            if 'capacity' in str(e) and messagebox.askyesno('Capacity', '%s\n\nAdd anyway?' % e):
                pdtools.add_items(self.save, guid, n, force=True)
            else:
                messagebox.showerror('Add items', str(e))
                return
        self.dirty = True
        self.status.set('Added %d items to slot %s (not saved yet)' % (n, guid))
        self.reload_tree_keep()

    def reload_tree_keep(self):
        opened = [i for i in self._all_items() if self.tree.item(i, 'open')]
        focus = self.tree.focus()
        self.tree.delete(*self.tree.get_children())
        for tag, doc in self.save.docs.items():
            if doc:
                self.add_node('', tag, tag, doc['root'], doc['type'])
        for i in opened:
            self.expand_to(i)
        if focus and self.tree.exists(focus):
            self.tree.see(focus)
            self.tree.focus(focus)

    def _all_items(self, parent=''):
        for i in self.tree.get_children(parent):
            yield i
            yield from self._all_items(i)

    def expand_to(self, path):
        parts = path.split('/')
        cur = parts[0]
        for p in parts[1:] + [None]:
            if not self.tree.exists(cur):
                return False
            if p is None:
                break
            self.on_open(iid=cur)
            self.tree.item(cur, open=True)
            cur = cur + '/' + p
        self.tree.see(cur)
        self.tree.focus(cur)
        self.tree.selection_set(cur)
        return True

    def goto_guid(self, guid):
        for path, v, t, label in pdtools.walk(self.save.root('GAME'), self.save.docs['GAME']['type'], 'GAME'):
            if t == '>' and path.endswith('/' + guid):
                self.expand_to(path)
                return
        messagebox.showinfo('Not found', guid)

    # ------------------------------------------------------------ search
    def search(self):
        if not self.save or not self.q.get():
            return
        try:
            hits = pdtools.find(self.save, self.q.get(), limit=500)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror('Search', str(e))
            return
        self.results.delete(0, 'end')
        self.result_paths = []
        for path, t, v in hits:
            self.result_paths.append(path)
            self.results.insert('end', '%s  [%s]  %s' % (path, t, preview(v, t)[:120]))
        self.status.set('%d hits%s' % (len(hits), ' (limited)' if len(hits) >= 500 else ''))

    def goto_result(self, _evt):
        sel = self.results.curselection()
        if sel:
            self.nb.select(0)
            self.expand_to(self.result_paths[sel[0]])

    # ------------------------------------------------------------ quick edit
    def build_quick(self):
        for w in self.quick.winfo_children():
            w.destroy()
        if not self.save.docs.get('GAME'):
            return
        row = 0

        def section(title):
            nonlocal row
            ttk.Label(self.quick, text=title, font=('TkDefaultFont', 11, 'bold')).grid(row=row, column=0, sticky='w', pady=(10, 2), padx=8)
            row += 1

        def entry(label, getter, setter):
            nonlocal row
            ttk.Label(self.quick, text=label).grid(row=row, column=0, sticky='w', padx=16)
            var = tk.StringVar(value=str(getter()))
            ent = ttk.Entry(self.quick, textvariable=var, width=20)
            ent.grid(row=row, column=1, sticky='w')

            def apply(*_):
                try:
                    setter(var.get())
                except ValueError:
                    self.status.set('%s: invalid value %r (ignored)' % (label, var.get()))
                    return
                self.dirty = True
                self.status.set('%s = %s (not saved yet)' % (label, var.get()))
            var.trace_add('write', apply)
            row += 1

        section('Currencies (BP_InventoryManager.CurrencyTable, int64)')
        for pair in pdtools.currencies(self.save):
            entry(pdtools.short_asset(pair[0]).replace('CA_', ''),
                  lambda p=pair: p[1], lambda s, p=pair: p.__setitem__(1, int(s)))
        section('Resources (BP_ResourceManager.CurrentValues, float)')
        for pair in pdtools.resources(self.save):
            entry(pair[0], lambda p=pair: p[1], lambda s, p=pair: p.__setitem__(1, float(s)))
        ttk.Label(self.quick, text='Values apply as you type (invalid input is ignored); then press Save.').grid(row=row, column=0, columnspan=2, sticky='w', padx=8, pady=10)


def main():
    root = tk.Tk()
    app = App(root, sys.argv[1] if len(sys.argv) > 1 else None)

    def on_close():
        if app.dirty and not messagebox.askyesno('Unsaved changes', 'Discard unsaved changes?'):
            return
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
