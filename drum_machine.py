# drum_machine.py  (arquivo único)
import os
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pygame
from db_backend import init_db, save_groove, load_all_grooves, load_groove_by_id, delete_groove, DB_FILE
import sys
import requests
import logging
import sounddevice as sd
import soundfile as sf
import numpy as np

# Configuração do logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app_debug.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

VERSION = "1.0.0"
UPDATE_URL = "https://seusite.com/drum_machine_latest.exe"

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

SAMPLES_PATH = resource_path("samples")

# ---------------- CONFIG ---------------- #
INSTRUMENTS = {
    "kick": ["Attack Kick 15.wav", "Attack Kick 46.wav", "Downstream Kick 04.wav", "FL 808 Kick.wav", "FL 909 Kick Alt.wav", "FL 909 Kick.wav", "FL Basic Kick.wav"],
    "snare": ["FL 808 Snare.wav", "Attack Snare 03.wav", "Attack Snare 26.wav", "FL Grv Snareclap 30.wav", "FL 808 Snare.wav", "FL 909 Snare.wav", "FL 909 Rim.wav"],
    "hat": ["Attack Hat 06.wav", "Attack OHat 02.wav"],
    "tom": ["FL 808 Tom.wav", "FL 909 Tom.wav"],
}

DISPLAY_NAMES = {
    "kick": "Bumbo",
    "snare": "Caixa",
    "hat": "Hi-hat",
    "tom": "Tom"
}

NUM_STEPS = 16

PRESETS = {
    "Reggae": {
        "kick":  [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
        "snare": [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],
        "hat":   [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
        "tom":   [0]*16
    },
    "Rock Basico": {
        "kick":  [1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0],
        "snare": [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0],
        "hat":   [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,0],
        "tom":   [0]*16
    }
}

# ---------------- INIT PYGAME ---------------- #
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
except Exception as e:
    logging.exception("Erro inicializando pygame.mixer: %s", e)

# carregar samples (se existirem)
samples = {}
for inst, files in INSTRUMENTS.items():
    samples[inst] = []
    for f in files:
        path = os.path.join(SAMPLES_PATH, inst, f)
        if os.path.exists(path):
            try:
                samples[inst].append(pygame.mixer.Sound(path))
            except pygame.error as e:
                logging.warning("Erro ao carregar sample %s: %s", path, e)
        else:
            logging.info("Aviso: sample não encontrado: %s", path)

# ---------------- DRUM MACHINE ---------------- #
class DrumMachine:
    def __init__(self, root):
        logging.info("Iniciando DrumMachine...")
        self.root = root
        self.root.title("Drum Machine Victor S.")
        self.root.columnconfigure(0, weight=1)

        # Sequencer / playback
        self.sequence = {inst: [0]*NUM_STEPS for inst in INSTRUMENTS.keys()}
        self.bpm = tk.IntVar(value=100)
        self.is_playing = False
        self.stop_event = threading.Event()
        self.thread = None

        # Looper (gravações do usuário)
        self.loop_samplerate = 44100
        self.loop_channels = 1            # default mono para gravações de instrumento
        self.loop_dir = os.path.join(os.path.abspath("."), "loops")
        os.makedirs(self.loop_dir, exist_ok=True)

        self.loop_duration_var = tk.IntVar(value=5)   # controlado via UI (spinbox) — evita popups
        self.num_tracks = 3
        self.tracks = []
        for i in range(self.num_tracks):
            file_path = os.path.join(self.loop_dir, f"user_loop_{i+1}.wav")
            self.tracks.append({
                "data": None,
                "file": file_path,
                "sound": None,
                "channel": None,
                "btn_record": None,
                "btn_play": None,
                "orig_record_bg": None,
                "orig_play_bg": None
            })

        # Metronomo / click
        self.metronome_enabled = tk.BooleanVar(value=False)
        self.click_sound = None
        click_path = os.path.join(SAMPLES_PATH, "Percussion", "Attack Blip 03.wav")
        if os.path.exists(click_path):
            try:
                self.click_sound = pygame.mixer.Sound(click_path)
            except Exception as e:
                logging.warning("Erro ao carregar click.wav: %s", e)

        # música importada
        self.music_file = None

        self._build_ui()
        init_db()
        logging.info("DrumMachine inicializada com sucesso!")

    def _build_ui(self):
        logging.debug("Construindo interface gráfica...")

        # Presets (mantive funcionalidade)
        preset_frame = ttk.Frame(self.root, padding=5)
        preset_frame.pack(fill="x", padx=5, pady=4)
        ttk.Label(preset_frame, text="Presets:").pack(side="left")
        self.preset_var = tk.StringVar()
        preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var, values=list(PRESETS.keys()))
        preset_combo.pack(side="left", padx=5)
        ttk.Button(preset_frame, text="Carregar", command=self.load_preset).pack(side="left", padx=5)

        # ---------------- BPM ---------------- #
        bpm_frame = ttk.Frame(self.root, padding=5)
        bpm_frame.pack(fill="x", padx=5, pady=4)
        ttk.Label(bpm_frame, text="BPM:").pack(side="left")
        self.bpm_label = ttk.Label(bpm_frame, text=str(self.bpm.get()))
        self.bpm_label.pack(side="left", padx=6)
        bpm_scale = ttk.Scale(
            bpm_frame, from_=40, to=200,
            variable=self.bpm, orient="horizontal",
            command=self.update_bpm_label
        )
        bpm_scale.pack(side="left", padx=5, fill="x", expand=True)

        # ---------------- Metronomo ---------------- #
        metro_frame = ttk.Frame(self.root, padding=5)
        metro_frame.pack(fill="x", padx=5, pady=4)
        ttk.Checkbutton(metro_frame, text="Som do BPM (Metrônomo)", variable=self.metronome_enabled).pack(side="left", padx=5)

        # ---------------- Timbres ---------------- #
        self.timbre_vars = {}
        timbre_frame = ttk.Frame(self.root, padding=5)
        timbre_frame.pack(fill="x", padx=5, pady=4)
        for inst, t_list in INSTRUMENTS.items():
            ttk.Label(timbre_frame, text=DISPLAY_NAMES.get(inst, inst)).pack(side="left", padx=3)
            options = [f"{DISPLAY_NAMES.get(inst, inst)} {i+1}" for i in range(len(t_list))]
            var = tk.StringVar(value=options[0])
            combo = ttk.Combobox(timbre_frame, textvariable=var, values=options, width=12)
            combo.pack(side="left", padx=3)
            self.timbre_vars[inst] = var

        # ---------------- DB ---------------- #
        db_frame = ttk.Frame(self.root, padding=5)
        db_frame.pack(fill="x", padx=5, pady=4)
        ttk.Label(db_frame, text="Grooves Salvos:").pack(side="left")
        self.db_list = ttk.Combobox(db_frame, values=[], width=30)
        self.db_list.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(db_frame, text="Salvar Preset", command=self.save_to_db).pack(side="left", padx=3)
        ttk.Button(db_frame, text="Tocar Preset", command=self.load_from_db).pack(side="left", padx=3)
        ttk.Button(db_frame, text="Excluir Preset", command=self.delete_from_db).pack(side="left", padx=3)
        ttk.Button(db_frame, text="Atualizar Lista", command=self.refresh_db_list).pack(side="left", padx=3)

        # ---------------- Sequencer ---------------- #
        self.grid_frame = ttk.Frame(self.root, padding=5)
        self.grid_frame.pack(fill="both", expand=True, padx=5, pady=6)
        self.step_buttons = {}
        for row, inst in enumerate(INSTRUMENTS.keys()):
            self.grid_frame.rowconfigure(row, weight=1)
            tk.Label(self.grid_frame, text=DISPLAY_NAMES.get(inst, inst), width=10, anchor="e").grid(row=row, column=0, padx=5, pady=2)
            self.step_buttons[inst] = []
            for col in range(NUM_STEPS):
                btn = tk.Button(self.grid_frame, width=2, height=1, relief="raised", bg="white",
                                command=lambda i=inst, c=col: self.toggle_step(i, c))
                btn.grid(row=row, column=col+1, padx=2, pady=2, sticky="nsew")
                self.step_buttons[inst].append(btn)
            for col in range(NUM_STEPS+1):
                self.grid_frame.columnconfigure(col, weight=1)

        # ---------------- Controls principais ---------------- #
        ctrl_frame = ttk.Frame(self.root, padding=5)
        ctrl_frame.pack(fill="x", padx=5, pady=6)
        ttk.Button(ctrl_frame, text="▶ Play Loop", command=self.start_loop).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="⏹ Stop", command=self.stop).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="🎵 Importar Música", command=self.import_music).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="▶ Tocar Música", command=self.play_music_only).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="▶ Música + Instrumentos", command=self.play_music_with_instruments).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="💾 Extrair Preset", command=self.save_groove).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="📂 Importar Preset", command=self.load_groove).pack(side="left", padx=5)

        # ---------------- Looper Independente ---------------- #
        loop_frame = ttk.LabelFrame(self.root, text="Looper", padding=6)
        loop_frame.pack(fill="x", padx=5, pady=6)

        # Loop length control (sem popups)
        length_frame = ttk.Frame(loop_frame)
        length_frame.pack(fill="x", pady=3)
        ttk.Label(length_frame, text="Loop length (s):").pack(side="left")
        spin = tk.Spinbox(length_frame, from_=1, to=120, textvariable=self.loop_duration_var, width=5)
        spin.pack(side="left", padx=6)

        # per-track controls
        for i, track in enumerate(self.tracks):
            frame = ttk.Frame(loop_frame, padding=3)
            frame.pack(fill="x", pady=2)

            # Record button (do not set bg here to preserve platform default)
            btn_record = tk.Button(frame, text=f"🎙 Gravar Pista {i+1}", command=lambda idx=i: self.record_track(idx))
            btn_record.pack(side="left", padx=3)

            # Play button
            btn_play = tk.Button(frame, text=f"▶ Play Pista {i+1}", command=lambda idx=i: self.play_track(idx))
            btn_play.pack(side="left", padx=3)

            # Stop button
            btn_stop = tk.Button(frame, text=f"⏹ Stop Pista {i+1}", command=lambda idx=i: self.stop_track(idx))
            btn_stop.pack(side="left", padx=3)

            # store buttons and original bg colors
            track["btn_record"] = btn_record
            track["btn_play"] = btn_play
            try:
                track["orig_record_bg"] = btn_record.cget("bg")
                track["orig_play_bg"] = btn_play.cget("bg")
            except Exception:
                track["orig_record_bg"] = None
                track["orig_play_bg"] = None

        self.refresh_db_list()

    # ---------------- Gravação / Looper ---------------- #
    def record_track(self, idx):
        """Inicia a gravação de uma pista em thread. Não usa popups (usa spinbox para duração)."""
        duration = int(self.loop_duration_var.get())
        track = self.tracks[idx]
        btn = track["btn_record"]

        # desativa botão e muda texto/cor para indicar gravação
        def ui_start():
            try:
                btn.config(state="disabled")
                btn.config(text=f"● Gravando Pista {idx+1}")
                if track["orig_record_bg"] is not None:
                    btn.config(bg="tomato")
            except Exception:
                pass

        def ui_end():
            try:
                btn.config(state="normal")
                btn.config(text=f"🎙 Gravar Pista {idx+1}")
                if track["orig_record_bg"] is not None:
                    btn.config(bg=track["orig_record_bg"])
            except Exception:
                pass

        self.root.after(0, ui_start)

        # grava em thread para não travar UI
        t = threading.Thread(target=self._record_track_thread, args=(idx, duration, ui_end), daemon=True)
        t.start()

    def _record_track_thread(self, idx, duration, ui_end_callback):
        """Thread que grava e salva o arquivo do track idx."""
        track = self.tracks[idx]
        try:
            logging.info("Iniciando gravação piste %d por %ds", idx+1, duration)
            frames = int(duration * self.loop_samplerate)
            audio = sd.rec(frames, samplerate=self.loop_samplerate, channels=self.loop_channels, dtype='float32')
            sd.wait()  # blocking but we are em thread

            # se primeiro take, salva direto; se já existe, mix (overdub)
            if track["data"] is None:
                track["data"] = audio
            else:
                # mix: soma na menor quantidade de frames para evitar shape mismatch
                min_len = min(track["data"].shape[0], audio.shape[0])
                mix = track["data"][:min_len] + audio[:min_len]
                track["data"] = np.clip(mix, -1.0, 1.0)

            # salvar com timestamp para evitar sobrescrita e facilitar debug
            ts = int(time.time())
            fname = os.path.join(self.loop_dir, f"user_loop_{idx+1}_{ts}.wav")
            track["file"] = fname
            sf.write(fname, track["data"], self.loop_samplerate, subtype='PCM_16')
            logging.info("Gravação salva em %s", fname)

            # carrega no pygame para tocar
            try:
                track["sound"] = pygame.mixer.Sound(fname)
            except Exception as e:
                logging.exception("Falha ao carregar loop no pygame: %s", e)
                track["sound"] = None

        except Exception as e:
            logging.exception("Erro ao gravar pista %d: %s", idx+1, e)
        finally:
            # atualizar UI (volta cor/texto)
            self.root.after(0, ui_end_callback)
            logging.info("Gravação da pista %d finalizada", idx+1)

    def play_track(self, idx):
        """Toca a pista idx em loop (infinito)"""
        track = self.tracks[idx]
        if not track.get("sound"):
            # tenta carregar a partir do arquivo se existir
            try:
                if os.path.exists(track["file"]):
                    track["sound"] = pygame.mixer.Sound(track["file"])
                else:
                    logging.info("Nenhum loop gravado na pista %d", idx+1)
                    return
            except Exception as e:
                logging.exception("Erro ao carregar som da pista %d: %s", idx+1, e)
                return

        try:
            track["channel"] = track["sound"].play(loops=-1)
            if track["orig_play_bg"] is not None:
                track["btn_play"].config(bg="lightgreen")
        except Exception as e:
            logging.exception("Erro ao tocar pista %d: %s", idx+1, e)

    def stop_track(self, idx):
        track = self.tracks[idx]
        try:
            if track.get("channel"):
                track["channel"].stop()
            if track["orig_play_bg"] is not None:
                track["btn_play"].config(bg=track["orig_play_bg"])
        except Exception as e:
            logging.exception("Erro ao parar pista %d: %s", idx+1, e)

    # ---------------- Funcionalidades Sequencer ---------------- #
    def toggle_step(self, inst, col):
        self.sequence[inst][col] = 1 - self.sequence[inst][col]
        self.update_button_color(inst, col)

    def update_button_color(self, inst, col, active_step=None):
        btn = self.step_buttons[inst][col]
        if col == active_step:
            btn.config(bg="red")
        else:
            btn.config(bg="green" if self.sequence[inst][col] else "white")

    # ---------------- Loop principal (drum machine) ---------------- #
    def loop(self):
        while not self.stop_event.is_set():
            beat_duration = 60 / self.bpm.get() / 4
            for step in range(NUM_STEPS):
                if self.stop_event.is_set():
                    break
                for inst, pattern in self.sequence.items():
                    if pattern[step] == 1 and samples.get(inst):
                        try:
                            idx_str = self.timbre_vars[inst].get().split()[-1]
                            idx = int(idx_str) - 1
                            if 0 <= idx < len(samples[inst]):
                                samples[inst][idx].play()
                        except Exception as e:
                            logging.exception("Erro ao tocar %s: %s", inst, e)

                if self.metronome_enabled.get() and self.click_sound:
                    if step % 4 == 0:
                        try:
                            self.click_sound.play()
                        except Exception as e:
                            logging.exception("Erro tocando click: %s", e)

                self.highlight_step(step)
                time.sleep(beat_duration)
            self.highlight_step(-1)

    def highlight_step(self, step):
        def update():
            for inst in INSTRUMENTS.keys():
                for col in range(NUM_STEPS):
                    self.update_button_color(inst, col, active_step=step if col == step else None)
        self.root.after(0, update)

    # ---------------- Controles ---------------- #
    def start_loop(self):
        if self.is_playing:
            return
        self.is_playing = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.is_playing = False
        self.highlight_step(-1)
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    # ---------------- Music Functions ---------------- #
    def import_music(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.ogg")])
        if not file_path:
            return
        self.music_file = file_path
        try:
            pygame.mixer.music.load(self.music_file)
            bpm = self.detect_bpm(self.music_file)
            messagebox.showinfo("Música carregada", f"Arquivo carregado!\nBPM estimado: {bpm}")
        except Exception as e:
            logging.exception("Erro carregando música: %s", e)
            messagebox.showerror("Erro", f"Não foi possível carregar o arquivo: {e}")

    def play_music_only(self):
        if not self.music_file:
            messagebox.showwarning("Aviso", "Nenhuma música importada!")
            return
        pygame.mixer.music.play()

    def play_music_with_instruments(self):
        if not self.music_file:
            messagebox.showwarning("Aviso", "Nenhuma música importada!")
            return
        pygame.mixer.music.play()
        self.start_loop()

    def detect_bpm(self, file_path):
        try:
            import librosa
            y, sr = librosa.load(file_path, mono=True)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return int(tempo)
        except Exception as e:
            logging.info("Detect BPM failed: %s", e)
            return 0

    # ---------------- JSON / DB ---------------- #
    def save_groove(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json")
        if not file_path:
            return
        data = {"sequence": self.sequence,
                "timbres": {inst: self.timbre_vars[inst].get() for inst in self.timbre_vars}}
        with open(file_path, "w") as f:
            json.dump(data, f)
        messagebox.showinfo("Sucesso", "Groove salvo em JSON!")

    def load_groove(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
        with open(file_path, "r") as f:
            data = json.load(f)
        self.sequence = data["sequence"]
        for inst, val in data["timbres"].items():
            self.timbre_vars[inst].set(val)
        for inst in INSTRUMENTS.keys():
            for col in range(NUM_STEPS):
                self.update_button_color(inst, col)

    def save_to_db(self):
        logging.debug("Chamando save_to_db()")
        name = simpledialog.askstring("Nome do Groove", "Digite o nome do groove:")
        if not name:
            logging.warning("Nome do groove não informado. Cancelando operação.")
            return
        try:
            save_groove(name, self.bpm.get(),
                        {inst: self.sequence[inst].copy() for inst in INSTRUMENTS.keys()},
                        {inst: self.timbre_vars[inst].get() for inst in self.timbre_vars})
            messagebox.showinfo("Sucesso", f"Groove '{name}' salvo no banco!")
            self.refresh_db_list()
        except Exception as e:
            logging.exception("Erro ao salvar no DB: %s", e)
            messagebox.showerror("Erro", f"Não foi possível salvar o groove: {e}")

    def refresh_db_list(self):
        try:
            grooves = load_all_grooves()
            self.db_list["values"] = [f"[{gid}] {name} - {bpm} BPM" for gid, name, bpm in grooves]
        except Exception as e:
            logging.exception("Erro ao listar grooves: %s", e)

    def load_from_db(self):
        logging.debug("Chamando load_from_db()")
        value = self.db_list.get()
        if not value:
            return
        groove_id = int(value.split("]")[0][1:])
        data, bpm = load_groove_by_id(groove_id)
        if not data:
            logging.debug("Nenhum dado retornado do DB para id %s", groove_id)
            return
        self.sequence = {inst: data["sequence"][inst].copy() for inst in INSTRUMENTS.keys()}
        for inst, val in data["timbres"].items():
            self.timbre_vars[inst].set(val)
        for inst in INSTRUMENTS.keys():
            for col in range(NUM_STEPS):
                self.update_button_color(inst, col)
        self.bpm.set(bpm)

    def delete_from_db(self):
        value = self.db_list.get()
        if not value:
            return
        groove_id = int(value.split("]")[0][1:])
        delete_groove(groove_id)
        messagebox.showinfo("Sucesso", "Groove deletado!")
        self.refresh_db_list()

    def load_preset(self):
        preset_name = self.preset_var.get()
        if preset_name not in PRESETS:
            return
        preset = PRESETS[preset_name]
        for inst in INSTRUMENTS.keys():
            self.sequence[inst] = preset.get(inst, [0]*NUM_STEPS).copy()
        for inst in INSTRUMENTS.keys():
            for col in range(NUM_STEPS):
                self.update_button_color(inst, col)

    def update_bpm_label(self, event=None):
        self.bpm_label.config(text=str(self.bpm.get()))

# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    init_db()
    print("DB file location:", os.path.abspath(DB_FILE))
    root = tk.Tk()
    app = DrumMachine(root)
    root.mainloop()
