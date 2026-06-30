"""
JUMO AQUIS Logger — GUI

Start:
    python3 gui.py
"""

import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.dates as mdates

import config
import app_settings
import storage
import version
from logging_setup import setup_logging
from poller import PollerThread
import export as export_module

LIVE_WINDOW_MINUTES = 30
PLOT_REFRESH_MS = 10_000


class JumoLoggerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.minsize(800, 640)

        build_str = version.BUILD_TIME or datetime.now().strftime("%Y%m%d_%H%M")
        self.title(f"JUMO AQUIS Logger v{version.VERSION} — Build {build_str}")

        self._cfg = app_settings.load()
        self._poller: PollerThread | None = None
        self._status_queue: queue.Queue = queue.Queue()

        self._build_ui()
        self._schedule_plot_refresh()
        self._process_status_queue()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        self._build_control_section(main)
        self._build_plot_section(main)
        self._build_export_section(main)

    def _build_control_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Verbindung & Steuerung", padding=8)
        frame.pack(fill=tk.X, pady=(0, 8))

        # Konfigurationszeile
        cfg = ttk.Frame(frame)
        cfg.pack(fill=tk.X)

        ttk.Label(cfg, text="IP-Adresse:").pack(side=tk.LEFT)
        self._ip_var = tk.StringVar(value=self._cfg["modbus_host"])
        ttk.Entry(cfg, textvariable=self._ip_var, width=16).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(cfg, text="Port:").pack(side=tk.LEFT)
        self._port_var = tk.StringVar(value=str(self._cfg["modbus_port"]))
        ttk.Entry(cfg, textvariable=self._port_var, width=6).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(cfg, text="Intervall (s):").pack(side=tk.LEFT)
        self._interval_var = tk.StringVar(value=str(self._cfg["poll_interval"]))
        ttk.Entry(cfg, textvariable=self._interval_var, width=6).pack(side=tk.LEFT, padx=(4, 0))

        # Status- und Schaltflächenzeile
        status_row = ttk.Frame(frame)
        status_row.pack(fill=tk.X, pady=(8, 0))

        self._status_label = ttk.Label(status_row, text="● Gestoppt", foreground="gray")
        self._status_label.pack(side=tk.LEFT)

        self._stop_btn = ttk.Button(
            status_row, text="■ Stoppen", command=self._stop_poller, state=tk.DISABLED
        )
        self._stop_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._start_btn = ttk.Button(
            status_row, text="▶ Starten", command=self._start_poller
        )
        self._start_btn.pack(side=tk.RIGHT)

    def _build_plot_section(self, parent):
        frame = ttk.LabelFrame(
            parent,
            text=f"Live-Vorschau (letzte {LIVE_WINDOW_MINUTES} Minuten)",
            padding=8,
        )
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self._fig = Figure(figsize=(10, 4), dpi=96)
        self._ax_temp = self._fig.add_subplot(211)
        self._ax_leit = self._fig.add_subplot(212, sharex=self._ax_temp)
        self._fig.tight_layout(pad=2.5)

        self._canvas = FigureCanvasTkAgg(self._fig, master=frame)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill=tk.X)
        NavigationToolbar2Tk(self._canvas, toolbar_frame)

    def _build_export_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Export", padding=8)
        frame.pack(fill=tk.X)

        row = ttk.Frame(frame)
        row.pack(fill=tk.X)

        ttk.Label(row, text="Von:").pack(side=tk.LEFT)
        default_von = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 00:00")
        self._von_var = tk.StringVar(value=default_von)
        ttk.Entry(row, textvariable=self._von_var, width=18).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(row, text="Bis:").pack(side=tk.LEFT)
        self._bis_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        self._bis_entry = ttk.Entry(row, textvariable=self._bis_var, width=18)
        self._bis_entry.pack(side=tk.LEFT, padx=(4, 4))
        self._bis_jetzt_var = tk.BooleanVar(value=self._cfg.get("export_bis_jetzt", True))
        ttk.Checkbutton(
            row, text="jetzt", variable=self._bis_jetzt_var,
            command=self._on_bis_jetzt_toggle,
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row, text="Format:").pack(side=tk.LEFT)
        self._fmt_var = tk.StringVar(value=self._cfg["export_format"])
        ttk.Combobox(
            row, textvariable=self._fmt_var, values=["xlsx", "csv"], width=6, state="readonly"
        ).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Button(row, text="Exportieren", command=self._run_export).pack(side=tk.RIGHT)

        # Initialzustand herstellen (Feld ggf. deaktivieren + Timer starten)
        self._on_bis_jetzt_toggle()

    # ------------------------------------------------------------------
    # Poller-Steuerung
    # ------------------------------------------------------------------

    def _start_poller(self):
        try:
            port = int(self._port_var.get())
            interval = int(self._interval_var.get())
        except ValueError:
            messagebox.showerror("Konfigurationsfehler", "Port und Intervall müssen Ganzzahlen sein.")
            return

        self._poller = PollerThread(
            host=self._ip_var.get(),
            port=port,
            unit_id=config.MODBUS_UNIT_ID,
            poll_interval=interval,
            messwerte=config.MESSWERTE,
            db_path=config.DB_PATH,
            status_callback=lambda evt, data: self._status_queue.put((evt, data)),
        )
        self._poller.start()
        self._save_settings()
        self._start_btn.configure(state=tk.DISABLED)
        self._stop_btn.configure(state=tk.NORMAL)
        self._status_label.configure(text="● Verbinde ...", foreground="orange")

    def _on_bis_jetzt_toggle(self):
        if self._bis_jetzt_var.get():
            self._bis_var.set(datetime.now().strftime("%Y-%m-%d %H:%M"))
            self._bis_entry.configure(state=tk.DISABLED)
            self._tick_bis_jetzt()
        else:
            self._bis_entry.configure(state=tk.NORMAL)

    def _tick_bis_jetzt(self):
        if self._bis_jetzt_var.get():
            self._bis_var.set(datetime.now().strftime("%Y-%m-%d %H:%M"))
            self.after(60_000, self._tick_bis_jetzt)

    def _stop_poller(self):
        if self._poller:
            self._poller.stop()
        self._stop_btn.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Status-Queue (Thread-sicherer Kanal vom PollerThread zur GUI)
    # ------------------------------------------------------------------

    def _process_status_queue(self):
        try:
            while True:
                evt, data = self._status_queue.get_nowait()
                if evt == "connected":
                    self._status_label.configure(
                        text=f"● Verbunden mit {data['host']}:{data['port']}",
                        foreground="green",
                    )
                elif evt == "reading":
                    parts = []
                    for name, (val, fehler) in data.get("readings", {}).items():
                        if fehler:
                            parts.append(f"{name}: Fehler")
                        elif val is not None:
                            parts.append(f"{name}: {val:.3f}")
                    self._status_label.configure(
                        text="● " + "   |   ".join(parts), foreground="green"
                    )
                elif evt == "error":
                    self._status_label.configure(
                        text=f"● Fehler: {data['message']}", foreground="red"
                    )
                elif evt == "stopped":
                    self._status_label.configure(text="● Gestoppt", foreground="gray")
                    self._start_btn.configure(state=tk.NORMAL)
                    self._stop_btn.configure(state=tk.DISABLED)
                    self._poller = None
        except queue.Empty:
            pass
        self.after(500, self._process_status_queue)

    # ------------------------------------------------------------------
    # Live-Plot
    # ------------------------------------------------------------------

    def _schedule_plot_refresh(self):
        self._redraw_plot()
        self.after(PLOT_REFRESH_MS, self._schedule_plot_refresh)

    def _redraw_plot(self):
        try:
            now = datetime.now(timezone.utc)
            von = (now - timedelta(minutes=LIVE_WINDOW_MINUTES)).isoformat()
            bis = now.isoformat()

            rows = storage.query_range(config.DB_PATH, von, bis)

            series: dict[str, tuple[list, list]] = {}
            for row in rows:
                eingang = row["eingang"]
                wert = row["wert_kompensiert"]
                if wert is None:
                    continue
                ts = datetime.fromisoformat(row["zeitstempel"]).astimezone()  # UTC → Lokalzeit
                if eingang not in series:
                    series[eingang] = ([], [])
                series[eingang][0].append(ts)
                series[eingang][1].append(wert)

            self._ax_temp.clear()
            self._ax_leit.clear()

            if "temperatur_medium" in series:
                ts_list, val_list = series["temperatur_medium"]
                self._ax_temp.plot(ts_list, val_list, color="tab:red", linewidth=1.2)
            self._ax_temp.set_ylabel("Temperatur (°C)")
            self._ax_temp.grid(True, alpha=0.3)
            self._ax_temp.tick_params(labelbottom=False)

            if "leitfaehigkeit" in series:
                ts_list, val_list = series["leitfaehigkeit"]
                self._ax_leit.plot(ts_list, val_list, color="tab:blue", linewidth=1.2)
            self._ax_leit.set_ylabel("Leitfähigkeit")
            self._ax_leit.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            self._ax_leit.grid(True, alpha=0.3)

            self._fig.autofmt_xdate(rotation=0, ha="center")
            self._fig.tight_layout(pad=2.5)
            self._canvas.draw_idle()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _run_export(self):
        fmt = self._fmt_var.get()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filetypes = (
            [("Excel-Datei", "*.xlsx")] if fmt == "xlsx" else [("CSV-Datei", "*.csv")]
        )
        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=filetypes,
            initialfile=f"export_{stamp}.{fmt}",
        )
        if not path:
            return

        try:
            if self._bis_jetzt_var.get():
                self._bis_var.set(datetime.now().strftime("%Y-%m-%d %H:%M"))
            export_module.run(
                von_text=self._von_var.get(),
                bis_text=self._bis_var.get(),
                fmt=fmt,
                output_path=path,
            )
            messagebox.showinfo("Export erfolgreich", f"Gespeichert unter:\n{path}")
        except ValueError as exc:
            messagebox.showerror("Export-Fehler", str(exc))

    # ------------------------------------------------------------------
    # Aufräumen beim Schliessen
    # ------------------------------------------------------------------

    def _save_settings(self):
        try:
            app_settings.save({
                "modbus_host": self._ip_var.get(),
                "modbus_port": int(self._port_var.get()),
                "poll_interval": int(self._interval_var.get()),
                "export_format": self._fmt_var.get(),
                "export_bis_jetzt": self._bis_jetzt_var.get(),
            })
        except (ValueError, OSError):
            pass

    def on_closing(self):
        self._save_settings()
        if self._poller:
            self._poller.stop()
            self._poller.join(timeout=5)
        self.destroy()


if __name__ == "__main__":
    import sys
    import traceback

    def _global_exception_handler(exc_type, exc_value, exc_tb):
        """
        Zeigt unbehandelte Exceptions als Fehlerdialog, statt lautlos zu sterben.
        Wichtig bei --windowed-Builds, wo kein Konsolenfenster existiert.
        """
        err = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            messagebox.showerror("Unerwarteter Fehler", err[:2000])
        except Exception:
            pass
        sys.exit(1)

    sys.excepthook = _global_exception_handler

    setup_logging(console=not getattr(sys, "frozen", False))

    app = JumoLoggerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
