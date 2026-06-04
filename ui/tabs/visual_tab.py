import customtkinter as ctk
import threading
from modules import gemini_client, groq_client
import config.prompts as prompts_cfg
from core.math_logic import calculate_visual_segments
from ui.visual_prompt_viewer import VisualPromptViewer

# --- THEME CONSTANTS ---
COLOR_BG = "#101010"
COLOR_CARD = "#141414" 
COLOR_ACCENT = "#D32F2F"
COLOR_ACCENT_HOVER = "#B71C1C"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_SUB = "#888888"
COLOR_BORDER = "#1F1F1F"

class VisualTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main = main_window
        
        # State
        self.latest_visual_prompts = ""

        # IMPORTANT: Nav controls first (bottom)
        if hasattr(self.main, 'create_nav_controls'):
             self.main.create_nav_controls(self, 1)

        # Layout Container (to avoid pack/grid conflict with parent nav)
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Config Grid: Col 0 fija para controles, Col 1 expansiva
        self.container.grid_columnconfigure(0, weight=0, minsize=420) 
        self.container.grid_columnconfigure(1, weight=1) 
        self.container.grid_rowconfigure(0, weight=1)

        self.setup_ui()

    def setup_ui(self):
        # ==========================
        # LEFT PANEL: CONTEXTO
        # ==========================
        self.left_panel = ctk.CTkFrame(self.container, fg_color=COLOR_BG, corner_radius=15, border_width=1, border_color=COLOR_BORDER)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=10)
        
        # Inner Padding
        l_content = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        l_content.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        ctk.CTkLabel(l_content, text="1. CONTEXTO NARRATIVO", font=("Impact", 24), text_color="#333").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(l_content, text="La IA necesita entender la historia para pintar el horror.", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(0, 20))

        # Text Area
        self.txt_context = ctk.CTkTextbox(l_content, 
                                          font=("Consolas", 12), 
                                          fg_color="#080808", 
                                          text_color="#DDD", 
                                          border_width=1, 
                                          border_color="#222", 
                                          wrap="word")
        self.txt_context.pack(fill="both", expand=True, pady=(0, 10))
        
        # Auto-fill from Concept Tab if available
        if hasattr(self.main, "current_trama_cache") and self.main.current_trama_cache:
            self.txt_context.insert("0.0", self.main.current_trama_cache)

        # ==========================
        # RIGHT PANEL: GENERATOR ENGINE
        # ==========================
        # ==========================
        # RIGHT PANEL: GENERATOR ENGINE
        # ==========================
        self.right_panel = ctk.CTkScrollableFrame(self.container, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color=COLOR_BORDER)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        
        # Title
        ctk.CTkLabel(self.right_panel, text="MOTOR VISUAL", font=("Impact", 32), text_color=COLOR_ACCENT).pack(pady=(40, 5))
        ctk.CTkLabel(self.right_panel, text="Configura la duración y genera los prompts.", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(pady=(0, 30))

        # Duration Input Group
        dur_frame = ctk.CTkFrame(self.right_panel, fg_color="#090909", corner_radius=10, border_color="#222", border_width=1)
        dur_frame.pack(fill="x", pady=(0, 25))

        ctk.CTkLabel(dur_frame, text="DURACIÓN DEL AUDIO (SEG)", font=("Arial", 11, "bold"), text_color="#666").pack(anchor="w", padx=15, pady=(15, 5))
        
        self.entry_duration = ctk.CTkEntry(dur_frame, 
                                           placeholder_text="58...", 
                                           font=("Arial", 24, "bold"), 
                                           height=50, 
                                           fg_color="transparent", 
                                           border_width=0, 
                                           text_color="white")
        self.entry_duration.pack(fill="x", padx=10, pady=(0, 5))
        
        # Hint below duration
        self.lbl_segments = ctk.CTkLabel(dur_frame, text="≈ 0 imágenes estimadas (corte cada 3s)", font=("Arial", 10), text_color="#444")
        self.lbl_segments.pack(anchor="w", padx=15, pady=(0, 15))

        # Bind validation/calc to entry
        self.entry_duration.bind("<KeyRelease>", self.update_segment_hint)

        # Generate Button (THE BIG RED BUTTON)
        self.btn_generate = ctk.CTkButton(self.right_panel, 
                                          text="GENERAR PROMPTS VISUALES  ⚡", 
                                          font=("Arial", 14, "bold"),
                                          height=60,
                                          fg_color=COLOR_ACCENT, 
                                          hover_color=COLOR_ACCENT_HOVER,
                                          text_color="white",
                                          command=self.run_generation_thread)
        self.btn_generate.pack(fill="x", pady=10)

        # Status & Results
        self.lbl_status = ctk.CTkLabel(self.right_panel, text="ESPERANDO INSTRUCCIONES...", font=("Consolas", 11), text_color="gray")
        self.lbl_status.pack(pady=(10, 0))

        # Result Action (Initially Hidden/Disabled)
        self.btn_view_results = ctk.CTkButton(self.right_panel, 
                                              text="⤢  ABRIR VISOR DE PROMPTS", 
                                              font=("Arial", 12, "bold"),
                                              height=45,
                                              fg_color="#222", 
                                              hover_color="#333",
                                              border_color="#444",
                                              border_width=1,
                                              text_color="gray",
                                              state="disabled",
                                              command=self.open_visual_editor)
        self.btn_view_results.pack(fill="x", pady=(20, 0))

    def update_segment_hint(self, event=None):
        try:
            val = float(self.entry_duration.get())
            segs = calculate_visual_segments(val)
            self.lbl_segments.configure(text=f"≈ {segs} imágenes estimadas (corte cada 3s)", text_color=COLOR_TEXT_SUB)
        except ValueError:
            self.lbl_segments.configure(text="Ingrese un número válido...", text_color=COLOR_ACCENT)

    def run_generation_thread(self):
        threading.Thread(target=self.run_generation, daemon=True).start()

    def run_generation(self):
        ctx = self.txt_context.get("0.0", "end").strip()
        dur_str = self.entry_duration.get().strip()

        # Validation
        if not ctx:
            self.update_status("❌ Falta el contexto narrativo", "orange")
            return
        if not dur_str:
            self.update_status("❌ Falta la duración del audio", "orange")
            return
            
        provider = getattr(self.main, "llm_provider", "gemini")
        if provider == "groq":
            api_key = getattr(self.main, "groq_api_key", "")
            bot_name = "GROQ"
        else:
            api_key = getattr(self.main, "google_api_key", "")
            bot_name = "GEMINI"
            
        if not api_key:
            self.update_status(f"⚠️ Configura tu API Key de {bot_name} en el menú global", "orange")
            return

        try:
            duration = float(dur_str)
        except ValueError:
            self.update_status("❌ La duración debe ser un número", "orange")
            return

        # UI Lock
        self.update_status(f"{bot_name} ESTÁ IMAGINANDO EL HORROR...", "#FFD700")
        self.btn_generate.configure(state="disabled", text="PROCESANDO...")
        
        try:
            # Logic
            num_images = calculate_visual_segments(duration)
            
            # Template Load
            current_template = prompts_cfg.VISUAL_PROMPT_TEMPLATE
            if not current_template:
                 with open(prompts_cfg.VISUAL_TEMPLATE_PATH, "r", encoding="utf-8") as f: 
                    current_template = f.read()

            # Injection
            final_prompt = current_template.replace("{STORY_CONTEXT}", ctx)\
                                           .replace("{DURATION}", dur_str)\
                                           .replace("{NUM_IMAGES}", str(num_images))
            
            # API Call
            if provider == "groq":
                result = groq_client.generate_content(final_prompt, api_key)
            else:
                result = gemini_client.generate_content(final_prompt, api_key)
            
            # Success
            self.after(0, lambda: self.on_success(result))

        except Exception as e:
            self.update_status(f"ERROR: {str(e)}", "red")
            self.after(0, lambda: self.btn_generate.configure(state="normal", text="GENERAR PROMPTS VISUALES ⚡"))

    def on_success(self, text):
        self.latest_visual_prompts = text
        self.main.latest_visual_prompts = text 
        
        # --- NEW: EXTRACT ENTITY ADN ---
        import re
        try:
            # Look for VARIABLE DE ENTIDAD (ENTITY_DNA): "..."
            adn_match = re.search(r"VARIABLE DE ENTIDAD.*?:\s*[\"']*(.*?)[\"']*(?=\n|$)", text, re.IGNORECASE)
            if adn_match:
                self.main.entity_adn = adn_match.group(1).strip()
                print(f">>> [VISUAL TAB] ADN Extraído: {self.main.entity_adn[:50]}...")
        except Exception as e:
            print(f">>> [VISUAL DNA PARSE ERROR]: {e}")

        self.update_status("✅ PROMPTS GENERADOS EXITOSAMENTE", "#00E676")
        self.btn_generate.configure(state="normal", text="RE-GENERAR PROMPTS ⚡")
        self.btn_view_results.configure(state="normal", fg_color="#222", text_color="white", border_color=COLOR_ACCENT)
        
        # Auto-open
        self.open_visual_editor()

    def update_status(self, text, color):
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color))

    def open_visual_editor(self):
        if not self.latest_visual_prompts: return
        VisualPromptViewer(self, self.latest_visual_prompts)

    def focus_set(self):
        """Override to refresh content when tab becomes visible"""
        super().focus_set()
        if hasattr(self.main, "current_trama_cache") and self.main.current_trama_cache:
            current = self.txt_context.get("0.0", "end").strip()
            if current != self.main.current_trama_cache:
                self.txt_context.delete("0.0", "end")
                self.txt_context.insert("0.0", self.main.current_trama_cache)
