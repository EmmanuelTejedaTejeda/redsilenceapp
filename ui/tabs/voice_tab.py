import os
import threading
import subprocess
import customtkinter as ctk
import tkinter.messagebox as msgbox
from modules import voice_generator

# En Windows importamos winsound para reproducción de audio nativa
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

# --- THEME CONSTANTS (Coherente con Silencio Rojo) ---
COLOR_BG = "#020202"           # Absolute Black
COLOR_CARD = "#050505"         # Deep Charcoal
COLOR_ACCENT = "#FF0000"       # Pure Neon Red
COLOR_ACCENT_HOVER = "#FF5252" # Light Red
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_SUB = "#666666"
COLOR_SUCCESS = "#00FF66"
FONT_TITLE = ("Impact", 32)
FONT_SECTION = ("Arial", 12, "bold")
FONT_MONO = ("Consolas", 11)

class VoiceTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main = main_window
        self.last_generated_path = None
        
        # Inyectar navegación
        if hasattr(self.main, 'create_nav_controls'):
            self.main.create_nav_controls(self, 4) # Índice 4 para voice_gen
            
        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Grid layout: Col 0 (Configuración - Fijo), Col 1 (Texto - Expansivo)
        self.grid_container.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_container.grid_columnconfigure(1, weight=1)
        self.grid_container.grid_rowconfigure(0, weight=1)
        
        self.setup_ui()

    def setup_ui(self):
        # ==========================
        # LEFT PANEL: CONFIGURATION
        # ==========================
        left_panel = ctk.CTkFrame(self.grid_container, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#121212")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(5, 5), pady=5)
        
        # Scrollable container inside left panel
        scroll_left = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        scroll_left.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Title
        ctk.CTkLabel(scroll_left, text="GENERACIÓN DE VOZ (TTS)", font=FONT_TITLE, text_color=COLOR_ACCENT).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(scroll_left, text="Sintetiza narraciones con el motor Gemini 2.5", font=("Arial", 11), text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(0, 20))
        
        # Model Selection
        ctk.CTkLabel(scroll_left, text="MODELO DE VOZ IA", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(5, 2))
        models = [
            "gemini-2.0-flash", 
            "gemini-2.5-flash-preview-tts", 
            "gemini-2.5-pro-preview-tts",
            "gemini-3.1-flash-tts-preview"
        ]
        self.combo_model = ctk.CTkOptionMenu(scroll_left, values=models, fg_color="#111", button_color="#222", button_hover_color=COLOR_ACCENT)
        self.combo_model.set("gemini-2.5-flash-preview-tts")
        self.combo_model.pack(fill="x", pady=(0, 15))
        
        # Voice Character Selection
        ctk.CTkLabel(scroll_left, text="PERSONAJE / VOZ", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(5, 2))
        voices = ["Charon"]
        self.combo_voice = ctk.CTkOptionMenu(scroll_left, values=voices, fg_color="#111", button_color="#222", button_hover_color=COLOR_ACCENT)
        self.combo_voice.set("Charon")
        self.combo_voice.pack(fill="x", pady=(0, 15))
        
        # Output Filename
        ctk.CTkLabel(scroll_left, text="NOMBRE DEL ARCHIVO DE SALIDA", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(5, 2))
        self.entry_filename = ctk.CTkEntry(scroll_left, placeholder_text="narracion_horror", height=32, fg_color="#080808", border_color="#181818")
        self.entry_filename.pack(fill="x", pady=(0, 5))
        self.entry_filename.insert(0, "narracion_horror")
        ctk.CTkLabel(scroll_left, text="Se guardará como archivo .wav en tu carpeta de audios", font=("Arial", 9), text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(0, 25))
        
        # Divider
        ctk.CTkFrame(scroll_left, height=1, fg_color="#1A1A1A").pack(fill="x", pady=15)
        
        # Actions Cards
        self.btn_generate = ctk.CTkButton(scroll_left, text="⚡ GENERAR NARRACIÓN ⚡", font=("Arial", 13, "bold"), height=50, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.run_generation_thread)
        self.btn_generate.pack(fill="x", pady=5)
        
        self.btn_play = ctk.CTkButton(scroll_left, text="🔊 REPRODUCIR AUDIO", font=("Arial", 12), height=40, fg_color="#1A1A1A", hover_color="#2A2A2A", state="disabled", command=self.play_audio)
        self.btn_play.pack(fill="x", pady=5)
        
        self.btn_open_folder = ctk.CTkButton(scroll_left, text="📂 ABRIR CARPETA", font=("Arial", 12), height=40, fg_color="#1A1A1A", hover_color="#2A2A2A", command=self.open_audio_folder)
        self.btn_open_folder.pack(fill="x", pady=5)

        # ==========================
        # RIGHT PANEL: TEXT INPUT
        # ==========================
        right_panel = ctk.CTkFrame(self.grid_container, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#121212")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=5)
        
        # Header Right
        hdr_right = ctk.CTkFrame(right_panel, fg_color="transparent")
        hdr_right.pack(fill="x", padx=20, pady=(15, 10))
        ctk.CTkLabel(hdr_right, text="TEXTO A CONVERTIR A AUDIO", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(side="left")
        
        # Paste Button
        btn_paste = ctk.CTkButton(hdr_right, text="📋 PEGAR", width=70, height=26, fg_color="#151515", hover_color="#252525", font=("Arial", 10, "bold"), command=self.paste_from_clipboard)
        btn_paste.pack(side="right")
        
        # Text input area
        self.txt_script = ctk.CTkTextbox(right_panel, fg_color="#020202", border_width=1, border_color="#181818", text_color="#DDD", wrap="word", font=("Arial", 12))
        self.txt_script.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.txt_script.insert("0.0", "Introduce o pega aquí la historia terrorífica que deseas narrar con el tono y dinámica de Charon...")

    def paste_from_clipboard(self):
        try:
            clipboard = self.clipboard_get()
            if clipboard:
                self.txt_script.delete("0.0", "end")
                self.txt_script.insert("0.0", clipboard)
        except Exception as e:
            msgbox.showwarning("Portapapeles Vacío", "No se pudo leer nada del portapapeles o está vacío.")

    def get_audio_folder(self):
        audio_dir = None
        if hasattr(self.main, "settings") and self.main.settings:
            audio_dir = self.main.settings.get("audio_folder_path")
        if not audio_dir:
            audio_dir = os.path.join(os.path.expanduser("~"), "Videos", "SilencioRojo", "Audio")
        return audio_dir

    def run_generation_thread(self):
        # 1. Obtener API Key y validar
        api_key = getattr(self.main, "google_api_key", "")
        if not api_key:
            self.main.update_status("⚠️ Configura tu API Key de Gemini en el menú de engranaje ⚙️", "orange")
            msgbox.showwarning("API Key Faltante", "Por favor, configura tu API Key de Gemini en los ajustes globales (icono de engranaje ⚙️).")
            return
            
        # 2. Validar texto
        text = self.txt_script.get("0.0", "end").strip()
        if not text or "Introduce o pega aquí la historia" in text:
            self.main.update_status("⚠️ Introduce un texto válido para generar", "orange")
            return
            
        # 3. Validar nombre de archivo
        filename = self.entry_filename.get().strip()
        if not filename:
            filename = "narracion_horror"
        if not filename.endswith(".wav"):
            filename += ".wav"
            
        # 4. Obtener plantillas
        voice_instructions_path = os.path.join(os.getcwd(), "config", "prompts", "voice", "voice_instructions2.txt")
        if not os.path.exists(voice_instructions_path):
            voice_instructions_path = os.path.join(os.getcwd(), "config", "prompts", "voice", "voice_instructions.txt")

        # Configurar UI
        self.btn_generate.configure(state="disabled", text="GENERANDO VOZ...")
        self.btn_play.configure(state="disabled")
        self.main.update_status("🎙️ LLAMANDO A LA API DE GEMINI 2.5 TTS...", "#FFD700")
        
        model_name = self.combo_model.get()
        audio_dir = self.get_audio_folder()
        output_file = os.path.join(audio_dir, filename)
        
        # Ejecutar en segundo plano
        def run():
            try:
                voice_generator.generate_voice(
                    text=text,
                    api_key=api_key,
                    voice_instructions_path=voice_instructions_path,
                    output_path=output_file,
                    model_name=model_name
                )
                self.after(0, lambda: self.on_generation_success(output_file))
            except Exception as e:
                self.after(0, lambda err=str(e): self.on_generation_error(err))
                
        threading.Thread(target=run, daemon=True).start()

    def on_generation_success(self, file_path):
        self.btn_generate.configure(state="normal", text="⚡ GENERAR NARRACIÓN ⚡")
        self.last_generated_path = file_path
        self.btn_play.configure(state="normal")
        self.main.update_status(f"✅ VOZ GENERADA CON ÉXITO: {os.path.basename(file_path)}", COLOR_SUCCESS)
        msgbox.showinfo("Generación Completa", f"Narración generada correctamente en:\n{file_path}")

    def on_generation_error(self, err_msg):
        self.btn_generate.configure(state="normal", text="⚡ GENERAR NARRACIÓN ⚡")
        self.main.update_status(f"❌ ERROR EN GENERACIÓN DE VOZ: {err_msg[:30]}", "red")
        msgbox.showerror("Error de Generación", f"No se pudo completar la generación de voz:\n{err_msg}")

    def play_audio(self):
        if not self.last_generated_path or not os.path.exists(self.last_generated_path):
            return
            
        if WINSOUND_AVAILABLE:
            try:
                # Reproducir audio de forma asíncrona en Windows
                winsound.PlaySound(self.last_generated_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                self.main.update_status("🔊 REPRODUCIENDO AUDIO...", COLOR_SUCCESS)
            except Exception as e:
                msgbox.showerror("Error de Reproducción", f"No se pudo reproducir el archivo:\n{e}")
        else:
            # Fallback en otros sistemas
            try:
                if os.name == 'nt':
                    os.startfile(self.last_generated_path)
                else:
                    subprocess.run(["xdg-open", self.last_generated_path])
            except Exception as e:
                msgbox.showerror("Error de Reproducción", f"No se pudo abrir el archivo:\n{e}")

    def open_audio_folder(self):
        folder = self.get_audio_folder()
        if os.path.exists(folder):
            try:
                if os.name == 'nt':
                    os.startfile(folder)
                else:
                    subprocess.run(["xdg-open", folder])
            except Exception as e:
                msgbox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")
        else:
            msgbox.showwarning("Carpeta No Existe", f"La carpeta de audios no existe todavía:\n{folder}")

    def get_state(self):
        return {
            "script_text": self.txt_script.get("0.0", "end").strip(),
            "output_filename": self.entry_filename.get().strip(),
            "model": self.combo_model.get(),
            "voice": self.combo_voice.get()
        }

    def restore_state(self, state):
        if not state:
            return
        script_text = state.get("script_text", "")
        if script_text:
            self.txt_script.delete("0.0", "end")
            self.txt_script.insert("0.0", script_text)
            
        filename = state.get("output_filename", "narracion_horror")
        self.entry_filename.delete(0, "end")
        self.entry_filename.insert(0, filename)
        
        self.combo_model.set(state.get("model", "gemini-2.5-flash-preview-tts"))
        self.combo_voice.set(state.get("voice", "Charon"))

    def focus_set(self):
        super().focus_set()
        # Sincronizar estado global
        self.main.update_status("VOZ GENERATION TTS READY", COLOR_TEXT_SUB)
