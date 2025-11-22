
"""
dbtablewidget_tk.py
-------------------
Tkinter/ttk implementation inspired by the original PySide6 DBTableWidget.

It renders a table using ttk.Treeview, supports human/machine value views,
in-place editing with Entry/Combobox overlays, and a right-click context menu
with three custom actions: Value, Func, and Tfunc.

Expected external dependencies (same as original project):
- DBState, DBModel           (from db.db_types)
- hrt_enum, hrt_bitEnum      (from hrt.*)
- str2type, type2str         (from hrt.hrt_type)
- ReactVar                   (from react.react_var)  # must offer .setValue(...),
                                                     # .type(), .byteSize(), .model,
                                                     # .getFunc(), .setFunc(...),
                                                     # .getTFunc(), .setTFunc(...),
                                                     # .translate(...), ._value,
                                                     # and a .valueChangedSignal
                                                     # with a .connect(callable) method
                                                     # (signal pattern).

Notes:
- Treeview doesn't natively embed per-cell widgets. We overlay an Entry/Combobox
  positioned over the active cell during editing, then destroy it on commit/cancel.
- Auto-complete lists are kept for Func/Tfunc dialogs.
- Standard clipboard actions are provided via the native right-click menu of the edit overlay.

Author: converted from PySide6 to Tkinter/ttk.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

# External project imports (keep same paths used in your project)
from db_files.db_types import DBState, DBModel
from hrt.hrt_enum import hrt_enum
from hrt.hrt_bitenum import hrt_bitEnum
from hrt.hrt_type import str2type, type2str
from react.react_var import ReactVar


class DBTableWidgetTk(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.state = DBState.humanValue
        self.autoCompleteList = {}
        self.dbDataFrame = None
        self.tableName = ""
        self.df = None

        self._editor = None  # overlay widget (Entry/Combobox)
        self._editor_row_id = None
        self._editor_col = None

        # Treeview + scrollbars
        self.tree = ttk.Treeview(self, show="tree headings")
        # configure a coluna #0 para exibir os índices
        self.tree.column("#0", width=160, anchor="w")
        self.tree.heading("#0", text="")  # pode deixar vazio ou colocar "Var" se preferir
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Events
        self.tree.bind("<Double-1>", self._on_double_click_begin_edit)
        self.tree.bind("<Button-3>", self._on_right_click)  # Windows/Linux right-click
        self.tree.bind("<Control-Button-1>", self._on_right_click)  # Mac alternative

        # Close editor if the tree is resized/scrolls to avoid stale placement
        self.tree.bind("<Configure>", lambda e: self._destroy_editor())
        self.tree.bind("<MouseWheel>", lambda e: self._destroy_editor())
        self.tree.bind("<Button-4>", lambda e: self._destroy_editor())  # Linux scroll up
        self.tree.bind("<Button-5>", lambda e: self._destroy_editor())  # Linux scroll down

        # Style tweaks
        style = ttk.Style(self)
        # Users can adjust fonts here if needed:
        style.configure("Treeview.Heading", font=("Arial", 12, "bold"))
        style.configure("Treeview", font=("Arial", 10))

    # -------------------------- Public API --------------------------

    def setAutoCompleteList(self, data: dict):
        self.autoCompleteList = data or {}

    def setBaseData(self, dbDataFrame, tableName: str):
        self.tableName = tableName
        self.dbDataFrame = dbDataFrame
        self.df = dbDataFrame.df[tableName]
        self.redrawAll()

    def changeType(self, isHuman: bool):
        self.state = DBState.humanValue if isHuman else DBState.machineValue
        self.redrawAll()

    # --------------------------- Internals --------------------------

    @staticmethod
    def _get_sync_value(var: ReactVar, state: DBState):
        if state == DBState.humanValue:
            return var._value
        # translate from machine->human or human->machine as needed.
        # The original code translates to machine and then back to human for display;
        # here we follow the same idea used in redrawAll.
        try:
            return var.translate(
                var._value, var.type(), var.byteSize(),
                DBState.machineValue, DBState.humanValue
            )
        except Exception:
            return var._value


    def redrawAll(self):
        # Clear editors if any
        self._destroy_editor()

        # Clear tree
        for col in self.tree["columns"]:
            self.tree.heading(col, text="")
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = ()

        if self.df is None:
            return

        # rows, cols = self.df.shape
        rowKeys = list(self.df.index)
        colKeys = list(self.df.columns)

        # Configure columns
        self.tree["columns"] = colKeys
        for c in colKeys:
            self.tree.heading(c, text=str(c))
            self.tree.column(c, width=150, anchor="w")

        # Insert rows
        for rowName in rowKeys:
            values = []
            for colName in colKeys:
                # ... dentro de redrawAll(), no loop:
                data: ReactVar = self.df.at[rowName, colName]

                if colName in ["BYTE_SIZE", "TYPE"]:
                    # META: nunca traduz; mostra valor bruto como texto
                    display_value = str(data._value)
                else:
                    raw_value = self._get_sync_value(data, self.state)
                    display_value = (
                        type2str(raw_value, data.type())
                        if self.state == DBState.humanValue and not isinstance(raw_value, str)
                        else raw_value
                    )
                values.append(str(display_value))

                # Subscribe to updates so UI refreshes when backend changes
                def make_callback(rn=rowName, cn=colName, var=data):
                    def _on_value_changed(*_):
                        self._update_cell(rn, cn, var)
                    return _on_value_changed
                try:
                    data.valueChangedSignal.connect(make_callback())
                except Exception:
                    # If signal not available, ignore
                    pass

            self.tree.insert("", "end", iid=str(rowName), text=str(rowName), values=values)

    def _update_cell(self, rowName, colName, var: ReactVar):
        try:
            if colName in ["BYTE_SIZE", "TYPE"]:
                display_value = str(var._value)
            else:
                raw_value = self._get_sync_value(var, self.state)
                display_value = (
                    type2str(raw_value, var.type())
                    if self.state == DBState.humanValue and not isinstance(raw_value, str)
                    else raw_value
                )

            col_index = list(self.df.columns).index(colName)
            values = list(self.tree.item(str(rowName), "values"))
            values[col_index] = str(display_value)
            self.tree.item(str(rowName), values=values)
        except Exception:
            pass


    # ------------------------- Editing logic ------------------------

    def _cell_info_from_event(self, event):
        """Return (row_id, col_index, col_name) for the event position, or (None, None, None)."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return None, None, None
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)  # e.g., '#1'
        if not row_id or not col_id:
            return None, None, None
        col_index = int(col_id.replace("#", "")) - 1
        col_name = self.tree["columns"][col_index]
        return row_id, col_index, col_name

    def _on_double_click_begin_edit(self, event):
        row_id, col_index, col_name = self._cell_info_from_event(event)
        if row_id is None:
            return

        rowName = row_id  # We used index as iid
        colName = col_name
        data: ReactVar = self.df.at[rowName, colName]

        # Determine if enum or text and if editable
        typeValue = data.type()
        model = getattr(data, "model", None)

        is_enum = (
            ("ENUM" in typeValue or "BIT_ENUM" in typeValue)
            and model not in {DBModel.Func, DBModel.tFunc}
            and colName not in ["BYTE_SIZE", "TYPE"]
        )

        editable_field = (
            self.state == DBState.humanValue
            or colName in ["BYTE_SIZE", "TYPE"]
            or any(x in typeValue for x in ["PACKED", "UNSIGNED", "FLOAT", "INTEGER", "DATE", "TIME"])
        ) and model not in {DBModel.Func, DBModel.tFunc}

        if not editable_field and not is_enum:
            # Not editable; do nothing
            return

        # Get bbox to place editor
        bbox = self.tree.bbox(row_id, col_name)
        if not bbox:
            return

        x, y, width, height = bbox
        # Place editor **inside the Treeview** using widget-relative coords.
        # Using absolute screen coords caused the editor to appear far from the clicked cell.
        self._destroy_editor()

        # Current display value
        raw_value = self._get_sync_value(data, self.state)
        display_value = (
            type2str(raw_value, data.type())
            if self.state == DBState.humanValue and not isinstance(raw_value, str)
            else raw_value
        )
        cur_text = str(display_value) if display_value is not None else ""

        if is_enum and self.tableName == "HART":
            items = []
            try:
                if typeValue.startswith("BIT_ENUM"):
                    idx = int(typeValue[len("BIT_ENUM"):])
                    items = list(hrt_bitEnum.get(idx, {}).values())
                elif typeValue.startswith("ENUM"):
                    idx = int(typeValue[len("ENUM"):])
                    items = list(hrt_enum.get(idx, {}).values())
            except Exception:
                items = []

            cb = ttk.Combobox(self.tree, values=items, state="readonly")
            cb.place(x=x, y=y, width=width, height=height)
            cb.set(cur_text)
            cb.focus_set()

            def commit_combo(event=None, var=data, combobox=cb):
                try:
                    var.setValue(combobox.get(), self.state)
                except Exception:
                    pass
                finally:
                    self._destroy_editor()

            cb.bind("<<ComboboxSelected>>", commit_combo)
            cb.bind("<Return>", commit_combo)
            cb.bind("<Escape>", lambda e: self._destroy_editor())
            self._editor = cb
        else:
            # Text editor
            entry = tk.Entry(self.tree)
            # Editable constraints
            if editable_field:
                entry.configure(state="normal")
                entry.configure(background="white")
            else:
                entry.configure(state="readonly")
                entry.configure(readonlybackground="#D3D3D3")

            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, cur_text)
            entry.select_range(0, tk.END)
            entry.focus_set()

            def commit_entry(event=None, var=data, e_widget=entry, _cur_text=cur_text):
                try:
                    new_text = e_widget.get()

                    # 1) Se o texto exibido NÃO mudou, não comita nada (evita PACKED_ASCII virar None).
                    if new_text == (_cur_text if _cur_text is not None else ""):
                        return

                    # 2) Se o Entry estiver readonly por qualquer motivo, ignore.
                    try:
                        if str(e_widget.cget("state")) == "readonly":
                            return
                    except Exception:
                        pass
                    
                    t_upper = (var.type() or "").upper()
                    # 3) PACKED / ASCII: gravar texto bruto (evita str2type->None)
                    if "PACKED" in t_upper or "ASCII" in t_upper:
                        # vazio => grava "" (não None)
                        var.setValue(new_text if new_text != "" else "", self.state)
                        return

                    # 4) Demais tipos: segue conversão padrão
                    var.setValue(str2type(new_text, var.type()), self.state)

                except Exception as e:
                    # Mostra o erro para facilitar debug (troque por 'pass' se preferir silencioso)
                    try:
                        messagebox.showerror("Erro", f"Falha ao aplicar valor: {e}", parent=self)
                    except Exception:
                        pass
                finally:
                    self._destroy_editor()

            # Context menu for entry
            menu = tk.Menu(entry, tearoff=0)
            menu.add_command(label="Cut", command=lambda: entry.event_generate("<<Cut>>"))
            menu.add_command(label="Copy", command=lambda: entry.event_generate("<<Copy>>"))
            menu.add_command(label="Paste", command=lambda: entry.event_generate("<<Paste>>"))
            entry.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))

            entry.bind("<Return>", commit_entry)
            entry.bind("<KP_Enter>", commit_entry)
            entry.bind("<Escape>", lambda e: self._destroy_editor())
            entry.bind("<FocusOut>", commit_entry)

            self._editor = entry

        self._editor_row_id = row_id
        self._editor_col = col_name

    def _destroy_editor(self):
        if self._editor is not None:
            try:
                self._editor.destroy()
            except Exception:
                pass
        self._editor = None
        self._editor_row_id = None
        self._editor_col = None

    # ------------------------ Context menu -------------------------

    def _on_right_click(self, event):
        row_id, col_index, col_name = self._cell_info_from_event(event)
        if row_id is None:
            return
        rowName, colName = row_id, col_name
        data: ReactVar = self.df.at[rowName, colName]

        menu = tk.Menu(self, tearoff=0)

        # --- Itens condicionais: Value / Func / Tfunc apenas para FLOAT ou UNSIGNED ---
        type_upper = (data.type() or "").upper()
        can_special = (
            colName not in ["BYTE_SIZE", "TYPE"] and
            ("FLOAT" in type_upper or "UNSIGNED" in type_upper)
        )

        if can_special:
            # Value
            def do_value():
                cellVal = data._value
                if self.state == DBState.humanValue:
                    try:
                        cellVal = type2str(cellVal, data.type())
                    except Exception:
                        pass
                val = simpledialog.askstring("Value", "Enter value:", initialvalue=str(cellVal), parent=self)
                if val is not None:
                    try:
                        data.setValue(str2type(val, data.type()), self.state)
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to set value: {e}", parent=self)

            menu.add_command(label="Value", command=do_value)

            # Func
            def do_func():
                top = tk.Toplevel(self)
                top.title("Func")
                top.transient(self.winfo_toplevel())
                top.grab_set()

                ttk.Label(top, text="Func:").pack(anchor="w", padx=8, pady=(8, 2))
                txt = tk.Text(top, width=60, height=6, wrap="word")
                txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))
                ttk.Label(top, text="Dica: use as sugestões definidas em setAutoCompleteList.", foreground="#555")\
                .pack(anchor="w", padx=8, pady=(0, 8))

                txt.insert("1.0", data.getFunc() or "")

                frm = ttk.Frame(top)
                frm.pack(fill="x", padx=8, pady=(0, 8))
                ttk.Button(frm, text="OK", command=lambda: (data.setFunc(txt.get("1.0", "end-1c")), top.destroy()))\
                .pack(side="right", padx=4)
                ttk.Button(frm, text="Cancelar", command=top.destroy).pack(side="right")

            menu.add_command(label="Func", command=do_func)

            # Tfunc
            def do_tfunc():
                # Expected format: "[num],[den],delay,input"
                tfunc = data.getTFunc() or ""
                try:
                    num_str, den_str, delay_str, input_str = map(str.strip, tfunc.split(","))
                except Exception:
                    num_str = den_str = delay_str = input_str = ""

                top = tk.Toplevel(self)
                top.title("Tfunc")
                top.transient(self.winfo_toplevel())
                top.grab_set()

                grid = ttk.Frame(top)
                grid.pack(fill="both", expand=True, padx=10, pady=10)

                ttk.Label(grid, text="Numerador [a0 a1 a2...]").grid(row=0, column=0, sticky="w")
                e_num = ttk.Entry(grid); e_num.grid(row=0, column=1, sticky="ew", padx=(8, 0))
                e_num.insert(0, num_str.strip("[]"))

                ttk.Label(grid, text="Denominador [b0 b1 b2...]").grid(row=1, column=0, sticky="w", pady=(6, 0))
                e_den = ttk.Entry(grid); e_den.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
                e_den.insert(0, den_str.strip("[]"))

                ttk.Label(grid, text="Delay").grid(row=2, column=0, sticky="w", pady=(6, 0))
                e_delay = ttk.Entry(grid); e_delay.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
                e_delay.insert(0, delay_str)

                ttk.Label(grid, text="Input (nome da variável)").grid(row=3, column=0, sticky="w", pady=(6, 0))
                t_input = tk.Text(grid, height=3, width=40, wrap="word")
                t_input.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
                t_input.insert("1.0", input_str)

                grid.columnconfigure(1, weight=1)

                btns = ttk.Frame(top); btns.pack(fill="x", padx=10, pady=(0, 10))

                def ok():
                    new_val = f'[{e_num.get()}],[{e_den.get()}],{e_delay.get()},{t_input.get("1.0", "end-1c")},'
                    try:
                        data.setTFunc(new_val)
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to set Tfunc: {e}", parent=self)
                    finally:
                        top.destroy()

                ttk.Button(btns, text="OK", command=ok).pack(side="right", padx=4)
                ttk.Button(btns, text="Cancelar", command=top.destroy).pack(side="right")

            menu.add_command(label="Tfunc", command=do_tfunc)

            menu.add_separator()

        # --- Itens padrão: Cut / Copy / Paste sempre disponíveis ---
        # Copy (texto visível da célula)
        def do_copy():
            try:
                text = self.tree.set(row_id, column=colName)
                self.clipboard_clear()
                self.clipboard_append(text)
            except Exception:
                pass

        # Paste (tenta converter para o tipo da célula)
        def do_paste():
            try:
                text = self.clipboard_get()
                t_upper = (data.type() or "").upper()
                if "PACKED" in t_upper or "ASCII" in t_upper:
                    data.setValue(text if text != "" else "", self.state)
                else:
                    data.setValue(str2type(text, data.type()), self.state)
            except Exception as e:
                messagebox.showerror("Error", f"Paste inválido: {e}", parent=self)


        # Cut = Copy + limpar valor (0 para numéricos; vazio para outros)
        def do_cut():
            do_copy()
            try:
                if any(t in type_upper for t in ["FLOAT", "UNSIGNED", "INTEGER"]):
                    data.setValue(str2type("0", data.type()), self.state)
                else:
                    data.setValue(str2type("", data.type()), self.state)
            except Exception:
                # Se não der para limpar, ao menos já copiamos
                pass

        menu.add_command(label="Cut", command=do_cut)
        menu.add_command(label="Copy", command=do_copy)
        menu.add_command(label="Paste", command=do_paste)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


    # ------------------------- Utilities ---------------------------

    def get_cell_var(self, rowName, colName) -> ReactVar:
        return self.df.at[rowName, colName]


# ------------------------ Example runner ----------------------------
if __name__ == "__main__":
    # This block is for manual testing. In your application, you'll create the frame
    # and call setBaseData(...) with your existing dbDataFrame & tableName.
    root = tk.Tk()
    root.title("DBTableWidgetTk - Example")
    root.geometry("900x500")
    info = ttk.Label(root, text="Hook this widget to your real dbDataFrame via setBaseData(db, 'TABLE').")
    info.pack(fill="x", padx=8, pady=6)
    widget = DBTableWidgetTk(root)
    widget.pack(fill="both", expand=True)
    ttk.Label(root, text="Right-click a cell for Value/Func/Tfunc. Double-click to edit.").pack(fill="x", padx=8, pady=6)
    root.mainloop()
