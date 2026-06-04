import os
import random
import threading
import subprocess
import webbrowser
import json
import customtkinter as ctk
from tkinter import filedialog
import config.prompts as prompts_cfg
from modules.video_render import render_final_video
from modules import gemini_client
from ui.narrative_editor import NarrativeEditor
from ui.tabs.media_tab import MediaTab
from ui.components.sidebar import Sidebar
from ui.tabs.concept_tab import ConceptTab
from ui.tabs.visual_tab import VisualTab
from ui.tabs.long_tab import LongTab
from ui.tabs.voice_tab import VoiceTab
from core.project_manager import ProjectManager
from ui.tabs.cover_tab import CoverTab
from ui.config_editor import ConfigEditor
from ui.image_converter import ImageConverter

from core.utils import get_resource_path
from core.math_logic import calculate_visual_segments

# --- DISEÑO & ESTÉTICA PRO (NEON HORROR) ---
ctk.set_appearance_mode("Dark")

# PALETA DE COLORES "SILENCIO ROJO CORE v10"
COLOR_BG = "#020202"           # Absolute Black
COLOR_PANEL = "#050505"        # Deep Charcoal
COLOR_ACCENT = "#FF0000"       # Pure Neon Red
COLOR_ACCENT_HOVER = "#FF5252" # Light Red
COLOR_BORDER = "#121212"       # Subtle Borders
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_DIM = "#555555"
COLOR_SUCCESS = "#00FF66"

FONT_MAIN = ("Inter", 13) 
FONT_BOLD = ("Inter", 13, "bold")
FONT_TITLE = ("Impact", 32)
FONT_MONO = ("Consolas", 12)

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SILENCIO ROJO | STUDIO CORE v10.0")
        self.geometry("1400x900")
        self.configure(fg_color=COLOR_BG)
        self.resizable(True, True)
        self.after(0, lambda: self.state('zoomed'))

        # Variables de estado
        self.audio_path = ""
        self.images_paths = []
        self.cover_path = ""
        self.generated_story_context = "" # DEPRECATED: Use Tab state directly
        self.latest_visual_prompts = ""
        self.latest_cover_prompt = "" 
        self.current_trama_cache = ""

        # Project Core
        self.project_manager = ProjectManager(get_resource_path("projects"))
        self.current_project_id = None
        
        # Cargar configuración primero
        self.settings_file = "config/settings.json"
        self.settings = self.load_settings()
        
        # Rutas dinámicas para portabilidad
        base_user_dir = os.path.join(os.path.expanduser("~"), "Videos", "SilencioRojo")
        self.ruta_drive = self.settings.get("videos_folder_path", os.path.join(base_user_dir, "Raw"))
        self.music_folder = self.settings.get("audio_folder_path", os.path.join(base_user_dir, "Musica"))
        self.img_download_folder = self.settings.get("images_folder_path", os.path.join(base_user_dir, "Imagenes"))
        
        self.downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self.assets_audio_folder = get_resource_path(os.path.join("assets", "audio"))
        self.prompt_file = "master_prompt.txt"
        
        self.current_music_path = None
        self.preview_process = None
        
        self.google_api_key = self.settings.get("google_api_key", "")
        self.groq_api_key = self.settings.get("groq_api_key", "")
        self.pexels_api_key = self.settings.get("pexels_api_key", "")
        self.llm_provider = self.settings.get("llm_provider", "gemini")
        
        # Inicialización de Core (Asegurar que existan las rutas)
        self.check_prompt_file()
        for folder in [self.img_download_folder, self.ruta_drive, self.music_folder]:
            if not os.path.exists(folder):
                try: os.makedirs(folder)
                except: pass

        # 1. ORDEN DE LEY: Configurar Carriles del Grid (Single Row/Col + Offset)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 2. Inicialización de Core y Componentes
        self.init_sidebar()
        self.init_main_area()
        self.after(30000, self.auto_save_loop)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 5. UI CACHE & PRE-WARM SYSTEM (High-Speed Navigation)
        self.view_cache = {}
        self.active_view = None
        self.dashboard_view = None
        
        # INICIALIZAR FLUJO (Secuencial: Dashboard -> Preload -> Restore Data)
        self.after(100, lambda: self.show_view("dashboard"))
        self.after(1000, self.run_startup_sequence)

    def run_startup_sequence(self):
        """Ejecuta la precarga y luego restaura la sesión guardada"""
        self.preload_all_views()
        self.auto_load_session()

    def preload_all_views(self):
        """Ejecuta la precarga y luego restaura la sesión guardada"""
        modules = ["concept", "visuals", "cover", "voice_gen", "media", "long_form"]
        for mod in modules:
            if mod not in self.view_cache:
                self.show_view(mod, silent=True)
        # Asegurarnos de quedar en Dashboard
        self.show_view("dashboard")

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_settings_to_file(self):
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        self.settings["google_api_key"] = self.google_api_key
        self.settings["groq_api_key"] = self.groq_api_key
        self.settings["pexels_api_key"] = self.pexels_api_key
        self.settings["llm_provider"] = self.llm_provider
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f)
            
    # --- AUTO-SAVE LOGIC ---
    def auto_load_session(self):
        latest = self.project_manager.get_latest_project()
        if latest:
            print(f"Loading session: {latest}")
            data = self.project_manager.load_project(latest)
            if data:
                self.restore_state(data)
                self.current_project_id = latest
                self.update_status(f"SESIÓN RESTAURADA: {latest}", COLOR_SUCCESS)
            else:
                self.current_project_id = self.project_manager.create_project("New_Session")
        else:
             self.current_project_id = self.project_manager.create_project("New_Session")

    def auto_save_loop(self):
        self.save_current_state()
        self.after(30000, self.auto_save_loop) # 30s Loop

    def on_close(self):
        print("Saving session before close...")
        self.save_current_state()
        self.destroy()

    def save_current_state(self):
        try:
            # 1. Gather state from all modules in CACHE
            state = {
                "concept": self.view_cache["concept"].get_state() if "concept" in self.view_cache else {},
                "visual": {
                     "prompts": self.latest_visual_prompts
                },
                "cover": {
                     "prompt": self.latest_cover_prompt
                },
                "voice": self.view_cache["voice_gen"].get_state() if "voice_gen" in self.view_cache else {},
                "media": self.view_cache["media"].get_state() if "media" in self.view_cache else {},
                "long_form": self.view_cache["long_form"].get_state() if "long_form" in self.view_cache else {}
            }
            
            # Use title from Concept Tab cache if available
            title = state["concept"].get("trama", "")[:20] if state["concept"].get("trama") else "Untitled"
            
            self.project_manager.save_project(state, self.current_project_id)
            # print(f"Auto-saved to {self.current_project_id}")
            
        except Exception as e:
            print(f"Auto-save error: {e}")

    def restore_state(self, data):
        # 1. Concept (Si existe en caché lo inyectamos)
        if "concept" in data:
            if "concept" in self.view_cache:
                self.view_cache["concept"].restore_state(data["concept"])
            self.current_trama_cache = data["concept"].get("trama", "")
            
        # 2. Visual
        if "visual" in data:
            self.latest_visual_prompts = data["visual"].get("prompts", "")
            
        # 3. Media
        if "media" in data and "media" in self.view_cache:
            self.view_cache["media"].restore_state(data["media"])

        # 4. Long Form
        if "long_form" in data and "long_form" in self.view_cache:
            self.view_cache["long_form"].restore_state(data["long_form"])
            
        # 5. Voice Gen
        if "voice" in data and "voice_gen" in self.view_cache:
            self.view_cache["voice_gen"].restore_state(data["voice"])

    # ... (Rest of init_sidebar and other existing methods) ... For brevity, showing replacement up to init_main_area or so if needed, but tool replaces contiguous block.
    # Since I need to inject methods and modify __init__, I will replace the class definition start.



    def init_sidebar(self):
        try:
            # USAR PLACE: Garantiza ancho absoluto
            self.sidebar_component = Sidebar(self, main_window=self)
            self.sidebar_component.place(x=0, y=0, relheight=1)
        except Exception as e:
            print(f">>> [SIDEBAR CRITICAL ERROR]: {e}")

    def init_main_area(self):
        try:
            # Main Content Container (Right side of Sidebar)
            # padx=(60,0) deja el espacio exacto para la barra lateral que está en .place()
            self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.main_frame.grid(row=0, column=0, sticky="nsew", padx=(60, 0), pady=0)
            self.main_frame.grid_rowconfigure(0, weight=1)
            self.main_frame.grid_columnconfigure(0, weight=1)

            # Dynamic Content Area
            self.content_area = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            self.content_area.grid(row=0, column=0, sticky="nsew", padx=2, pady=2) # Reducción de margen crítico
            self.content_area.grid_rowconfigure(0, weight=1)
            self.content_area.grid_columnconfigure(0, weight=1)
        except Exception as e:
            print(f">>> [MAIN AREA ERROR]: {e}")

        # Note: view_cache is now initialized in __init__ for the pre-warm system
        
        # --- STATUS BAR (Bottom) ---
        self.status_bar = ctk.CTkFrame(self.main_frame, height=35, fg_color="#050505", corner_radius=0, border_width=1, border_color="#111")
        self.status_bar.grid(row=1, column=0, sticky="ew")
        
        # System Health Indicators
        self.status_icon = ctk.CTkLabel(self.status_bar, text="🟢", font=("Arial", 10))
        self.status_icon.pack(side="left", padx=(15, 5))
        
        self.status_lbl = ctk.CTkLabel(self.status_bar, text="SYSTEM ONLINE | SILENCIO ROJO CORE", font=("Consolas", 10), text_color="#444")
        self.status_lbl.pack(side="left")
        
        # Right stats
        stats_frame = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        stats_frame.pack(side="right", padx=20)
        
        if self.llm_provider == "groq":
            provider_display = "GROQ (LLAMA 3.3)"
        else:
            provider_display = getattr(gemini_client, "DEFAULT_MODEL", "UNKNOWN").upper()
            
        ctk.CTkLabel(stats_frame, text=f"AI CORE: {provider_display}", font=("Arial", 9, "bold"), text_color="#2E7D32").pack(side="left", padx=10)
        ctk.CTkLabel(stats_frame, text="RENDER: IDLE", font=("Arial", 9, "bold"), text_color="#444").pack(side="left", padx=10)
        ctk.CTkLabel(stats_frame, text="V10.0", font=("Impact", 12), text_color=COLOR_ACCENT).pack(side="left", padx=(10, 0))
        
        # Animations
        self.after(100, self.animate_entrance)
        self.animate_status_pulse()

    def animate_entrance(self):
        # Sutil efecto de "Deslizar y aparecer" para el contenido principal
        self.main_frame.configure(border_color=COLOR_ACCENT, border_width=2)
        self.after(300, lambda: self.main_frame.configure(border_color=COLOR_BG, border_width=0))

    def animate_status_pulse(self):
        try:
            current_text = self.status_icon.cget("text")
            if current_text == "🟢":
                self.status_icon.configure(text="●", text_color=COLOR_SUCCESS)
            else:
                self.status_icon.configure(text="🟢", text_color="#FFFFFF")
                
            self.after(800, self.animate_status_pulse)
        except:
            pass

    def show_view(self, view_name, silent=False):
        # 1. Crear la vista si no existe (Backup por si falla la pre-carga)
        if view_name not in self.view_cache:
            if view_name == "dashboard":
                self.view_cache["dashboard"] = self.create_dashboard_view()
            elif view_name == "concept":
                self.view_cache["concept"] = ConceptTab(self.content_area, main_window=self)
            elif view_name == "visuals":
                self.view_cache["visuals"] = VisualTab(self.content_area, main_window=self)
            elif view_name == "cover":
                self.view_cache["cover"] = CoverTab(self.content_area, main_window=self)
            elif view_name == "media":
                self.view_cache["media"] = MediaTab(self.content_area, main_window=self)
            elif view_name == "voice_gen":
                self.view_cache["voice_gen"] = VoiceTab(self.content_area, main_window=self)
            elif view_name == "long_form":
                self.view_cache["long_form"] = LongTab(self.content_area, main_window=self)
            
            # Ubicar en el grid fijo (todas las capas existen simultáneamente)
            if view_name in self.view_cache:
                self.view_cache[view_name].grid(row=0, column=0, sticky="nsew")

        # 2. EL TRUCO DE VELOCIDAD: Levantar la capa (Z-order)
        # Sin recálculos de layout, solo movimiento de memoria de video.
        if view_name in self.view_cache:
            target_view = self.view_cache[view_name]
            target_view.lift()
            
            # --- NEW: TRIGGER AUTO-SYNC ---
            if not silent:
                target_view.focus_set()
            
            # 3. Solo animar si no es precarga silenciosa
            if not silent:
                # Opcional: Podríamos añadir un flash de opacidad, 
                # pero evitamos .place() para no romper el layout responsivo.
                pass

    def animate_view_entrance(self):
        # Desactivado para prevenir conflictos de geometría (Error de Caja Flotante)
        try:
            v_title = self.sidebar_component.current_view if hasattr(self, 'sidebar_component') else "SYSTEM"
            self.update_status(f"⚡ {v_title.upper()} READY", "#00E676")
        except: 
            pass

    def create_dashboard_view(self):
        # PROJECT OVERVIEW DASHBOARD
        frm = ctk.CTkFrame(self.content_area, fg_color="transparent")
        
        # Header
        ctk.CTkLabel(frm, text="COMMAND CENTER", font=("Impact", 48), text_color="#222").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(frm, text="PANEL INTERACTIVO DE CONTROL", font=("Arial", 12), text_color="#555").pack(anchor="w", pady=(0, 30))
        
        # Interactive Controls Container
        controls_frame = ctk.CTkFrame(frm, fg_color="transparent")
        controls_frame.pack(fill="x", pady=20)
        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(1, weight=1)
        controls_frame.grid_columnconfigure(2, weight=1)
        
        # Card 1: GESTIÓN (Interactive)
        c1 = self.create_interactive_card(controls_frame, 0, "📁", "PROYECTO")
        ctk.CTkButton(c1, text="NUEVA HISTORIA ✨", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.action_new_story).pack(pady=(10,5), padx=20, fill="x")
        ctk.CTkButton(c1, text="DIRECTORIO LOCAL 📂", fg_color="#222", hover_color="#333", command=self.action_open_dir).pack(pady=5, padx=20, fill="x")

        # Card 2: AI MOTOR (Interactive)
        c2 = self.create_interactive_card(controls_frame, 1, "🧠", "MOTOR INTELIGENCIA")
        model_name = getattr(gemini_client, "DEFAULT_MODEL", "gemini-2.5-flash")
        
        # Dropdown para cambiar modelo (Incluyendo v2.5 según solicitud)
        models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp", "gemini-2.5-flash", "gemini-2.5-pro"]
        if model_name not in models: models.append(model_name)
        
        dropdown = ctk.CTkOptionMenu(c2, values=models, command=self.on_model_change, fg_color="#222", button_color="#333", button_hover_color=COLOR_ACCENT)
        dropdown.set(model_name)
        dropdown.pack(pady=(10, 5), padx=20, fill="x")
        
        ctk.CTkLabel(c2, text="ESTADO: ONLINE 🟢", font=("Arial", 10, "bold"), text_color=COLOR_SUCCESS).pack(pady=5)

        # Card 3: SISTEMA / RENDER (Interactive)
        c3 = self.create_interactive_card(controls_frame, 2, "⚙️", "SISTEMA TÉCNICO")
        ctk.CTkButton(c3, text="CONFIGURACIÓN 🛠️", fg_color="#222", hover_color="#333", command=self.open_config_editor).pack(pady=(10,5), padx=20, fill="x")
        ctk.CTkButton(c3, text="VERIFICAR RUTAS 🔎", fg_color="#222", hover_color="#333", command=self.action_verify_paths).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(c3, text="CONVERSOR IMÁGENES 🖼️", fg_color="#222", hover_color="#333", command=self.open_image_converter).pack(pady=5, padx=20, fill="x")

        # Project List (Mini Table)
        list_frm = ctk.CTkScrollableFrame(frm, fg_color="#0A0A0A", border_width=1, border_color="#222", label_text="ÚLTIMAS SESIONES")
        list_frm.pack(fill="both", expand=True, pady=20)
        
        # Load from ProjectManager
        projects = self.project_manager.list_projects()
        if not projects:
            ctk.CTkLabel(list_frm, text="No hay proyectos recientes.", text_color="#444").pack(pady=20)
        else:
            for p in projects[:10]: # Top 10
                row = ctk.CTkFrame(list_frm, fg_color="transparent")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text="📁", width=30).pack(side="left")
                ctk.CTkLabel(row, text=p, font=("Consolas", 12), text_color="#AAA").pack(side="left", padx=10)
                ctk.CTkButton(row, text="CARGAR", width=60, height=20, fg_color="#222", hover_color=COLOR_ACCENT, 
                              command=lambda pid=p: self.load_project_by_id(pid)).pack(side="right", padx=10)

        return frm

    def create_interactive_card(self, parent, col, emoji, title):
        card = ctk.CTkFrame(parent, fg_color="#0A0A0A", border_width=1, border_color="#222", corner_radius=12)
        card.grid(row=0, column=col, sticky="nsew", padx=10)
        ctk.CTkLabel(card, text=emoji, font=("Arial", 30)).pack(pady=(15, 0))
        ctk.CTkLabel(card, text=title, font=("Impact", 16), text_color="#DDD").pack(pady=(0, 5))
        return card

    # --- ACCIONES DEL PANEL INTERACTIVO ---
    def action_new_story(self):
        self.show_view("concept")
        self.update_status("INICIANDO NUEVO PROYECTO...", COLOR_SUCCESS)
        
    def action_open_dir(self):
        out_dir = get_resource_path("projects")
        if os.path.exists(out_dir):
            if os.name == 'nt':
                os.startfile(out_dir)
            else:
                subprocess.run(['xdg-open', out_dir])
                
    def on_model_change(self, selected_model):
        gemini_client.DEFAULT_MODEL = selected_model
        self.update_status(f"♻️ MODELO CAMBIADO A: {selected_model}".upper(), COLOR_SUCCESS)
        
        # Update status bar label if it exists
        if hasattr(self, 'status_bar'):
            # Find the stats_frame in the status_bar (it's the second child, but let's iterate to be safe)
            for widget in self.status_bar.winfo_children():
                if isinstance(widget, ctk.CTkFrame):
                    for subwidget in widget.winfo_children():
                        if isinstance(subwidget, ctk.CTkLabel) and getattr(subwidget, '_text', '').startswith("AI CORE:"):
                            subwidget.configure(text=f"AI CORE: {selected_model.upper()}")
                            break

    def action_verify_paths(self):
        if not self.google_api_key:
            self.update_status("⚠️ ATENCIÓN: API KEY FALTANTE", "red")
        else:
            self.update_status("✅ MOTOR IA Y RUTAS VERIFICADOS (OK)", COLOR_SUCCESS)
        
    def load_project_by_id(self, project_id):
        data = self.project_manager.load_project(project_id)
        if data:
            self.restore_state(data)
            self.current_project_id = project_id
            self.update_status(f"PROYECTO CARGADO: {project_id}", COLOR_SUCCESS)
            # Switch to concept tab? Or stay?
            # self.show_view("concept")

    # --- REMOVED TAB SETUP METHODS (Delegates handled in show_view) ---
    def setup_brain_ui(self): pass
    def setup_painter_ui(self): pass
    def setup_cover_ui(self): pass
    def setup_media_ui(self): pass


    # --- ACCIONES GLOBALES ---
    def open_config_editor(self):
        ConfigEditor(self)

    def open_image_converter(self):
        ImageConverter(self)

    def open_narrative_editor(self):
        NarrativeEditor(self)

    def reset_ui(self):
        self.view_cache = {}
        self.show_view("dashboard")
        self.update_status("♻ SISTEMA REINICIADO", COLOR_SUCCESS)

    def update_status(self, text, color=None):
        if hasattr(self, 'status_lbl'):
            self.status_lbl.configure(text=text, text_color=color if color else COLOR_TEXT_DIM)

    def check_prompt_file(self):
        if not os.path.exists(self.prompt_file):
            with open(self.prompt_file, "w", encoding="utf-8") as f: f.write(prompts_cfg.DEFAULT_PROMPT)

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
