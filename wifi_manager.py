"""
WiFi Manager Pro — Python 3.x | Windows
Функции: сканирование сетей, мониторинг сигнала, управление подключением,
         просмотр сохранённых профилей, получение паролей, статистика.
Зависимости: только стандартная библиотека + tkinter (встроен в Python).
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import time
import re
import os
import sys
from datetime import datetime


# ──────────────────────────── ЦВЕТА И СТИЛИ ────────────────────────────

BG        = "#0d1117"
PANEL     = "#161b22"
BORDER    = "#30363d"
ACCENT    = "#58a6ff"
ACCENT2   = "#3fb950"
WARN      = "#f0883e"
DANGER    = "#f85149"
TEXT      = "#e6edf3"
SUBTEXT   = "#8b949e"
HOVER     = "#1f2937"

FONT_HEAD = ("Consolas", 18, "bold")
FONT_SUB  = ("Consolas", 10)
FONT_BODY = ("Consolas", 10)
FONT_MONO = ("Courier New", 9)


# ──────────────────────────── УТИЛИТЫ ────────────────────────────

def run_cmd(cmd: str) -> str:
    """Выполнить команду и вернуть stdout (или сообщение об ошибке)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, encoding="cp866", errors="replace"
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"[Ошибка]: {e}"


def signal_bars(rssi: int) -> str:
    """Конвертировать RSSI (%) в символьные полосы."""
    if rssi >= 80:   return "████  Отличный"
    if rssi >= 60:   return "███░  Хороший"
    if rssi >= 40:   return "██░░  Средний"
    if rssi >= 20:   return "█░░░  Слабый"
    return               "░░░░  Нет сигнала"


def signal_color(rssi: int) -> str:
    if rssi >= 60: return ACCENT2
    if rssi >= 30: return WARN
    return DANGER


# ──────────────────────────── ПАРСЕРЫ ────────────────────────────

def parse_networks(raw: str) -> list[dict]:
    """Разобрать вывод `netsh wlan show networks mode=bssid`."""
    networks = []
    current: dict | None = None
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("SSID") and "BSSID" not in line:
            if current:
                networks.append(current)
            ssid = line.split(":", 1)[-1].strip()
            current = {"ssid": ssid or "<Скрытая>", "bssid": "—",
                       "signal": 0, "auth": "—", "cipher": "—",
                       "band": "—", "channel": "—"}
        elif current:
            if "BSSID" in line:
                current["bssid"] = line.split(":", 1)[-1].strip()
            elif re.search(r"Сигнал|Signal", line):
                m = re.search(r"(\d+)%", line)
                current["signal"] = int(m.group(1)) if m else 0
            elif re.search(r"Тип проверки подлинности|Authentication", line):
                current["auth"] = line.split(":", 1)[-1].strip()
            elif re.search(r"Тип шифрования|Cipher", line):
                current["cipher"] = line.split(":", 1)[-1].strip()
            elif re.search(r"Радиотип|Radio type", line):
                current["band"] = line.split(":", 1)[-1].strip()
            elif re.search(r"Канал|Channel", line):
                current["channel"] = line.split(":", 1)[-1].strip()
    if current:
        networks.append(current)
    return networks


def parse_profiles(raw: str) -> list[str]:
    """Имена сохранённых профилей."""
    profiles = []
    for line in raw.splitlines():
        m = re.search(r"Профиль всех пользователей\s*:\s*(.+)|All User Profile\s*:\s*(.+)", line)
        if m:
            profiles.append((m.group(1) or m.group(2)).strip())
    return profiles


def parse_profile_password(raw: str) -> str:
    """Извлечь пароль из вывода профиля."""
    for line in raw.splitlines():
        m = re.search(r"Содержимое ключа\s*:\s*(.+)|Key Content\s*:\s*(.+)", line)
        if m:
            return (m.group(1) or m.group(2)).strip()
    return "—"


def parse_connection_info(raw: str) -> dict:
    """Текущее подключение."""
    info = {}
    for line in raw.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            info[key.strip()] = val.strip()
    return info


# ══════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ОКНО
# ══════════════════════════════════════════════════════════════════

class WiFiManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WiFi Manager Pro")
        self.geometry("960x680")
        self.minsize(820, 560)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._monitor_running = False
        self._monitor_thread: threading.Thread | None = None
        self._networks: list[dict] = []
        self._profiles: list[str] = []

        self._build_ui()
        self._refresh_networks()
        self._refresh_profiles()
        self._refresh_status()

    # ─────────── UI BUILDER ───────────

    def _build_ui(self):
        # ── Заголовок ──
        header = tk.Frame(self, bg=PANEL, height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="📡  WiFi Manager Pro",
                 font=FONT_HEAD, bg=PANEL, fg=ACCENT).pack(side="left", padx=20, pady=10)

        self._status_dot = tk.Label(header, text="●", font=("Consolas", 14),
                                    bg=PANEL, fg=SUBTEXT)
        self._status_dot.pack(side="right", padx=6)
        self._status_lbl = tk.Label(header, text="Статус: —",
                                    font=FONT_SUB, bg=PANEL, fg=SUBTEXT)
        self._status_lbl.pack(side="right", padx=(0, 4))

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")

        # ── Вкладки ──
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook",        background=BG,    borderwidth=0)
        style.configure("TNotebook.Tab",    background=PANEL, foreground=SUBTEXT,
                        padding=[14, 6],    font=FONT_SUB,    borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        self._tab_scan      = self._make_frame(nb)
        self._tab_profiles  = self._make_frame(nb)
        self._tab_monitor   = self._make_frame(nb)
        self._tab_connect   = self._make_frame(nb)
        self._tab_info      = self._make_frame(nb)

        nb.add(self._tab_scan,     text="  🔍 Сканирование  ")
        nb.add(self._tab_profiles, text="  💾 Профили  ")
        nb.add(self._tab_monitor,  text="  📊 Мониторинг  ")
        nb.add(self._tab_connect,  text="  🔗 Подключение  ")
        nb.add(self._tab_info,     text="  ℹ️ О программе  ")

        self._build_scan_tab()
        self._build_profiles_tab()
        self._build_monitor_tab()
        self._build_connect_tab()
        self._build_info_tab()

    def _make_frame(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=BG)
        return f

    # ─────────── ВКЛАДКА 1: СКАНИРОВАНИЕ ───────────

    def _build_scan_tab(self):
        tab = self._tab_scan

        toolbar = tk.Frame(tab, bg=BG)
        toolbar.pack(fill="x", padx=16, pady=(14, 0))

        self._btn_scan = self._btn(toolbar, "🔄  Обновить", self._refresh_networks)
        self._btn_scan.pack(side="left")

        self._sort_var = tk.StringVar(value="Сигнал ↓")
        tk.Label(toolbar, text="Сортировка:", bg=BG, fg=SUBTEXT, font=FONT_SUB).pack(side="left", padx=(16, 4))
        sort_cb = ttk.Combobox(toolbar, textvariable=self._sort_var,
                               values=["Сигнал ↓", "Сигнал ↑", "Имя A→Z", "Канал"],
                               width=12, state="readonly", font=FONT_SUB)
        sort_cb.pack(side="left")
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self._render_networks())

        self._scan_count = tk.Label(toolbar, text="", bg=BG, fg=SUBTEXT, font=FONT_SUB)
        self._scan_count.pack(side="right")

        # Таблица
        cols = ("SSID", "Сигнал", "Безопасность", "Канал", "Диапазон", "BSSID")
        frame = tk.Frame(tab, bg=BG)
        frame.pack(fill="both", expand=True, padx=16, pady=10)

        style = ttk.Style()
        style.configure("Scan.Treeview",
                        background=PANEL, foreground=TEXT,
                        fieldbackground=PANEL, borderwidth=0,
                        rowheight=26, font=FONT_BODY)
        style.configure("Scan.Treeview.Heading",
                        background=BORDER, foreground=SUBTEXT,
                        borderwidth=0, font=FONT_SUB)
        style.map("Scan.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

        self._tree = ttk.Treeview(frame, columns=cols, show="headings",
                                  style="Scan.Treeview")
        widths = [220, 130, 120, 70, 100, 150]
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, minwidth=60)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._on_network_dblclick)

        tk.Label(tab, text="Двойной клик — подключиться к выбранной сети",
                 bg=BG, fg=SUBTEXT, font=FONT_MONO).pack(pady=(0, 8))

    def _render_networks(self):
        sort = self._sort_var.get()
        nets = list(self._networks)
        if sort == "Сигнал ↓":   nets.sort(key=lambda n: n["signal"], reverse=True)
        elif sort == "Сигнал ↑": nets.sort(key=lambda n: n["signal"])
        elif sort == "Имя A→Z":  nets.sort(key=lambda n: n["ssid"].lower())
        elif sort == "Канал":    nets.sort(key=lambda n: n.get("channel", "0"))

        for row in self._tree.get_children():
            self._tree.delete(row)

        for n in nets:
            sig_txt = f"{n['signal']}%  {signal_bars(n['signal'])}"
            tag = "good" if n["signal"] >= 60 else ("warn" if n["signal"] >= 30 else "bad")
            self._tree.insert("", "end", values=(
                n["ssid"], sig_txt, n["auth"],
                n.get("channel", "—"), n.get("band", "—"), n["bssid"]
            ), tags=(tag,))

        self._tree.tag_configure("good", foreground=ACCENT2)
        self._tree.tag_configure("warn", foreground=WARN)
        self._tree.tag_configure("bad",  foreground=DANGER)
        self._scan_count.config(text=f"Найдено сетей: {len(nets)}")

    def _refresh_networks(self):
        self._btn_scan.config(state="disabled", text="⏳  Сканирование...")
        self._scan_count.config(text="Сканирование…")

        def task():
            raw = run_cmd("netsh wlan show networks mode=bssid")
            self._networks = parse_networks(raw)
            self.after(0, lambda: (
                self._render_networks(),
                self._btn_scan.config(state="normal", text="🔄  Обновить")
            ))
        threading.Thread(target=task, daemon=True).start()

    def _on_network_dblclick(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        ssid = self._tree.item(sel[0])["values"][0]
        auth = self._tree.item(sel[0])["values"][2]
        self._open_connect_dialog(ssid, str(auth))

    # ─────────── ВКЛАДКА 2: ПРОФИЛИ ───────────

    def _build_profiles_tab(self):
        tab = self._tab_profiles

        toolbar = tk.Frame(tab, bg=BG)
        toolbar.pack(fill="x", padx=16, pady=(14, 0))
        self._btn_prof  = self._btn(toolbar, "🔄  Обновить", self._refresh_profiles)
        self._btn_prof.pack(side="left")
        self._btn_pass  = self._btn(toolbar, "🔑  Показать пароль", self._show_password, WARN)
        self._btn_pass.pack(side="left", padx=8)
        self._btn_del   = self._btn(toolbar, "🗑  Удалить профиль", self._delete_profile, DANGER)
        self._btn_del.pack(side="left")
        self._btn_export = self._btn(toolbar, "💾  Экспорт всех", self._export_profiles, ACCENT2)
        self._btn_export.pack(side="left", padx=8)

        frame = tk.Frame(tab, bg=BG)
        frame.pack(fill="both", expand=True, padx=16, pady=10)

        self._prof_list = tk.Listbox(frame, bg=PANEL, fg=TEXT, selectbackground=ACCENT,
                                     selectforeground=BG, font=FONT_BODY, borderwidth=0,
                                     highlightthickness=0, activestyle="none")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._prof_list.yview)
        self._prof_list.configure(yscrollcommand=vsb.set)
        self._prof_list.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Панель деталей
        self._prof_detail = scrolledtext.ScrolledText(
            tab, height=7, bg=PANEL, fg=ACCENT2, font=FONT_MONO,
            borderwidth=0, state="disabled"
        )
        self._prof_detail.pack(fill="x", padx=16, pady=(0, 10))

        self._prof_list.bind("<<ListboxSelect>>", self._on_profile_select)

    def _refresh_profiles(self):
        raw = run_cmd("netsh wlan show profiles")
        self._profiles = parse_profiles(raw)
        self._prof_list.delete(0, "end")
        for p in self._profiles:
            self._prof_list.insert("end", f"  📶  {p}")

    def _on_profile_select(self, event):
        sel = self._prof_list.curselection()
        if not sel:
            return
        name = self._profiles[sel[0]]
        raw = run_cmd(f'netsh wlan show profile name="{name}"')
        self._show_prof_detail(raw)

    def _show_prof_detail(self, text: str):
        self._prof_detail.config(state="normal")
        self._prof_detail.delete("1.0", "end")
        self._prof_detail.insert("end", text)
        self._prof_detail.config(state="disabled")

    def _show_password(self):
        sel = self._prof_list.curselection()
        if not sel:
            messagebox.showinfo("WiFi Manager", "Выберите профиль в списке.")
            return
        name = self._profiles[sel[0]]
        raw = run_cmd(f'netsh wlan show profile name="{name}" key=clear')
        pwd = parse_profile_password(raw)
        messagebox.showinfo(f"Пароль: {name}", f"🔑  Пароль: {pwd}")

    def _delete_profile(self):
        sel = self._prof_list.curselection()
        if not sel:
            messagebox.showinfo("WiFi Manager", "Выберите профиль в списке.")
            return
        name = self._profiles[sel[0]]
        if not messagebox.askyesno("Удалить профиль",
                                   f"Удалить профиль «{name}»?\nСеть будет забыта."):
            return
        out = run_cmd(f'netsh wlan delete profile name="{name}"')
        messagebox.showinfo("Результат", out.strip() or "Удалено.")
        self._refresh_profiles()

    def _export_profiles(self):
        folder = os.path.expanduser("~\\Desktop\\WiFi_Profiles")
        os.makedirs(folder, exist_ok=True)
        out = run_cmd(f'netsh wlan export profile folder="{folder}" key=clear')
        messagebox.showinfo("Экспорт", f"Профили сохранены в:\n{folder}\n\n{out[:300]}")

    # ─────────── ВКЛАДКА 3: МОНИТОРИНГ ───────────

    def _build_monitor_tab(self):
        tab = self._tab_monitor

        toolbar = tk.Frame(tab, bg=BG)
        toolbar.pack(fill="x", padx=16, pady=(14, 6))

        self._btn_mon_start = self._btn(toolbar, "▶  Запустить мониторинг",
                                        self._toggle_monitor)
        self._btn_mon_start.pack(side="left")

        tk.Label(toolbar, text="Интервал (сек):", bg=BG, fg=SUBTEXT, font=FONT_SUB).pack(side="left", padx=(16,4))
        self._interval_var = tk.IntVar(value=3)
        sp = ttk.Spinbox(toolbar, from_=1, to=60, textvariable=self._interval_var,
                         width=5, font=FONT_SUB)
        sp.pack(side="left")

        self._btn_mon_clear = self._btn(toolbar, "🗑  Очистить", self._clear_monitor, DANGER)
        self._btn_mon_clear.pack(side="right")

        # Canvas для графика сигнала
        self._canvas = tk.Canvas(tab, bg=PANEL, height=140, highlightthickness=0)
        self._canvas.pack(fill="x", padx=16, pady=(0, 8))
        self._signal_history: list[int] = []

        self._mon_log = scrolledtext.ScrolledText(
            tab, bg=PANEL, fg=ACCENT2, font=FONT_MONO,
            borderwidth=0, state="disabled"
        )
        self._mon_log.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    def _toggle_monitor(self):
        if self._monitor_running:
            self._monitor_running = False
            self._btn_mon_start.config(text="▶  Запустить мониторинг", bg=ACCENT)
        else:
            self._monitor_running = True
            self._btn_mon_start.config(text="⏹  Остановить", bg=DANGER)
            self._signal_history.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

    def _monitor_loop(self):
        while self._monitor_running:
            raw = run_cmd("netsh wlan show interfaces")
            info = parse_connection_info(raw)
            sig_str = ""
            for k, v in info.items():
                if re.search(r"Сигнал|Signal", k):
                    sig_str = v
                    break
            sig = int(re.search(r"\d+", sig_str).group()) if re.search(r"\d+", sig_str) else 0
            ts  = datetime.now().strftime("%H:%M:%S")
            ssid = info.get("SSID", info.get("Имя", "—"))
            line = f"[{ts}]  SSID: {ssid:<22}  Сигнал: {sig:3}%  {signal_bars(sig)}\n"
            self.after(0, lambda l=line, s=sig: self._mon_append(l, s))
            time.sleep(self._interval_var.get())

    def _mon_append(self, line: str, sig: int):
        self._mon_log.config(state="normal")
        self._mon_log.insert("end", line)
        self._mon_log.see("end")
        self._mon_log.config(state="disabled")

        self._signal_history.append(sig)
        if len(self._signal_history) > 60:
            self._signal_history.pop(0)
        self._draw_signal_graph()

    def _draw_signal_graph(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width() or 900
        h = 140
        pad = 8

        # Фон
        c.create_rectangle(0, 0, w, h, fill=PANEL, outline="")

        # Горизонтальные линии
        for pct in (25, 50, 75, 100):
            y = h - pad - (h - 2*pad) * pct // 100
            c.create_line(pad, y, w - pad, y, fill=BORDER, dash=(4, 4))
            c.create_text(pad + 2, y, text=f"{pct}%", anchor="w",
                          fill=SUBTEXT, font=FONT_MONO)

        hist = self._signal_history
        if len(hist) < 2:
            return

        xs = [pad + 32 + (w - pad - 32) * i // (len(hist) - 1) for i in range(len(hist))]
        ys = [h - pad - (h - 2*pad) * v // 100 for v in hist]

        # Закрашенная область
        pts_area = [pad + 32, h - pad] + [x for p in zip(xs, ys) for x in p] + [xs[-1], h - pad]
        c.create_polygon(pts_area, fill="#1f3b5c", outline="")

        # Линия
        pts_line = [x for p in zip(xs, ys) for x in p]
        c.create_line(pts_line, fill=ACCENT, width=2, smooth=True)

        # Последняя точка
        c.create_oval(xs[-1]-4, ys[-1]-4, xs[-1]+4, ys[-1]+4, fill=ACCENT, outline=BG, width=2)
        c.create_text(xs[-1]+6, ys[-1], text=f"{hist[-1]}%", anchor="w",
                      fill=ACCENT, font=FONT_MONO)

    def _clear_monitor(self):
        self._mon_log.config(state="normal")
        self._mon_log.delete("1.0", "end")
        self._mon_log.config(state="disabled")
        self._signal_history.clear()
        self._draw_signal_graph()

    # ─────────── ВКЛАДКА 4: ПОДКЛЮЧЕНИЕ ───────────

    def _build_connect_tab(self):
        tab = self._tab_connect

        inner = tk.Frame(tab, bg=BG)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(inner, text="Подключиться к Wi-Fi", font=("Consolas", 14, "bold"),
                 bg=BG, fg=ACCENT).grid(row=0, column=0, columnspan=2, pady=(0, 20))

        labels = ["SSID (Имя сети):", "Пароль:", "Тип безопасности:"]
        for i, lbl in enumerate(labels):
            tk.Label(inner, text=lbl, bg=BG, fg=SUBTEXT, font=FONT_SUB, anchor="w"
                     ).grid(row=i+1, column=0, sticky="w", padx=(0, 12), pady=6)

        self._conn_ssid = self._entry(inner)
        self._conn_ssid.grid(row=1, column=1, pady=6, ipady=4)

        self._conn_pass = self._entry(inner, show="●")
        self._conn_pass.grid(row=2, column=1, pady=6, ipady=4)

        self._conn_auth = ttk.Combobox(inner, values=["WPA2PSK", "WPA3SAE", "open"],
                                       width=28, state="readonly", font=FONT_SUB)
        self._conn_auth.set("WPA2PSK")
        self._conn_auth.grid(row=3, column=1, pady=6)

        self._btn(inner, "🔗  Подключиться", self._do_connect
                  ).grid(row=4, column=0, columnspan=2, pady=(20, 8))
        self._btn(inner, "⚡  Отключиться от текущей сети", self._do_disconnect, WARN
                  ).grid(row=5, column=0, columnspan=2, pady=4)
        self._btn(inner, "🔄  Перезапустить Wi-Fi адаптер", self._restart_adapter, DANGER
                  ).grid(row=6, column=0, columnspan=2, pady=4)

        self._conn_result = tk.Label(inner, text="", bg=BG, fg=ACCENT2,
                                     font=FONT_SUB, wraplength=340)
        self._conn_result.grid(row=7, column=0, columnspan=2, pady=(12, 0))

    def _open_connect_dialog(self, ssid: str, auth: str):
        self._conn_ssid.delete(0, "end")
        self._conn_ssid.insert(0, ssid)
        auth_val = "WPA2PSK" if "WPA2" in auth else ("open" if "Open" in auth else "WPA2PSK")
        self._conn_auth.set(auth_val)
        # Переключить на вкладку подключения
        for w in self.winfo_children():
            if isinstance(w, ttk.Notebook):
                w.select(3)
                break

    def _do_connect(self):
        ssid = self._conn_ssid.get().strip()
        pwd  = self._conn_pass.get().strip()
        auth = self._conn_auth.get()

        if not ssid:
            self._conn_result.config(text="⚠ Введите SSID!", fg=WARN)
            return

        # Создать XML профиль
        if auth == "open":
            key_xml = ""
            auth_xml = "<authentication>open</authentication><encryption>none</encryption>"
        else:
            key_xml = f"<keyMaterial>{pwd}</keyMaterial>"
            auth_xml = (f"<authentication>{auth}</authentication>"
                        f"<encryption>AES</encryption>")

        xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM><security>
    <authEncryption>{auth_xml}</authEncryption>
    {"<sharedKey><keyType>passPhrase</keyType><protected>false</protected>" + key_xml + "</sharedKey>" if pwd else ""}
  </security></MSM>
</WLANProfile>"""

        tmp = os.path.join(os.environ.get("TEMP", "."), "_wm_profile.xml")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(xml)

        def task():
            add = run_cmd(f'netsh wlan add profile filename="{tmp}"')
            con = run_cmd(f'netsh wlan connect name="{ssid}"')
            try: os.remove(tmp)
            except: pass
            msg = (con + add).strip()
            color = ACCENT2 if "успешно" in msg.lower() or "success" in msg.lower() else WARN
            self.after(0, lambda: self._conn_result.config(text=f"✔ {msg[:160]}", fg=color))
            self.after(1500, self._refresh_status)

        self._conn_result.config(text="⏳ Подключение…", fg=SUBTEXT)
        threading.Thread(target=task, daemon=True).start()

    def _do_disconnect(self):
        out = run_cmd("netsh wlan disconnect")
        self._conn_result.config(text=out.strip()[:160], fg=WARN)
        self.after(1000, self._refresh_status)

    def _restart_adapter(self):
        if not messagebox.askyesno("Перезапуск адаптера",
                                   "Перезапустить Wi-Fi адаптер?\n(Нужны права администратора)"):
            return
        out1 = run_cmd('netsh interface set interface "Wi-Fi" disabled')
        time.sleep(1.5)
        out2 = run_cmd('netsh interface set interface "Wi-Fi" enabled')
        self._conn_result.config(text=(out1 + out2).strip()[:160] or "Адаптер перезапущен.", fg=ACCENT2)

    # ─────────── ВКЛАДКА 5: О ПРОГРАММЕ ───────────

    def _build_info_tab(self):
        tab = self._tab_info
        inner = tk.Frame(tab, bg=BG)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        lines = [
            ("📡  WiFi Manager Pro", ("Consolas", 22, "bold"), ACCENT),
            ("Версия 1.0  •  Python 3.x  •  Windows", FONT_SUB, SUBTEXT),
            ("", FONT_SUB, BG),
            ("Возможности программы:", ("Consolas", 11, "bold"), TEXT),
            ("  🔍  Сканирование доступных Wi-Fi сетей", FONT_SUB, TEXT),
            ("  📊  Мониторинг сигнала в реальном времени с графиком", FONT_SUB, TEXT),
            ("  💾  Просмотр и управление сохранёнными профилями", FONT_SUB, TEXT),
            ("  🔑  Показ сохранённых паролей", FONT_SUB, TEXT),
            ("  🔗  Подключение к сетям (WPA2, WPA3, Open)", FONT_SUB, TEXT),
            ("  🗑  Удаление профилей", FONT_SUB, TEXT),
            ("  💾  Экспорт профилей на рабочий стол", FONT_SUB, TEXT),
            ("  ⚡  Отключение и перезапуск адаптера", FONT_SUB, TEXT),
            ("", FONT_SUB, BG),
            ("Зависимости: только стандартная библиотека Python", FONT_MONO, SUBTEXT),
            ("Использует: netsh wlan (встроен в Windows)", FONT_MONO, SUBTEXT),
        ]

        for text, font, color in lines:
            tk.Label(inner, text=text, font=font, bg=BG, fg=color,
                     anchor="w").pack(anchor="w", pady=1)

    # ─────────── СТАТУС СТРОКА ───────────

    def _refresh_status(self):
        def task():
            raw = run_cmd("netsh wlan show interfaces")
            info = parse_connection_info(raw)
            ssid = info.get("SSID", info.get("Имя", ""))
            sig_str = ""
            for k, v in info.items():
                if re.search(r"Сигнал|Signal", k):
                    sig_str = v
                    break

            if ssid:
                sig = int(re.search(r"\d+", sig_str).group()) if re.search(r"\d+", sig_str) else 0
                msg   = f"Подключено: {ssid}  ({sig}%)"
                color = signal_color(sig)
                dot   = ACCENT2
            else:
                msg   = "Не подключено"
                color = SUBTEXT
                dot   = DANGER

            self.after(0, lambda: (
                self._status_lbl.config(text=msg, fg=color),
                self._status_dot.config(fg=dot)
            ))

        threading.Thread(target=task, daemon=True).start()
        self.after(10_000, self._refresh_status)   # авто-обновление каждые 10 с

    # ─────────── ВСПОМОГАТЕЛЬНЫЕ ВИДЖЕТЫ ───────────

    def _btn(self, parent, text: str, cmd=None, color=ACCENT) -> tk.Button:
        b = tk.Button(
            parent, text=text, command=cmd,
            bg=color, fg=BG, activebackground=TEXT, activeforeground=BG,
            font=FONT_SUB, relief="flat", cursor="hand2",
            padx=12, pady=5
        )
        b.bind("<Enter>", lambda e: b.config(bg=TEXT))
        b.bind("<Leave>", lambda e: b.config(bg=color))
        return b

    def _entry(self, parent, show="") -> tk.Entry:
        e = tk.Entry(parent, bg=PANEL, fg=TEXT, insertbackground=ACCENT,
                     font=FONT_BODY, relief="flat", width=30,
                     highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=BORDER, show=show)
        return e


# ══════════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if sys.platform != "win32":
        print("Эта программа работает только на Windows.")
        sys.exit(1)

    app = WiFiManager()
    app.mainloop()
