"""
DAF — Delayed Auditory Feedback
Приложение для замедления речи в реальном времени
Требования: pip install pyaudio numpy
"""

import tkinter as tk
from tkinter import ttk, font
import pyaudio
import numpy as np
import threading
import collections
import sys

# ─── Аудио-константы ───────────────────────────────────────────────
CHUNK   = 512
FORMAT  = pyaudio.paFloat32
CHANNELS = 1
RATE    = 44100

# ─── Цветовая схема ────────────────────────────────────────────────
BG        = "#0d0f14"
PANEL     = "#161920"
ACCENT    = "#00d4aa"
ACCENT2   = "#0099ff"
TEXT      = "#e8eaf0"
TEXT_DIM  = "#6b7280"
DANGER    = "#ff4d6d"
SUCCESS   = "#00d4aa"
SLIDER_BG = "#1e2330"


class DAFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DAF — Delayed Auditory Feedback")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.geometry("480x620")

        self.running = False
        self.p = pyaudio.PyAudio()
        self.stream_in  = None
        self.stream_out = None
        self.audio_thread = None

        # ── Переменные ──────────────────────────────────────
        self.delay_var   = tk.IntVar(value=200)
        self.volume_var  = tk.DoubleVar(value=1.0)
        self.mix_var     = tk.DoubleVar(value=1.0)   # 0=только живой, 1=только delayed
        self.pitch_shift = tk.BooleanVar(value=False)
        self.input_dev   = tk.IntVar(value=-1)
        self.output_dev  = tk.IntVar(value=-1)

        self._build_ui()
        self._populate_devices()

    # ══════════════════════════════════════════════════════════════
    #  UI
    # ══════════════════════════════════════════════════════════════
    def _build_ui(self):
        pad = dict(padx=24, pady=0)

        # ── Заголовок ─────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(28, 4))

        tk.Label(header, text="DAF", bg=BG, fg=ACCENT,
                 font=("Courier New", 38, "bold")).pack(side="left")

        sub = tk.Frame(header, bg=BG)
        sub.pack(side="left", padx=(10, 0), pady=(12, 0))
        tk.Label(sub, text="Delayed Auditory Feedback", bg=BG, fg=TEXT_DIM,
                 font=("Courier New", 10)).pack(anchor="w")
        tk.Label(sub, text="v1.0  ·  реальное время", bg=BG, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(anchor="w")

        # ── Индикатор статуса ──────────────────────────────────
        self.status_frame = tk.Frame(self.root, bg=PANEL, height=36)
        self.status_frame.pack(fill="x", padx=24, pady=(10, 0))
        self.status_frame.pack_propagate(False)

        self.status_dot = tk.Label(self.status_frame, text="●", bg=PANEL, fg=TEXT_DIM,
                                   font=("Courier New", 14))
        self.status_dot.pack(side="left", padx=(14, 6), pady=8)

        self.status_lbl = tk.Label(self.status_frame, text="Остановлено",
                                   bg=PANEL, fg=TEXT_DIM,
                                   font=("Courier New", 11))
        self.status_lbl.pack(side="left")

        # ── Устройства ────────────────────────────────────────
        dev_frame = tk.LabelFrame(self.root, text="  Устройства  ", bg=BG, fg=TEXT_DIM,
                                  font=("Courier New", 9), bd=1, relief="flat",
                                  labelanchor="n")
        dev_frame.pack(fill="x", padx=24, pady=(16, 0))

        self._row_label(dev_frame, "Микрофон (вход)")
        self.in_combo = ttk.Combobox(dev_frame, state="readonly", font=("Courier New", 9))
        self.in_combo.pack(fill="x", padx=12, pady=(0, 8))

        self._row_label(dev_frame, "Наушники (выход)")
        self.out_combo = ttk.Combobox(dev_frame, state="readonly", font=("Courier New", 9))
        self.out_combo.pack(fill="x", padx=12, pady=(0, 10))

        # ── Параметры ─────────────────────────────────────────
        params = tk.Frame(self.root, bg=BG)
        params.pack(fill="x", padx=24, pady=(14, 0))

        # Задержка
        self._slider_block(params,
                           label="Задержка",
                           unit="мс",
                           var=self.delay_var,
                           from_=50, to=800, resolution=10,
                           value_fmt=lambda v: f"{int(v)} мс")

        # Громкость обратной связи
        self._slider_block(params,
                           label="Громкость DAF",
                           unit="%",
                           var=self.volume_var,
                           from_=0.0, to=2.0, resolution=0.05,
                           value_fmt=lambda v: f"{int(v*100)} %")

        # Микс live/delayed
        self._slider_block(params,
                           label="Микс live → DAF",
                           unit="",
                           var=self.mix_var,
                           from_=0.0, to=1.0, resolution=0.05,
                           value_fmt=lambda v: f"{int(v*100)} %")

        # ── Кнопка ────────────────────────────────────────────
        self.btn = tk.Button(
            self.root, text="▶  ЗАПУСТИТЬ DAF",
            bg=ACCENT, fg="#000000",
            font=("Courier New", 13, "bold"),
            bd=0, relief="flat", cursor="hand2",
            activebackground="#00b899", activeforeground="#000",
            padx=0, pady=12,
            command=self.toggle
        )
        self.btn.pack(fill="x", padx=24, pady=(22, 8))

        # ── Подсказка ─────────────────────────────────────────
        tk.Label(self.root,
                 text="Говорите в микрофон — в наушниках услышите\nсвой голос с выбранной задержкой",
                 bg=BG, fg=TEXT_DIM, font=("Courier New", 9),
                 justify="center").pack(pady=(4, 0))

        # ── Стиль combobox ────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TCombobox",
                        fieldbackground=SLIDER_BG,
                        background=SLIDER_BG,
                        foreground=TEXT,
                        selectbackground=ACCENT,
                        selectforeground="#000",
                        bordercolor=SLIDER_BG,
                        arrowcolor=ACCENT)

    def _row_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(anchor="w", padx=12, pady=(6, 2))

    def _slider_block(self, parent, label, unit, var, from_, to, resolution, value_fmt):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", pady=5)

        head = tk.Frame(frame, bg=BG)
        head.pack(fill="x")

        tk.Label(head, text=label, bg=BG, fg=TEXT,
                 font=("Courier New", 10, "bold")).pack(side="left")

        val_lbl = tk.Label(head, text=value_fmt(var.get()),
                           bg=BG, fg=ACCENT, font=("Courier New", 10, "bold"))
        val_lbl.pack(side="right")

        def on_change(v):
            val_lbl.config(text=value_fmt(float(v)))

        slider = tk.Scale(
            frame,
            variable=var,
            from_=from_, to=to,
            resolution=resolution,
            orient="horizontal",
            showvalue=False,
            bg=BG, fg=TEXT,
            troughcolor=SLIDER_BG,
            activebackground=ACCENT,
            highlightthickness=0,
            bd=0,
            command=on_change
        )
        slider.pack(fill="x", pady=(2, 0))

    # ══════════════════════════════════════════════════════════════
    #  Устройства
    # ══════════════════════════════════════════════════════════════
    def _populate_devices(self):
        inputs, outputs = [], []
        n = self.p.get_device_count()
        for i in range(n):
            info = self.p.get_device_info_by_index(i)
            name = info["name"]
            if info["maxInputChannels"] > 0:
                inputs.append((i, name))
            if info["maxOutputChannels"] > 0:
                outputs.append((i, name))

        in_names  = [f"{i}: {n}" for i, n in inputs]
        out_names = [f"{i}: {n}" for i, n in outputs]

        self.in_combo["values"]  = in_names
        self.out_combo["values"] = out_names

        # Выбрать дефолтные
        def_in  = self.p.get_default_input_device_info()["index"]
        def_out = self.p.get_default_output_device_info()["index"]

        for idx, (dev_i, _) in enumerate(inputs):
            if dev_i == def_in:
                self.in_combo.current(idx); break
        for idx, (dev_i, _) in enumerate(outputs):
            if dev_i == def_out:
                self.out_combo.current(idx); break

        self._in_devices  = inputs
        self._out_devices = outputs

    def _get_selected_devices(self):
        in_idx  = self._in_devices[self.in_combo.current()][0]  if self.in_combo.current()  >= 0 else None
        out_idx = self._out_devices[self.out_combo.current()][0] if self.out_combo.current() >= 0 else None
        return in_idx, out_idx

    # ══════════════════════════════════════════════════════════════
    #  Запуск / остановка
    # ══════════════════════════════════════════════════════════════
    def toggle(self):
        if not self.running:
            self._start()
        else:
            self._stop()

    def _start(self):
        self.running = True
        self.btn.config(text="■  ОСТАНОВИТЬ DAF", bg=DANGER,
                        activebackground="#cc3355", fg="white")
        self.status_dot.config(fg=SUCCESS)
        self.status_lbl.config(text="Активно — DAF работает", fg=SUCCESS)

        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()

    def _stop(self):
        self.running = False
        self.btn.config(text="▶  ЗАПУСТИТЬ DAF", bg=ACCENT,
                        activebackground="#00b899", fg="#000")
        self.status_dot.config(fg=TEXT_DIM)
        self.status_lbl.config(text="Остановлено", fg=TEXT_DIM)

    # ══════════════════════════════════════════════════════════════
    #  Аудио-цикл
    # ══════════════════════════════════════════════════════════════
    def _audio_loop(self):
        in_idx, out_idx = self._get_selected_devices()

        current_delay_ms  = self.delay_var.get()
        current_delay_smp = int(current_delay_ms / 1000.0 * RATE)

        # Кольцевой буфер нулей размером current_delay_smp
        buffer = collections.deque([np.float32(0.0)] * current_delay_smp)

        kwargs_in  = dict(format=FORMAT, channels=CHANNELS, rate=RATE,
                          input=True, frames_per_buffer=CHUNK)
        kwargs_out = dict(format=FORMAT, channels=CHANNELS, rate=RATE,
                          output=True, frames_per_buffer=CHUNK)
        if in_idx  is not None: kwargs_in["input_device_index"]   = in_idx
        if out_idx is not None: kwargs_out["output_device_index"] = out_idx

        try:
            s_in  = self.p.open(**kwargs_in)
            s_out = self.p.open(**kwargs_out)
        except Exception as e:
            self.root.after(0, lambda: self._show_error(str(e)))
            self.running = False
            return

        while self.running:
            # ── Динамическое обновление задержки ──────────────────
            new_delay_ms  = self.delay_var.get()
            new_delay_smp = int(new_delay_ms / 1000.0 * RATE)
            if new_delay_smp != current_delay_smp:
                diff = new_delay_smp - current_delay_smp
                if diff > 0:
                    # Задержка увеличилась — добавляем тишину в начало
                    for _ in range(diff):
                        buffer.appendleft(np.float32(0.0))
                else:
                    # Задержка уменьшилась — удаляем старые сэмплы из начала
                    drop = min(-diff, len(buffer))
                    for _ in range(drop):
                        buffer.popleft()
                current_delay_smp = new_delay_smp
            try:
                raw = s_in.read(CHUNK, exception_on_overflow=False)
            except Exception:
                break

            live = np.frombuffer(raw, dtype=np.float32).copy()

            # Извлечь CHUNK старых сэмплов (задержанные)
            delayed = np.empty(CHUNK, dtype=np.float32)
            for i in range(CHUNK):
                delayed[i] = buffer.popleft()

            # Добавить новые сэмплы в конец буфера
            buffer.extend(live.tolist())

            volume = np.float32(self.volume_var.get())
            mix    = np.float32(self.mix_var.get())

            # Финальный сигнал: микс live + delayed
            out_signal = live * (1.0 - mix) + delayed * volume * mix

            # Предохранитель от клиппинга
            np.clip(out_signal, -1.0, 1.0, out=out_signal)

            try:
                s_out.write(out_signal.tobytes())
            except Exception:
                break

        s_in.stop_stream();  s_in.close()
        s_out.stop_stream(); s_out.close()

    def _show_error(self, msg):
        self._stop()
        top = tk.Toplevel(self.root)
        top.title("Ошибка")
        top.configure(bg=BG)
        tk.Label(top, text="Ошибка аудио:", bg=BG, fg=DANGER,
                 font=("Courier New", 11, "bold")).pack(padx=20, pady=(16, 4))
        tk.Label(top, text=msg, bg=BG, fg=TEXT,
                 font=("Courier New", 9), wraplength=340).pack(padx=20, pady=(0, 16))

    def on_close(self):
        self.running = False
        self.root.destroy()


# ══════════════════════════════════════════════════════════════════
#  Точка входа
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app = DAFApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)

    # Тёмная иконка в заголовке (опционально)
    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    root.mainloop()
