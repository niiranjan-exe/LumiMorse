# =============================================================================
#██╗      ██╗   ██╗███╗   ███╗██╗    ███╗   ███╗ ██████╗ ██████╗ ███████╗███████╗
#██║      ██║   ██║████╗ ████║██║    ████╗ ████║██╔═══██╗██╔══██╗██╔════╝██╔════╝
#██║      ██║   ██║██╔████╔██║██║    ██╔████╔██║██║   ██║██████╔╝███████╗█████╗  
#██║      ██║   ██║██║╚██╔╝██║██║    ██║╚██╔╝██║██║   ██║██╔══██╗╚════██║██╔══╝  
#███████╗ ╚██████╔╝██║ ╚═╝ ██║██║    ██║ ╚═╝ ██║╚██████╔╝██║  ██║███████║███████╗
#╚══════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝
# =============================================================================
#   LUMI MORSE  .  LASER MORSE COMMUNICATION SYSTEM  .  ARDUINO BRIDGE  v5.0
#
#   Arduino serial protocol handled here:
#     SEND  "RX\n"             -> Arduino enters receive mode
#     SEND  "TX <message>\n"   -> Arduino transmits full message via laser
#     SEND  "CAL\n"            -> Arduino runs LDR calibration routine
#
#   RECEIVE from Arduino:
#     "LASER LINK READY"       handshake on boot
#     "RX MODE"                confirmed receive mode active
#     "[TX] Sending..."        TX started on Arduino side
#     "[TX] Done"              TX finished on Arduino side
#     "CAL MODE - ..."         calibration banner
#     "CAL DONE"               calibration finished
#     "0" / "1"                raw LDR readings during CAL
#     plain chars/words        decoded morse characters during RX
# =============================================================================

import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time
import random
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
from datetime import datetime
import queue

# ── API KEY ───────────────────────────────────────────────────
API_KEY = "ABC123"

# ── MORSE TABLE ───────────────────────────────────────────────
MORSE = {
    'A':'.-',    'B':'-...',  'C':'-.-.',  'D':'-..',   'E':'.',
    'F':'..-.',  'G':'--.',   'H':'....',  'I':'..',    'J':'.---',
    'K':'-.-',   'L':'.-..',  'M':'--',    'N':'-.',    'O':'---',
    'P':'.--.',  'Q':'--.-',  'R':'.-.',   'S':'...',   'T':'-',
    'U':'..-',   'V':'...-',  'W':'.--',   'X':'-..-',  'Y':'-.--',
    'Z':'--..',
    '0':'-----', '1':'.----', '2':'..---', '3':'...--', '4':'....-',
    '5':'.....', '6':'-....', '7':'--...', '8':'---..', '9':'----.',
    '.':'.-.-.-', ',':'--..--', '?':'..--..', '!':'-.-.--',
    '/':'-..-.', '=':'-...-',  '+':'.-.-.', '-':'-....-'
}
MORSE_INV = {v: k for k, v in MORSE.items()}

# ── COLOUR PALETTE ────────────────────────────────────────────
C = {
    "bg":          "#020810",
    "panel":       "#050e1c",
    "panel2":      "#07111f",
    "border":      "#0ea5e9",
    "border_dim":  "#1e3a4a",
    "tx_accent":   "#f97316",
    "tx_dim":      "#7c3010",
    "tx_glow":     "#fbbf24",
    "rx_accent":   "#22d3ee",
    "rx_dim":      "#0c4a55",
    "rx_glow":     "#67e8f9",
    "cal_accent":  "#a78bfa",
    "cal_dim":     "#3b1f7a",
    "idle_accent": "#38bdf8",
    "green":       "#4ade80",
    "green_dim":   "#14532d",
    "red":         "#f43f5e",
    "red_dim":     "#4c0519",
    "muted":       "#1e293b",
    "muted2":      "#334155",
    "text_hi":     "#f0f9ff",
    "text_mid":    "#94a3b8",
    "text_lo":     "#475569",
    "yellow":      "#fde68a",
    "purple":      "#a78bfa",
    "pink":        "#f472b6",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# =============================================================================
#  CUSTOM WIDGETS
# =============================================================================

class NeonFrame(ctk.CTkFrame):
    """Dark glass panel with a coloured border."""
    def __init__(self, parent, color=None, **kw):
        super().__init__(parent,
                         fg_color=C["panel"],
                         border_width=1,
                         border_color=color or C["border"],
                         corner_radius=14,
                         **kw)


class PulseLabel(ctk.CTkLabel):
    """LED-style label that pulses between two colours."""
    def __init__(self, parent, col_a, col_b, speed=600, **kw):
        super().__init__(parent, **kw)
        self._ca, self._cb, self._sp = col_a, col_b, speed
        self._flip = False
        self._beat()

    def _beat(self):
        self.configure(text_color=self._cb if self._flip else self._ca)
        self._flip = not self._flip
        self.after(self._sp, self._beat)

    def set_colors(self, a, b):
        self._ca, self._cb = a, b


class OscCanvas(tk.Canvas):
    """Animated oscilloscope. Colour and amplitude change per mode."""
    def __init__(self, parent, w=760, h=80, **kw):
        super().__init__(parent, width=w, height=h,
                         bg=C["bg"], highlightthickness=0, **kw)
        self.W, self.H = w, h
        self._pts  = [h // 2] * w
        self._mode = "IDLE"
        self._alive = True
        self._loop()

    def set_mode(self, m):
        self._mode = m

    def _loop(self):
        if not self._alive:
            return
        self.delete("w")
        col, amp = {
            "TX":  (C["tx_accent"],  36),
            "RX":  (C["rx_accent"],  28),
            "CAL": (C["cal_accent"], 22),
        }.get(self._mode, (C["muted2"], 6))

        nxt = self._pts[-1] + random.randint(-5, 5)
        nxt = max(self.H // 2 - amp, min(self.H // 2 + amp, nxt))
        self._pts = self._pts[1:] + [nxt]

        coords = []
        for x, y in enumerate(self._pts):
            coords += [x, y]
        if len(coords) >= 4:
            self.create_line(coords, fill=col, width=2, smooth=True, tags="w")

        for frac in (0.25, 0.5, 0.75):
            y = int(self.H * frac)
            self.create_line(0, y, self.W, y,
                             fill=C["muted"], dash=(3, 9), tags="w")
        self.create_text(6, 4, anchor="nw", text=self._mode,
                         font=("Courier", 9, "bold"), fill=col, tags="w")
        self.after(38, self._loop)

    def destroy(self):
        self._alive = False
        super().destroy()


class MorseBar(tk.Canvas):
    """Renders morse dots and dashes as coloured blocks."""
    def __init__(self, parent, w=860, h=46, **kw):
        super().__init__(parent, width=w, height=h,
                         bg=C["panel"], highlightthickness=0, **kw)
        self.W, self.H = w, h

    def show(self, code, mode="IDLE", prog=1.0):
        self.delete("all")
        if not code:
            return
        active = C["tx_accent"] if mode == "TX" else C["rx_accent"]
        dim    = C["muted2"]
        total  = len(code)
        done   = int(total * prog)
        x = 18
        for i, sym in enumerate(code):
            col = active if i < done else dim
            if sym == '.':
                self.create_oval(x, 10, x + 16, self.H - 10,
                                 fill=col, outline=col)
                x += 26
            elif sym == '-':
                self.create_rectangle(x, 16, x + 38, self.H - 16,
                                      fill=col, outline=col)
                x += 48


class HexRain(tk.Canvas):
    """Scrolling hex-digit matrix for the sidebar background."""
    def __init__(self, parent, w=248, h=800, **kw):
        super().__init__(parent, width=w, height=h,
                         bg=C["bg"], highlightthickness=0, **kw)
        self.W, self.H = w, h
        cols = w // 14
        self._streams = [
            {"x":    i * 14 + 7,
             "y":    random.randint(-400, 0),
             "spd":  random.uniform(1.2, 4.2),
             "chars":[format(random.randint(0, 255), '02X') for _ in range(32)],
             "head": 0}
            for i in range(cols)
        ]
        self._alive = True
        self._tick()

    def _tick(self):
        if not self._alive:
            return
        self.delete("m")
        for s in self._streams:
            for j in range(16):
                y = s["y"] - j * 13
                if not (0 <= y <= self.H):
                    continue
                frac = max(0.0, 1 - j / 16)
                g    = int(frac * 55)
                col  = f"#{g:02x}{min(255, g + 40):02x}{g:02x}"
                ch   = s["chars"][(s["head"] + j) % len(s["chars"])]
                self.create_text(s["x"], y, text=ch,
                                 font=("Courier", 8), fill=col, tags="m")
            s["y"] += s["spd"]
            if s["y"] > self.H + 220:
                s["y"]   = random.randint(-400, -60)
                s["spd"] = random.uniform(1.2, 4.2)
            s["head"] = (s["head"] + 1) % len(s["chars"])
        self.after(55, self._tick)

    def destroy(self):
        self._alive = False
        super().destroy()


class CalibrationMeter(tk.Canvas):
    """Bar chart that shows live 0/1 LDR readings during CAL mode."""
    def __init__(self, parent, w=862, h=60, **kw):
        super().__init__(parent, width=w, height=h,
                         bg=C["panel2"], highlightthickness=0, **kw)
        self.W, self.H = w, h
        self._readings = []

    def push(self, val: int):
        self._readings.append(val)
        if len(self._readings) > 100:
            self._readings = self._readings[-100:]
        self._draw()

    def _draw(self):
        self.delete("all")
        if not self._readings:
            return
        n  = len(self._readings)
        bw = self.W / max(n, 1)
        for i, v in enumerate(self._readings):
            col = C["green"] if v == 0 else C["red"]
            x0  = i * bw
            y0  = self.H * (1 - v) * 0.75 + 4
            self.create_rectangle(x0, y0, x0 + max(bw - 1, 1), self.H - 4,
                                  fill=col, outline="")
        latest = self._readings[-1]
        desc   = "LASER ON" if latest == 0 else "LASER OFF"
        self.create_text(6, 4, anchor="nw",
                         text=f"LDR  0=LASER DETECTED  1=DARK   latest={latest} ({desc})",
                         font=("Courier", 8), fill=C["text_mid"])


# =============================================================================
#  COLOUR LOG WIDGET
# =============================================================================

LOG_TAGS = {
    "INFO": C["text_mid"],
    "TX":   C["tx_accent"],
    "RX":   C["rx_accent"],
    "CAL":  C["cal_accent"],
    "OK":   C["green"],
    "ERR":  C["red"],
    "WARN": C["yellow"],
    "SYS":  C["purple"],
    "DATA": C["rx_glow"],
}


class ColorLog(tk.Text):
    """Multi-colour timestamped log built on a plain tk.Text."""
    def __init__(self, parent, **kw):
        kw.setdefault("bg",               C["bg"])
        kw.setdefault("fg",               C["text_hi"])
        kw.setdefault("font",             ("Courier New", 10))
        kw.setdefault("relief",           "flat")
        kw.setdefault("insertbackground", C["text_hi"])
        kw.setdefault("selectbackground", C["muted2"])
        kw.setdefault("padx", 8)
        kw.setdefault("pady", 4)
        super().__init__(parent, state="disabled", **kw)
        for tag, col in LOG_TAGS.items():
            self.tag_config(tag, foreground=col)
        self.tag_config("TS",   foreground=C["text_lo"])
        self.tag_config("BOLD", font=("Courier New", 10, "bold"))

    def append(self, level: str, text: str):
        ts  = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        tag = level if level in LOG_TAGS else "INFO"
        self.configure(state="normal")
        self.insert("end", f"[{ts}] ", "TS")
        self.insert("end", f"[{level:<4}] ", (tag, "BOLD"))
        self.insert("end", text + "\n", tag)
        self.configure(state="disabled")
        self.see("end")

    def clear(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")

    def dump(self) -> str:
        return self.get("1.0", "end")


# =============================================================================
#  MAIN APPLICATION
# =============================================================================

class LaserMorseHUD(ctk.CTk):

    # ── INIT ──────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.title("LUMI MORSE -  LASER MORSE COMMUNICATION SYSTEM  v5.0")
        self.geometry("1200x760")
        self.resizable(True, True)
        self.state("zoomed")
        self.configure(fg_color=C["bg"])

        # application state
        self.ser           = None
        self.connected     = False
        self.mode          = "IDLE"
        self._rx_alive     = False
        self._rx_thread    = None
        self.serial_queue  = queue.Queue()

        # session counters
        self.stat_tx_chars = 0
        self.stat_rx_chars = 0
        self.stat_errors   = 0
        self.stat_messages = 0

        # runtime buffers
        self.rx_message    = ""
        self._tx_pending   = ""

        # UI variables
        self.port_var  = tk.StringVar(value="")
        self.baud_var  = tk.StringVar(value="9600")
        self._ports    = self._scan_ports()
        if self._ports:
            self.port_var.set(self._ports[0])

        self._build_ui()
        self._poll_queue()
        self._tick_clock()
        self._tick_stats()

    # ── PORT SCAN ─────────────────────────────────────────────
    def _scan_ports(self):
        found = [p.device for p in serial.tools.list_ports.comports()]
        return found if found else ["No Ports"]

    def _refresh_ports(self):
        ports = self._scan_ports()
        self.port_menu.configure(values=ports)
        self.port_var.set(ports[0])
        self._log("SYS", "Port list refreshed.")

    # =========================================================
    #  UI CONSTRUCTION
    # =========================================================

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=230)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    # ─── SIDEBAR ──────────────────────────────────────────────
    def _build_sidebar(self):
        sb = NeonFrame(self, color=C["border_dim"], width=230)
        sb.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")
        sb.grid_propagate(False)

        # scrolling hex rain background
        self._rain = HexRain(sb, w=228, h=760)
        self._rain.place(x=0, y=0)

        # overlay so widgets sit above rain
        ov = ctk.CTkFrame(sb, fg_color="transparent")
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)

        # brand
        ctk.CTkLabel(ov, text="LUMI MORSE",
                     font=("Courier New", 19, "bold"),
                     text_color=C["idle_accent"]).pack(padx=14, pady=(16, 2), anchor="w")
        ctk.CTkLabel(ov, text="ARDUINO BRIDGE  v5.0",
                     font=("Courier New", 8),
                     text_color=C["text_lo"]).pack(padx=14, anchor="w")
        self._div(ov)

        # live clock
        self.clock_lbl = ctk.CTkLabel(ov, text="00:00:00",
                                       font=("Courier New", 19, "bold"),
                                       text_color=C["yellow"])
        self.clock_lbl.pack(pady=(4, 0))
        self.date_lbl = ctk.CTkLabel(ov, text="",
                                      font=("Courier New", 9),
                                      text_color=C["text_lo"])
        self.date_lbl.pack()
        self._div(ov)

        # api key
        self._sb_lbl(ov, "API KEY")
        self.api_entry = ctk.CTkEntry(ov,
                                       placeholder_text="Enter key...",
                                       show="*", width=200,
                                       font=("Courier New", 11),
                                       fg_color=C["panel2"],
                                       border_color=C["border_dim"],
                                       text_color=C["text_hi"])
        self.api_entry.pack(padx=14, pady=(2, 6))

        # serial port
        self._sb_lbl(ov, "SERIAL PORT")
        pr = ctk.CTkFrame(ov, fg_color="transparent")
        pr.pack(padx=14, fill="x")
        self.port_menu = ctk.CTkOptionMenu(
            pr, variable=self.port_var, values=self._ports, width=160,
            font=("Courier New", 10), fg_color=C["panel2"],
            button_color=C["muted"], button_hover_color=C["border"])
        self.port_menu.pack(side="left")
        ctk.CTkButton(pr, text="R", width=30, height=28,
                      font=("Courier New", 11, "bold"),
                      fg_color=C["muted"], hover_color=C["border_dim"],
                      command=self._refresh_ports).pack(side="left", padx=4)

        # baud rate
        self._sb_lbl(ov, "BAUD RATE")
        self.baud_menu = ctk.CTkOptionMenu(
            ov, variable=self.baud_var,
            values=["1200", "2400", "4800", "9600",
                    "19200", "38400", "57600", "115200"],
            width=200, font=("Courier New", 10),
            fg_color=C["panel2"],
            button_color=C["muted"], button_hover_color=C["border"])
        self.baud_menu.pack(padx=14, pady=(2, 6))

        # connect/disconnect
        self.conn_btn = ctk.CTkButton(
            ov, text="CONNECT", width=200, height=36,
            font=("Courier New", 12, "bold"),
            fg_color=C["panel2"], border_width=1,
            border_color=C["border"], hover_color="#0c2a3e",
            command=self._toggle_connect)
        self.conn_btn.pack(padx=14, pady=6)

        # LED status
        led_row = ctk.CTkFrame(ov, fg_color="transparent")
        led_row.pack(pady=2)
        self.led = PulseLabel(led_row,
                              col_a=C["red"], col_b="#ff7a7a", speed=700,
                              text="*", font=("Arial", 26, "bold"))
        self.led.pack(side="left")
        self.led_lbl = ctk.CTkLabel(led_row, text="OFFLINE",
                                     font=("Courier New", 12, "bold"),
                                     text_color=C["red"])
        self.led_lbl.pack(side="left", padx=6)
        self._div(ov)

        # mode buttons
        self._sb_lbl(ov, "OPERATION MODE")
        self.tx_btn = ctk.CTkButton(
            ov, text="TX MODE", width=200, height=36,
            font=("Courier New", 12, "bold"),
            fg_color=C["tx_dim"], border_width=1,
            border_color=C["tx_accent"], text_color=C["tx_accent"],
            hover_color=C["tx_accent"], command=self._do_tx)
        self.tx_btn.pack(padx=14, pady=3)

        self.rx_btn = ctk.CTkButton(
            ov, text="RX MODE", width=200, height=36,
            font=("Courier New", 12, "bold"),
            fg_color=C["rx_dim"], border_width=1,
            border_color=C["rx_accent"], text_color=C["rx_accent"],
            hover_color=C["rx_accent"], command=self._do_rx)
        self.rx_btn.pack(padx=14, pady=3)

        self.cal_btn = ctk.CTkButton(
            ov, text="CALIBRATE", width=200, height=30,
            font=("Courier New", 11, "bold"),
            fg_color=C["cal_dim"], border_width=1,
            border_color=C["cal_accent"], text_color=C["cal_accent"],
            hover_color=C["cal_accent"], command=self._do_cal)
        self.cal_btn.pack(padx=14, pady=3)

        ctk.CTkButton(
            ov, text="IDLE", width=200, height=26,
            font=("Courier New", 10), fg_color=C["muted"],
            hover_color=C["muted2"], text_color=C["text_lo"],
            command=self._do_idle).pack(padx=14, pady=3)

        self._div(ov)

        # session stats
        self._sb_lbl(ov, "SESSION STATS")
        sf = NeonFrame(ov, color=C["muted"], width=200)
        sf.pack(padx=14, pady=4)
        self._stx  = self._stat_row(sf, "TX CHARS",  C["tx_accent"])
        self._srx  = self._stat_row(sf, "RX CHARS",  C["rx_accent"])
        self._serr = self._stat_row(sf, "ERRORS",    C["red"])
        self._smsg = self._stat_row(sf, "MESSAGES",  C["green"])

    def _sb_lbl(self, parent, text):
        ctk.CTkLabel(parent, text=text,
                     font=("Courier New", 9, "bold"),
                     text_color=C["text_lo"]).pack(anchor="w", padx=14, pady=(6, 0))

    def _stat_row(self, parent, label, col):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label,
                     font=("Courier New", 9),
                     text_color=C["text_lo"]).pack(side="left")
        lbl = ctk.CTkLabel(row, text="0",
                            font=("Courier New", 11, "bold"),
                            text_color=col)
        lbl.pack(side="right")
        return lbl

    def _div(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color=C["muted"],
                     corner_radius=0).pack(fill="x", padx=12, pady=8)

    # ─── MAIN PANEL ───────────────────────────────────────────
    def _build_main(self):
        mp = NeonFrame(self)
        mp.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")

        # banner
        self.banner = ctk.CTkLabel(mp, text="LUMI MORSE  -  SYSTEM IDLE",
                                    font=("Courier New", 26, "bold"),
                                    text_color=C["idle_accent"])
        self.banner.pack(pady=(16, 2))
        self.sub_lbl = ctk.CTkLabel(mp,
                                     text="Connect to Arduino and choose a mode.",
                                     font=("Courier New", 11),
                                     text_color=C["text_lo"])
        self.sub_lbl.pack()

        # big character + info
        char_row = ctk.CTkFrame(mp, fg_color="transparent")
        char_row.pack(pady=(8, 0))

        self.big_char = ctk.CTkLabel(char_row, text="?",
                                      font=("Courier New", 86, "bold"),
                                      text_color=C["idle_accent"])
        self.big_char.pack(side="left", padx=(30, 8))

        info_col = ctk.CTkFrame(char_row, fg_color="transparent")
        info_col.pack(side="left", anchor="center")

        ctk.CTkLabel(info_col, text="MORSE CODE",
                     font=("Courier New", 9, "bold"),
                     text_color=C["text_lo"]).pack(anchor="w")
        self.morse_lbl = ctk.CTkLabel(info_col, text="",
                                       font=("Courier New", 20, "bold"),
                                       text_color=C["yellow"])
        self.morse_lbl.pack(anchor="w")

        ctk.CTkLabel(info_col, text="DECODED TEXT",
                     font=("Courier New", 9, "bold"),
                     text_color=C["text_lo"]).pack(anchor="w", pady=(12, 0))
        self.decoded_lbl = ctk.CTkLabel(info_col, text="--",
                                         font=("Courier New", 16, "bold"),
                                         text_color=C["text_hi"],
                                         wraplength=380, justify="left")
        self.decoded_lbl.pack(anchor="w")

        # morse dot/dash visualiser
        self.morse_bar = MorseBar(mp, w=760, h=40)
        self.morse_bar.pack(pady=(4, 2))

        # progress bar
        pb_row = ctk.CTkFrame(mp, fg_color="transparent")
        pb_row.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(pb_row, text="PROGRESS",
                     font=("Courier New", 9), text_color=C["text_lo"]).pack(side="left", padx=4)
        self.progress = ctk.CTkProgressBar(pb_row, width=600, height=8,
                                            progress_color=C["idle_accent"],
                                            fg_color=C["muted"], corner_radius=4)
        self.progress.set(0)
        self.progress.pack(side="left", padx=8)
        self.pct_lbl = ctk.CTkLabel(pb_row, text="--",
                                     font=("Courier New", 10),
                                     text_color=C["text_lo"])
        self.pct_lbl.pack(side="left")

        # oscilloscope
        osc_wrap = NeonFrame(mp, color=C["muted"])
        osc_wrap.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(osc_wrap, text="SIGNAL  .  OSCILLOSCOPE",
                     font=("Courier New", 8, "bold"),
                     text_color=C["text_lo"]).pack(anchor="w", padx=10, pady=(4, 0))
        self.osc = OscCanvas(osc_wrap, w=760, h=68)
        self.osc.pack(padx=6, pady=(0, 6))

        # calibration meter (hidden until CAL mode)
        self.cal_wrap = NeonFrame(mp, color=C["cal_accent"])
        ctk.CTkLabel(self.cal_wrap,
                     text="LDR CALIBRATION  .  LIVE SENSOR READINGS",
                     font=("Courier New", 8, "bold"),
                     text_color=C["cal_accent"]).pack(anchor="w", padx=10, pady=(4, 0))
        self.cal_meter = CalibrationMeter(self.cal_wrap, w=760, h=52)
        self.cal_meter.pack(padx=6, pady=(0, 6))
        # cal_wrap is NOT packed yet — shown only during CAL

        # ── received / sent message box (BIG) ──
        msg_wrap = NeonFrame(mp, color=C["rx_accent"])
        msg_wrap.pack(fill="x", padx=16, pady=4)

        msg_hdr = ctk.CTkFrame(msg_wrap, fg_color="transparent")
        msg_hdr.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(msg_hdr, text="LUMI MORSE  .  MESSAGE BUFFER",
                     font=("Courier New", 9, "bold"),
                     text_color=C["rx_accent"]).pack(side="left")
        ctk.CTkButton(msg_hdr, text="CLEAR", width=56, height=20,
                      font=("Courier New", 8, "bold"),
                      fg_color=C["muted"], hover_color=C["muted2"],
                      command=self._clear_message).pack(side="right", padx=2)
        ctk.CTkButton(msg_hdr, text="COPY", width=50, height=20,
                      font=("Courier New", 8, "bold"),
                      fg_color=C["muted"], hover_color=C["muted2"],
                      command=self._copy_message).pack(side="right", padx=2)

        self.msg_box = tk.Text(
            msg_wrap,
            height=9,
            bg=C["panel2"], fg=C["text_hi"],
            font=("Courier New", 13, "bold"),
            relief="flat", wrap="word",
            insertbackground=C["rx_accent"],
            selectbackground=C["muted2"],
            padx=10, pady=8,
            state="disabled"
        )
        msg_sb = tk.Scrollbar(msg_wrap, orient="vertical",
                              command=self.msg_box.yview,
                              bg=C["muted"], troughcolor=C["panel2"], width=8)
        self.msg_box.configure(yscrollcommand=msg_sb.set)
        msg_sb.pack(side="right", fill="y", pady=(0, 6))
        self.msg_box.pack(fill="x", padx=(8, 0), pady=(0, 8))

        # log area
        log_wrap = ctk.CTkFrame(mp, fg_color="transparent")
        log_wrap.pack(fill="both", expand=True, padx=16, pady=(4, 4))

        log_hdr = ctk.CTkFrame(log_wrap, fg_color="transparent")
        log_hdr.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(log_hdr, text="SYSTEM LOG  .  ARDUINO SERIAL BRIDGE",
                     font=("Courier New", 9, "bold"),
                     text_color=C["text_lo"]).pack(side="left")
        # colour legend
        for tag, col in [("TX", C["tx_accent"]), ("RX", C["rx_accent"]),
                          ("CAL", C["cal_accent"]), ("ERR", C["red"]),
                          ("OK", C["green"]), ("DATA", C["rx_glow"])]:
            ctk.CTkButton(log_hdr, text=tag, width=40, height=20,
                          font=("Courier New", 8, "bold"),
                          fg_color="transparent", border_width=1,
                          border_color=col, text_color=col,
                          hover_color=C["muted"],
                          state="disabled").pack(side="right", padx=2)

        log_box = ctk.CTkFrame(log_wrap, fg_color=C["bg"],
                                border_width=1, border_color=C["muted"],
                                corner_radius=8)
        log_box.pack(fill="both", expand=True)

        self.log = ColorLog(log_box, height=6)
        sb_y = tk.Scrollbar(log_box, orient="vertical",
                             command=self.log.yview,
                             bg=C["muted"], troughcolor=C["bg"], width=10)
        self.log.configure(yscrollcommand=sb_y.set)
        sb_y.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        # bottom toolbar
        tb = ctk.CTkFrame(mp, fg_color="transparent")
        tb.pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkButton(tb, text="SEND MESSAGE",
                      font=("Courier New", 12, "bold"),
                      fg_color=C["tx_dim"], border_width=1,
                      border_color=C["tx_accent"], text_color=C["tx_accent"],
                      hover_color=C["tx_accent"], height=34,
                      command=self._do_tx).pack(side="left", padx=4)

        ctk.CTkButton(tb, text="START RX",
                      font=("Courier New", 12, "bold"),
                      fg_color=C["rx_dim"], border_width=1,
                      border_color=C["rx_accent"], text_color=C["rx_accent"],
                      hover_color=C["rx_accent"], height=34,
                      command=self._do_rx).pack(side="left", padx=4)

        ctk.CTkButton(tb, text="CALIBRATE",
                      font=("Courier New", 12, "bold"),
                      fg_color=C["cal_dim"], border_width=1,
                      border_color=C["cal_accent"], text_color=C["cal_accent"],
                      hover_color=C["cal_accent"], height=34,
                      command=self._do_cal).pack(side="left", padx=4)

        ctk.CTkButton(tb, text="CLEAR LOG",
                      font=("Courier New", 11),
                      fg_color=C["muted"], hover_color=C["muted2"],
                      height=34, command=self._clear_log).pack(side="left", padx=4)

        ctk.CTkButton(tb, text="EXPORT LOG",
                      font=("Courier New", 11),
                      fg_color="transparent", border_width=1,
                      border_color=C["purple"], text_color=C["purple"],
                      hover_color=C["muted"], height=34,
                      command=self._export_log).pack(side="right", padx=4)

        ctk.CTkButton(tb, text="EXPORT MSG",
                      font=("Courier New", 11),
                      fg_color="transparent", border_width=1,
                      border_color=C["green"], text_color=C["green"],
                      hover_color=C["muted"], height=34,
                      command=self._export_message).pack(side="right", padx=4)

    # =========================================================
    #  SERIAL  CONNECT / DISCONNECT
    # =========================================================

    def _toggle_connect(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        if self.api_entry.get() != API_KEY:
            messagebox.showerror("Auth Error", "Invalid API Key - Access Denied")
            self.stat_errors += 1
            return

        port = self.port_var.get()
        baud = int(self.baud_var.get())

        if port in ("", "No Ports"):
            messagebox.showerror("No Port", "Select a valid COM port first.")
            return

        try:
            self.ser = serial.Serial(port, baud, timeout=0.05)
            # Arduino resets on DTR -- wait for it to boot
            time.sleep(2.0)
            self.ser.reset_input_buffer()
            self.connected = True

            self.conn_btn.configure(text="DISCONNECT",
                                    fg_color=C["red_dim"],
                                    border_color=C["red"])
            self.led.set_colors(C["green"], "#86efac")
            self.led_lbl.configure(text="ONLINE", text_color=C["green"])
            self._log("OK", f"Connected  {port}  @{baud} baud")
            self._log("SYS", "Waiting for Arduino handshake (LASER LINK READY)...")

            # start background reader thread
            self._rx_alive  = True
            self._rx_thread = threading.Thread(
                target=self._serial_reader, daemon=True)
            self._rx_thread.start()

        except Exception as ex:
            self.stat_errors += 1
            messagebox.showerror("Connection Error", str(ex))
            self._log("ERR", str(ex))

    def _disconnect(self):
        self._rx_alive = False
        self.mode      = "IDLE"
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.ser       = None
        self.connected = False

        self.conn_btn.configure(text="CONNECT",
                                fg_color=C["panel2"],
                                border_color=C["border"])
        self.led.set_colors(C["red"], "#ff7a7a")
        self.led_lbl.configure(text="OFFLINE", text_color=C["red"])
        self._apply_idle_theme()
        self._log("SYS", "Disconnected from serial port.")

    def _send_raw(self, cmd: str):
        """Write a command string to Arduino over serial."""
        if not (self.ser and self.ser.is_open):
            self._log("ERR", f"Not connected -- cannot send: {repr(cmd)}")
            self.stat_errors += 1
            return
        try:
            self.ser.write((cmd + "\n").encode("utf-8"))
            self._log("SYS", f"SENT: {repr(cmd)}")
        except Exception as ex:
            self._log("ERR", f"Write failed: {ex}")
            self.stat_errors += 1

    # =========================================================
    #  BACKGROUND SERIAL READER  (daemon thread)
    # =========================================================

    def _serial_reader(self):
        """Reads lines from Arduino indefinitely, queues them."""
        while self._rx_alive:
            if not (self.ser and self.ser.is_open):
                break
            try:
                raw = self.ser.readline()
                if raw:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        self.serial_queue.put(line)
            except serial.SerialException as ex:
                self.serial_queue.put(f"__ERR__{ex}")
                break
            except Exception:
                pass
            time.sleep(0.005)
        self._rx_alive = False

    # ── queue drain (runs in tkinter thread every 40 ms) ──────
    def _poll_queue(self):
        try:
            while True:
                line = self.serial_queue.get_nowait()
                self._dispatch(line)
        except queue.Empty:
            pass
        self.after(40, self._poll_queue)

    def _dispatch(self, line: str):
        """
        Route every Arduino serial line to the correct handler.
        This is the core of the Arduino integration.
        """

        # reader thread error
        if line.startswith("__ERR__"):
            self._log("ERR", "Serial error: " + line[7:])
            self.stat_errors += 1
            self._disconnect()
            return

        # always echo raw to log
        self._log("DATA", line)

        # ── HANDSHAKE ──────────────────────────────────────────
        if "LASER LINK READY" in line:
            self._log("OK", "Arduino handshake received: LASER LINK READY")
            self.sub_lbl.configure(
                text="Arduino online. Select TX or RX mode to begin.")
            return

        # ── TX FEEDBACK ────────────────────────────────────────
        if "[TX] Sending" in line:
            self._log("TX", "Arduino laser TX started...")
            self.sub_lbl.configure(text="Arduino transmitting via laser...")
            return

        if "[TX] Done" in line:
            self._log("TX", "Arduino laser TX complete.")
            self.stat_messages += 1
            self.progress.set(1.0)
            self.pct_lbl.configure(text="100%")
            self.banner.configure(text="LUMI MORSE  -  TX COMPLETE")
            self.after(3000, self._do_idle)
            return

        # ── RX CONFIRMED ───────────────────────────────────────
        if line == "RX MODE":
            self._log("RX", "Arduino is now in RX mode. Listening for laser pulses...")
            self.sub_lbl.configure(text="Listening for incoming laser morse code...")
            return

        # ── CALIBRATION EVENTS ─────────────────────────────────
        if "CAL MODE" in line:
            self._log("CAL", line)
            # show the calibration meter panel
            try:
                self.cal_wrap.pack(fill="x", padx=16, pady=4)
            except Exception:
                pass
            return

        if "CAL DONE" in line:
            self._log("CAL", "Calibration routine complete.")
            self.after(2500, lambda: self.cal_wrap.pack_forget())
            self.after(3000, self._do_idle)
            return

        # ── RAW LDR READINGS during CAL ────────────────────────
        if self.mode == "CAL" and line in ("0", "1"):
            self.cal_meter.push(int(line))
            return

        # ── DECODED CHARACTERS during RX ───────────────────────
        # Arduino prints chars/words directly to Serial during receiveLoop()
        if self.mode == "RX":
            added = False
            for ch in line:
                if ch.isalnum() or ch in " .,?!/":
                    self.rx_message += ch
                    self.stat_rx_chars += 1
                    added = True
                    code = MORSE.get(ch.upper(), "")
                    self.big_char.configure(text=ch.upper() if ch != " " else "SPC")
                    self.morse_lbl.configure(text=" ".join(code) if code else "")
                    if code:
                        self.morse_bar.show(code, "RX", 1.0)

            if added:
                # show the last 80 chars of accumulated message
                disp = self.rx_message[-80:]
                self.decoded_lbl.configure(text=disp)
                self._msg_box_set(self.rx_message)

    # =========================================================
    #  OPERATION MODES
    # =========================================================

    # ── TX ────────────────────────────────────────────────────
    def _tx_dialog(self):
        """Full-screen styled TX message input dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("LUMI MORSE   -  TRANSMIT MESSAGE")
        dialog.configure(bg=C["bg"])
        dialog.grab_set()

        # ── maximise on open ──
        dialog.state("zoomed")          # Windows maximise
        dialog.update_idletasks()

        result = [None]

        # ── header ──
        hdr = tk.Frame(dialog, bg=C["tx_dim"], pady=0)
        hdr.pack(fill="x")

        tk.Label(hdr,
                 text="◈  LUMI MORSE  —  TX MESSAGE COMPOSER",
                 font=("Courier New", 22, "bold"),
                 bg=C["tx_dim"], fg=C["tx_accent"]).pack(side="left", padx=30, pady=18)

        tk.Label(hdr,
                 text="Ctrl+Enter to transmit  ·  Esc to cancel",
                 font=("Courier New", 11),
                 bg=C["tx_dim"], fg=C["tx_glow"]).pack(side="right", padx=30)

        # ── morse preview strip (top) ──
        preview_bar = tk.Frame(dialog, bg=C["panel"], height=2)
        preview_bar.pack(fill="x")
        self._dlg_preview = tk.Label(
            dialog, text="Start typing to see morse preview…",
            font=("Courier New", 13), bg=C["panel2"],
            fg=C["yellow"], anchor="w", padx=20, pady=6)
        self._dlg_preview.pack(fill="x", padx=0)

        # ── tip row ──
        tk.Label(dialog,
                 text="  Supports  A–Z  ·  0–9  ·  Space  ·  . , ? ! / = + -",
                 font=("Courier New", 10),
                 bg=C["bg"], fg=C["text_lo"]).pack(anchor="w", padx=24, pady=(12, 4))

        # ── big text area ──
        txt_frame = tk.Frame(dialog, bg=C["border"], bd=1)
        txt_frame.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        txt = tk.Text(
            txt_frame,
            bg=C["panel2"], fg=C["text_hi"],
            font=("Courier New", 22, "bold"),
            relief="flat", wrap="word",
            insertbackground=C["tx_accent"],
            insertwidth=3,
            selectbackground=C["tx_dim"],
            selectforeground=C["tx_glow"],
            padx=30, pady=24,
            undo=True)
        sb = tk.Scrollbar(txt_frame, orient="vertical",
                          command=txt.yview,
                          bg=C["muted"], troughcolor=C["panel2"], width=12)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.focus_set()

        # ── character counter ──
        char_lbl = tk.Label(dialog, text="0 characters  ·  0 morse symbols",
                            font=("Courier New", 10),
                            bg=C["bg"], fg=C["text_lo"], anchor="e")
        char_lbl.pack(fill="x", padx=28, pady=(0, 4))

        # ── live preview + counter on every keystroke ──
        def _on_key(event=None):
            raw = txt.get("1.0", "end").strip().upper()
            # morse preview — first 12 chars to avoid overflow
            preview = ""
            for ch in raw[:12]:
                if ch == " ":
                    preview += "  /  "
                else:
                    preview += MORSE.get(ch, "?") + "   "
            if len(raw) > 12:
                preview += f"… (+{len(raw)-12} more chars)"
            self._dlg_preview.configure(
                text=preview if preview else "Start typing to see morse preview…")

            # char counter
            symbols = sum(len(MORSE.get(c, "")) for c in raw if c != " ")
            char_lbl.configure(
                text=f"{len(raw)} characters  ·  {symbols} morse symbols")

        txt.bind("<KeyRelease>", _on_key)

        # ── buttons ──
        btn_row = tk.Frame(dialog, bg=C["bg"])
        btn_row.pack(fill="x", padx=24, pady=(0, 24))

        def confirm(event=None):
            val = txt.get("1.0", "end").strip()
            if val:
                result[0] = val
            dialog.destroy()

        def cancel(event=None):
            dialog.destroy()

        # TRANSMIT button
        tx_btn = tk.Button(
            btn_row, text="▶  TRANSMIT",
            font=("Courier New", 15, "bold"),
            bg=C["tx_dim"], fg=C["tx_accent"],
            activebackground=C["tx_accent"], activeforeground="#000",
            relief="flat", padx=30, pady=12,
            cursor="hand2", command=confirm)
        tx_btn.pack(side="left", padx=(0, 12))

        # CLEAR button
        tk.Button(
            btn_row, text="⌫  CLEAR",
            font=("Courier New", 13),
            bg=C["muted"], fg=C["text_mid"],
            activebackground=C["muted2"], activeforeground=C["text_hi"],
            relief="flat", padx=20, pady=12,
            cursor="hand2",
            command=lambda: (txt.delete("1.0", "end"), _on_key())
        ).pack(side="left", padx=(0, 12))

        # CANCEL button
        tk.Button(
            btn_row, text="✕  CANCEL",
            font=("Courier New", 13),
            bg=C["red_dim"], fg=C["red"],
            activebackground=C["red"], activeforeground="#000",
            relief="flat", padx=20, pady=12,
            cursor="hand2", command=cancel
        ).pack(side="left")

        # keyboard shortcuts
        txt.bind("<Control-Return>", confirm)
        dialog.bind("<Escape>", cancel)

        dialog.wait_window()
        return result[0]

    def _do_tx(self):
        if not self.connected:
            messagebox.showwarning("Not Connected", "Connect to Arduino first.")
            return

        msg = self._tx_dialog()
        if not msg:
            return

        msg = msg.upper().strip()
        self._tx_pending = msg
        self.mode = "TX"
        self.rx_message = ""
        self.osc.set_mode("TX")
        self._apply_tx_theme(msg)

        # Send the single TX command -- Arduino handles the rest
        self._send_raw(f"TX {msg}")
        self._log("TX", f'Transmitting: "{msg}"  ({len(msg)} chars)')

        # Animate progress bar locally to reflect estimated Arduino timing
        threading.Thread(target=self._tx_anim, args=(msg,), daemon=True).start()

    def _tx_anim(self, msg: str):
        """
        Mimics Arduino timing locally so the progress bar feels live.
        Arduino: DOT=250ms, DASH=750ms, inter-symbol gap=DOT, letter gap=DOT*3
        """
        DOT = 0.250
        DASH = DOT * 3
        GAP  = DOT
        LGAP = DOT * 3
        WGAP = DOT * 7

        # estimate total duration
        total = 0.0
        for ch in msg:
            if ch == ' ':
                total += WGAP
            else:
                code = MORSE.get(ch, "")
                for s in code:
                    total += (DASH if s == '-' else DOT) + GAP
                total += LGAP

        elapsed = 0.0
        for ch in msg:
            if self.mode != "TX":
                break
            if ch == ' ':
                elapsed += WGAP
                self.after(0, self.big_char.configure, {"text": "SPC"})
                self.after(0, self.morse_lbl.configure, {"text": "..."})
                time.sleep(WGAP)
                continue

            code = MORSE.get(ch, "")
            if not code:
                continue

            self.after(0, self.big_char.configure, {"text": ch})
            self.after(0, self.morse_lbl.configure, {"text": " ".join(code)})
            self.after(0, self.decoded_lbl.configure, {"text": f"Sending: {ch}"})
            self.after(0, self.morse_bar.show, code, "TX", 0.0)

            nsyms = len(code)
            for si, sym in enumerate(code):
                dur = DASH if sym == '-' else DOT
                elapsed += dur + GAP
                self.after(0, self.morse_bar.show, code, "TX", (si + 1) / nsyms)
                pct = min(elapsed / max(total, 0.001), 0.99)
                self.after(0, self.progress.set, pct)
                self.after(0, self.pct_lbl.configure, {"text": f"{int(pct * 100)}%"})
                self.stat_tx_chars += 1
                time.sleep(dur + GAP)

            elapsed += LGAP
            time.sleep(LGAP)

    # ── RX ────────────────────────────────────────────────────
    def _do_rx(self):
        if not self.connected:
            messagebox.showwarning("Not Connected", "Connect to Arduino first.")
            return
        self.mode = "RX"
        self.rx_message = ""
        self.osc.set_mode("RX")
        self._apply_rx_theme()
        self._send_raw("RX")         # Arduino expects exactly "RX\n"
        self._log("RX", "RX command sent. Waiting for Arduino confirmation...")

    # ── CAL ───────────────────────────────────────────────────
    def _do_cal(self):
        if not self.connected:
            messagebox.showwarning("Not Connected", "Connect to Arduino first.")
            return
        self.mode = "CAL"
        self.cal_meter._readings.clear()
        self.osc.set_mode("CAL")
        self._apply_cal_theme()
        self._send_raw("CAL")        # Arduino expects exactly "CAL\n"
        self._log("CAL", "CAL command sent. Adjust potentiometer to align laser on LDR...")

    # ── IDLE ──────────────────────────────────────────────────
    def _do_idle(self):
        self.mode = "IDLE"
        self.osc.set_mode("IDLE")
        self._apply_idle_theme()

    # =========================================================
    #  THEME SWITCHERS  (full colour overhaul per mode)
    # =========================================================

    def _apply_tx_theme(self, msg=""):
        self.configure(fg_color="#0e0500")
        self.banner.configure(text="LUMI MORSE  -  TRANSMITTING", text_color=C["tx_accent"])
        self.sub_lbl.configure(text=f'TX: "{msg}"', text_color=C["tx_glow"])
        self.big_char.configure(text_color=C["tx_accent"])
        self.progress.configure(progress_color=C["tx_accent"])
        self.progress.set(0)
        self.pct_lbl.configure(text="0%")
        self.tx_btn.configure(fg_color=C["tx_accent"], text_color="#000000")
        self.rx_btn.configure(fg_color=C["rx_dim"],    text_color=C["rx_accent"])
        self.cal_btn.configure(fg_color=C["cal_dim"],  text_color=C["cal_accent"])

    def _apply_rx_theme(self):
        self.configure(fg_color="#00090e")
        self.banner.configure(text="LUMI MORSE  -  RECEIVING", text_color=C["rx_accent"])
        self.sub_lbl.configure(text="Listening for laser pulses...",
                                text_color=C["rx_glow"])
        self.big_char.configure(text="?", text_color=C["rx_accent"])
        self.morse_lbl.configure(text="")
        self.decoded_lbl.configure(text="--")
        self.progress.configure(progress_color=C["rx_accent"])
        self.rx_btn.configure(fg_color=C["rx_accent"],  text_color="#000000")
        self.tx_btn.configure(fg_color=C["tx_dim"],     text_color=C["tx_accent"])
        self.cal_btn.configure(fg_color=C["cal_dim"],   text_color=C["cal_accent"])

    def _apply_cal_theme(self):
        self.configure(fg_color="#080010")
        self.banner.configure(text="LUMI MORSE  -  CALIBRATING", text_color=C["cal_accent"])
        self.sub_lbl.configure(
            text="Adjust potentiometer -- watching LDR sensor...",
            text_color=C["purple"])
        self.big_char.configure(text="~", text_color=C["cal_accent"])
        self.progress.configure(progress_color=C["cal_accent"])
        self.cal_btn.configure(fg_color=C["cal_accent"], text_color="#000000")
        self.tx_btn.configure(fg_color=C["tx_dim"],      text_color=C["tx_accent"])
        self.rx_btn.configure(fg_color=C["rx_dim"],      text_color=C["rx_accent"])

    def _apply_idle_theme(self):
        self.configure(fg_color=C["bg"])
        self.banner.configure(text="LUMI MORSE  -  SYSTEM IDLE", text_color=C["idle_accent"])
        self.sub_lbl.configure(text="Awaiting command...", text_color=C["text_lo"])
        self.big_char.configure(text="?", text_color=C["idle_accent"])
        self.morse_lbl.configure(text="")
        self.progress.configure(progress_color=C["idle_accent"])
        self.progress.set(0)
        self.pct_lbl.configure(text="--")
        self.tx_btn.configure(fg_color=C["tx_dim"],   text_color=C["tx_accent"])
        self.rx_btn.configure(fg_color=C["rx_dim"],   text_color=C["rx_accent"])
        self.cal_btn.configure(fg_color=C["cal_dim"], text_color=C["cal_accent"])

    # =========================================================
    #  PERIODIC TICKS
    # =========================================================

    def _tick_clock(self):
        now = datetime.now()
        self.clock_lbl.configure(text=now.strftime("%H:%M:%S"))
        self.date_lbl.configure(text=now.strftime("%Y . %m . %d"))
        self.after(1000, self._tick_clock)

    def _tick_stats(self):
        self._stx.configure( text=str(self.stat_tx_chars))
        self._srx.configure( text=str(self.stat_rx_chars))
        self._serr.configure(text=str(self.stat_errors))
        self._smsg.configure(text=str(self.stat_messages))
        self.after(400, self._tick_stats)

    # =========================================================
    #  LOG HELPERS
    # =========================================================

    def _log(self, level: str, text: str):
        self.log.append(level, text)

    def _clear_log(self):
        self.log.clear()
        self._log("SYS", "Log cleared.")

    def _clear_message(self):
        self.rx_message = ""
        self._msg_box_set("")
        self.decoded_lbl.configure(text="--")
        self._log("SYS", "Received message buffer cleared.")

    def _msg_box_set(self, text: str):
        """Replace the entire message box content."""
        self.msg_box.configure(state="normal")
        self.msg_box.delete("1.0", "end")
        if text:
            self.msg_box.insert("end", text)
        self.msg_box.configure(state="disabled")
        self.msg_box.see("end")

    def _copy_message(self):
        self.clipboard_clear()
        self.clipboard_append(self.rx_message)
        self._log("SYS", "Message copied to clipboard.")

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"securebeam_log_{datetime.now():%Y%m%d_%H%M%S}.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.log.dump())
            self._log("OK", f"Log exported to: {path}")
        except Exception as ex:
            self._log("ERR", f"Export failed: {ex}")

    def _export_message(self):
        if not self.rx_message.strip():
            messagebox.showinfo("Nothing", "No received message to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"securebeam_msg_{datetime.now():%Y%m%d_%H%M%S}.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.rx_message)
            self._log("OK", f"Message exported to: {path}")
        except Exception as ex:
            self._log("ERR", f"Export failed: {ex}")

    # =========================================================
    #  SHUTDOWN
    # =========================================================

    def _on_close(self):
        self.mode      = "IDLE"
        self._rx_alive = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.destroy()


# =============================================================================
#  ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = LaserMorseHUD()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
