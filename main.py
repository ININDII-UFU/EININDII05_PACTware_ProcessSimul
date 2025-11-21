# git tag v0.0.1
# git push origin v0.0.1
"""
db_app_tk.py
------------
Tkinter main window equivalent to the PySide6 bootstrap the user provided.

It:
- creates ReactFactory (async) for ["HART", "MODBUS"]
- configures SimulTf and connects isTFuncSignal
- registers preexisting tFunc variables
- starts/stops a ModbusServer thread on demand
- offers UI controls:
    * Human/Hex view (applies to both tables)
    * Start/Stop simulation and Modbus server (with port field)
    * Notebook with two tabs (HART, MODBUS) showing DBTableWidgetTk tables
"""

from __future__ import annotations
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox
# --- project imports (expected to exist in your environment) ---
from db.db_types import DBModel, DBState
from react.react_factory import ReactFactory
from ctrl.simul_tf import SimulTf    # adjust path if different in your project
from mb.mb_server import ModbusServer  # adjust path if different in your project
from utils.safe_async import run_async
# our Tk table widget
from utils.dbtablewidget_tk import DBTableWidgetTk
# usar o seu gerenciador HART (preferível)
from hrt.hrt_comm import HrtComm
from hrt.hrt_transmitter import HrtTransmitter
from hrt.hrt_frame import HrtFrame

# --- HOTFIX: adiciona _fmt_machine_hex se a classe não tiver (monkey-patch) ---
if not hasattr(DBTableWidgetTk, "_fmt_machine_hex"):
    def _fmt_machine_hex(self, value, byte_size: int):
        try:
            if isinstance(value, (bytes, bytearray)):
                return " ".join(f"{b:02X}" for b in value)
            if isinstance(value, (list, tuple)) and all(isinstance(b, int) for b in value):
                return " ".join(f"{b:02X}" for b in value)
            if isinstance(value, int):
                width = max(1, int(byte_size))
                bs = value.to_bytes(width, byteorder="big", signed=False)
                return " ".join(f"{b:02X}" for b in bs)
            return str(value)
        except Exception:
            return str(value)
    DBTableWidgetTk._fmt_machine_hex = _fmt_machine_hex
# -------------------------------------------------------------------------------
import threading
from PIL import Image, ImageTk

def show_splash_scaled(root, image_path):
    """
    Mostra splash redimensionada para ~70% da tela,
    e retorna o objeto Toplevel para ser destruído depois.
    """
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    # Carrega a imagem
    img = Image.open(image_path)

    # Fator de escala (70% da tela)
    max_w = int(screen_w * 0.7)
    max_h = int(screen_h * 0.7)

    # Mantém proporção
    img.thumbnail((max_w, max_h))

    splash_img = ImageTk.PhotoImage(img)

    w, h = img.size
    x = (screen_w - w) // 2
    y = (screen_h - h) // 2

    splash.geometry(f"{w}x{h}+{x}+{y}")

    label = tk.Label(splash, image=splash_img)
    label.image = splash_img
    label.pack()

    return splash


class MainWindowTk(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        print("🚀 Iniciando MainWindow...")

        master.title("HART/MODBUS – Tk UI")
        master.geometry("1100x650")

        # garante que o frame ocupa a janela inteira
        self.pack(fill="both", expand=True)

        # --- internal state/refs -
        self.is_hart_running = False
        self.is_modbus_running = False

        # --- create backend ---
        print("🔄 Criando ReactFactory...")
        self.reactFactory = run_async(ReactFactory.create(["HART", "MODBUS"]))
        self.HrtTransmitter = HrtTransmitter(self.reactFactory,"HART")
        print("✅ ReactFactory criado com sucesso!")

        # --- simulator wiring ---
        print("🔄 Configurando Simulador...")
        self.simulTf = SimulTf(50)
        print("✅ Simulador configurado.")

        print("🔄 Conectando sinais de tFunc...")
        # espera que isTFuncSignal tenha um .connect(callable)
        self.reactFactory.isTFuncSignal.connect(self.simulTf.tfConnect)
        print("✅ Sinais de tFunc conectados.")

        print("🔄 Registrando variáveis com tFunc...")
        for tbl in self.reactFactory.df:
            for row in self.reactFactory.df[tbl].index:
                for col in self.reactFactory.df[tbl].columns:
                    var = self.reactFactory.df[tbl].at[row, col]
                    if getattr(var, "model", None) == DBModel.tFunc:
                        self.simulTf.tfConnect(var, True)
        print("✅ Variáveis registradas com tFunc.")

        # --- Modbus server (thread controller) ---
        print("🔄 Iniciando servidor Modbus...")
        self.servidor_thread = ModbusServer(self.reactFactory)  # não inicia ainda
        # HART communication
        self.hart_comm = HrtComm(func_read=self._on_hart_frame)

        # --- UI ---
        print("🔄 Configurando UI...")
        self._build_ui()
        print("✅ UI configurada.")

        print("🔄 Carregando tabelas...")
        self.hrtTable.setBaseData(self.reactFactory, "HART")
        self.mbTable.setBaseData(self.reactFactory, "MODBUS")
        print("✅ Tabelas carregadas.")

    # --------------------- UI construction ---------------------
    def _build_ui(self):
        # Top bar
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(side="top", fill="x")

        # Human/Hex selector dentro de um LabelFrame
        lf_view = ttk.LabelFrame(top, text="Visualização", padding=(6, 4))
        lf_view.pack(side="left", padx=(0, 10))  # continua na mesma "linha" do top

        self.view_var = tk.StringVar(value="human")
        rb_human = ttk.Radiobutton(
            lf_view,
            text="Humano",
            value="human",
            variable=self.view_var,
            command=self._on_view_change
        )
        rb_hex = ttk.Radiobutton(
            lf_view,
            text="Hex",
            value="hex",
            variable=self.view_var,
            command=self._on_view_change
        )
        rb_human.pack(side="left", padx=(4, 2))
        rb_hex.pack(side="left", padx=(0, 2))

        # spacing
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        # Modbus port + Start/Stop dentro de um painel (LabelFrame)
        lf_modbus = ttk.LabelFrame(top, text="Servidor Modbus", padding=(6, 4))
        lf_modbus.pack(side="left", padx=(0, 10))  # continua na mesma "linha" do top

        ttk.Label(lf_modbus, text="Porta TCP:").pack(side="left")
        self.port_var = tk.StringVar(value="502")
        self.port_entry = ttk.Entry(lf_modbus, width=8, textvariable=self.port_var)
        self.port_entry.pack(side="left", padx=(4, 8))

        self.btn_start_modbus = ttk.Button(lf_modbus, text="Start",
                                    command=lambda: self._startStopModbus(True))
        self.btn_stop_modbus = ttk.Button(lf_modbus, text="Stop",
                                   command=lambda: self._startStopModbus(False))
        self.btn_start_modbus.pack(side="left", padx=(0, 4))
        self.btn_stop_modbus.pack(side="left")
        
        # spacing entre Modbus e HART
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        # --- backend HART ---
        self.hart_comm = HrtComm(func_read=self._on_hart_frame)

        # --- variáveis de UI ---
        self.modbus_port_var = tk.StringVar(
            value=self.modbus_port_var.get() if hasattr(self, "modbus_port_var") else "502"
        )
        self.hart_com_var = tk.StringVar(value="")

        # ====== HART Comm dentro de um LabelFrame ======
        lf_hart = ttk.LabelFrame(top, text="Hart Comm", padding=(6, 4))
        lf_hart.pack(side="left", padx=(0, 10))

        ttk.Label(lf_hart, text="Porta Serial:").pack(side="left", padx=(0, 4))

        self.cb_hart = ttk.Combobox(
            lf_hart,
            textvariable=self.hart_com_var,
            width=10,
            state="readonly",
            values=[]
        )
        self.cb_hart.pack(side="left", padx=(0, 4))

        self.btn_refresh_hart = ttk.Button(
            lf_hart,
            text="↻",
            width=3,
            command=self._refresh_hart_ports
        )
        self.btn_refresh_hart.pack(side="left")
        self.btn_start_hart = ttk.Button(lf_hart, text="Start",
                                    command=lambda: self._startStopHart(True))
        self.btn_stop_hart = ttk.Button(lf_hart, text="Stop",
                                   command=lambda: self._startStopHart(False))
        self.btn_start_hart.pack(side="left", padx=(0, 4))
        self.btn_stop_hart.pack(side="left")

        # popula a lista de COMs e seleciona a preferida do config (se existir)
        self._refresh_hart_ports()
        self._toggle_comm_inputs_hart(False)
        self._toggle_comm_inputs_modbus(False)

        # status text
        self.status_var = tk.StringVar(value="Parado")
        ttk.Label(top, textvariable=self.status_var).pack(side="right")

        # Notebook with two tables
        nb = ttk.Notebook(self)
        nb.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        # HART tab
        tab_hart = ttk.Frame(nb)
        nb.add(tab_hart, text="HART")
        self.hrtTable = DBTableWidgetTk(tab_hart)
        self.hrtTable.pack(fill="both", expand=True)

        # MODBUS tab
        tab_mb = ttk.Frame(nb)
        nb.add(tab_mb, text="MODBUS")
        self.mbTable = DBTableWidgetTk(tab_mb)
        self.mbTable.pack(fill="both", expand=True)

    # ------------------- Callbacks & helpers -------------------
    def _on_view_change(self):
        isHuman = (self.view_var.get() == "human")
        # espelha nas duas tabelas
        self.hrtTable.changeType(isHuman)
        self.mbTable.changeType(isHuman)
        
    def _refresh_hart_ports(self):
        """Atualiza a lista de COMs usando HrtComm.available_ports."""
        try:
            ports = list(self.hart_comm.available_ports)
        except Exception:
            ports = []
        if not ports:
            ports = [f"COM{i}" for i in range(1, 33)]
        self.cb_hart["values"] = ports
        if ports and not self.hart_com_var.get():
            self.hart_com_var.set(ports[0])

    def _on_hart_frame(self, hex_str: str):
        def process_on_ui(hrt_comm):
            print(hex_str)
            frame_to_write: str = (self.HrtTransmitter.response(HrtFrame(hex_str))).frame
            if frame_to_write != "" and hrt_comm.write_frame(frame_to_write):
                print(f"Wrote frame: {frame_to_write}")
            else:
                print("Failed to write frame")
        self.after(0, process_on_ui, self.hart_comm)  # joga para a main thread do Tk
        
    def _toggle_comm_inputs_hart(self, disable: bool):
        """Habilita/desabilita os controles de entrada durante a conexão."""
        self.btn_start_hart.configure(state="disabled" if disable else "normal")
        self.btn_stop_hart.configure(state="normal" if disable else "disabled")
        # Porta COM (Combobox) + botão refresh
        self.cb_hart.configure(state="disabled" if disable else "readonly")
        self.btn_refresh_hart.configure(state="disabled" if disable else "normal")


    def _toggle_comm_inputs_modbus(self, disable: bool):
        """Habilita/desabilita os controles de entrada durante a conexão."""
        # botões
        self.btn_start_modbus.configure(state="disabled" if disable else "normal")
        self.btn_stop_modbus.configure(state="normal" if disable else "disabled")
        # Porta Modbus (Entry) travada quando conectado
        if hasattr(self, "e_modbus"):
            self.e_modbus.configure(state="disabled" if disable else "normal")
        self.port_entry.configure(state="disabled" if disable else "normal")


    def _startStopModbus(self, state: bool):
        if state:  # === START MODBUS ===
            try:
                port = int(self.port_var.get().strip())
            except ValueError:
                messagebox.showerror("Porta inválida",
                                    "Informe um número de porta válido, ex.: 5020",
                                    parent=self)
                return

            try:
                self.servidor_thread.start(port=port)
            except Exception as e:
                messagebox.showerror("Erro ao iniciar Modbus", str(e), parent=self)
                return

            self.is_modbus_running = True
            self._toggle_comm_inputs_modbus(True)
            # start simulTf sempre que iniciar Modbus
            self.simulTf.start(True)
            return

        # === STOP MODBUS ===

        # Se HART estiver rodando → para apenas Modbus
        self.servidor_thread.stop()

        self.is_modbus_running = False
        self._toggle_comm_inputs_modbus(False)

        # Se HART NÃO estiver rodando → agora sim para o simulTf
        if not self.is_hart_running:
            self.simulTf.start(False)

    def _startStopHart(self, state: bool):
        if state:  # === START HART ===
            hart_port = (self.hart_com_var.get() or "").strip()
            try:
                if hart_port:
                    self.hart_comm.port = hart_port
                ok = self.hart_comm.connect(port=hart_port, func_read=self._on_hart_frame)
            except Exception as e:
                ok = False
                err = str(e)

            if not ok:
                detail = err if 'err' in locals() else getattr(
                    getattr(self.hart_comm, "_comm_serial", None),
                    "last_error",
                    ""
                ) or ""

                messagebox.showerror(
                    "Erro ao iniciar HART",
                    f"Não foi possível abrir a porta HART {hart_port or '(config)'}.\n"
                    f"Detalhes: {detail}",
                    parent=self
                )
                return

            self.is_hart_running = True
            self._toggle_comm_inputs_hart(True)
            # start simulTf sempre que iniciar HART
            self.simulTf.start(True)
            return

        # === STOP HART ===

        # Se Modbus estiver rodando → para apenas HART
        self.hart_comm.disconnect()


        self.is_hart_running = False
        self._toggle_comm_inputs_hart(False)

        # Se Modbus NÃO estiver rodando → agora sim para o simulTf
        if not self.is_modbus_running:
            self.simulTf.start(False)
            
# --------------------- main app entry point ---------------------  
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # esconder a janela principal antes do splash

    splash_path = "assets/splash_image.png"
    splash = show_splash_scaled(root, splash_path)

    def init_app():
        # cria a UI principal (SEM mainloop)
        app = MainWindowTk(root)

        # quando terminar de montar:
        splash.destroy()
        root.deiconify()  # mostra a janela principal

    # executa montagem pesada NA THREAD PRINCIPAL (seguro!)
    root.after(200, init_app)

    root.mainloop()


