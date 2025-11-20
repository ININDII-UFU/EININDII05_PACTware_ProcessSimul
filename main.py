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

class MainWindowTk(tk.Tk):
    def __init__(self):
        super().__init__()
        print("🚀 Iniciando MainWindow...")

        self.title("HART/MODBUS – Tk UI")
        self.geometry("1100x650")

        # --- internal state/refs -
        self._running = False

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

        # garanta que o estado inicial dos widgets reflita “desconectado”
        self._sync_comm_widgets(disconnected=True)

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


    def _sync_comm_widgets(self, connected=False, disconnected=False):
        """Habilita/desabilita controles de acordo com o estado da comunicação."""
        # defina “running” como o seu critério de conexão atual
        running = connected or (getattr(self, "server", None) and getattr(self.server, "running", False) and not disconnected)

        # botões
        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_stop.configure(state="normal" if running else "disabled")

        # Porta Modbus (Entry) travada quando conectado
        if hasattr(self, "e_modbus"):
            self.e_modbus.configure(state="disabled" if running else "normal")

        # Porta COM (Combobox) travada quando conectado
        if hasattr(self, "cb_hart"):
            self.cb_hart.configure(state="disabled" if running else "readonly")
        if hasattr(self, "btn_refresh_hart"):
            self.btn_refresh_hart.configure(state="disabled" if running else "normal")

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
        # Porta COM (Combobox) + botão refresh
        try:
            self.cb_hart.configure(state="disabled" if disable else "readonly")
        except Exception:
            pass
        try:
            self.btn_refresh_hart.configure(state="disabled" if disable else "normal")
        except Exception:
            pass

    def _toggle_comm_inputs_modbus(self, disable: bool):
        """Habilita/desabilita os controles de entrada durante a conexão."""
        # Porta Modbus (Entry)
        try:
            self.port_entry.configure(state="disabled" if disable else "normal")
        except Exception:
            pass

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
            try:
                self.simulTf.start(True)
            except:
                pass

            self._set_main_running_visual(True)
            return

        # === STOP MODBUS ===

        # Se HART estiver rodando → para apenas Modbus
        try:
            self.servidor_thread.stop()
        except:
            pass

        self.is_modbus_running = False
        self._toggle_comm_inputs_modbus(False)

        # Se HART NÃO estiver rodando → agora sim para o simulTf
        if not self.is_hart_running:
            try:
                self.simulTf.start(False)
            except:
                pass
            self._set_main_running_visual(False)

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
            try:
                self.simulTf.start(True)
            except:
                pass

            self._set_main_running_visual(True)
            return

        # === STOP HART ===

        # Se Modbus estiver rodando → para apenas HART
        try:
            self.hart_comm.disconnect()
        except:
            pass

        self.is_hart_running = False
        self._toggle_comm_inputs_hart(False)

        # Se Modbus NÃO estiver rodando → agora sim para o simulTf
        if not self.is_modbus_running:
            try:
                self.simulTf.start(False)
            except:
                pass
            self._set_main_running_visual(False)


    def _set_main_running_visual(self, running: bool):
        self._running = running
        if running:
            self.status_var.set("Rodando")
            self.btn_start.state(["disabled"])
            self.btn_stop.state(["!disabled"])
        else:
            self.status_var.set("Parado")
            self.btn_start.state(["!disabled"])
            self.btn_stop.state(["disabled"])
            
if __name__ == "__main__":
    app = MainWindowTk()
    app.mainloop()