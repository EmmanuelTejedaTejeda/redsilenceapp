import customtkinter as ctk
import threading
from modules import gemini_client, groq_client
import config.prompts as prompts_cfg

# --- THEME CONSTANTS ---
COLOR_BG = "#101010"
COLOR_CARD = "#141414"
COLOR_ACCENT = "#D32F2F"      # Red standard
COLOR_ACCENT_HOVER = "#B71C1C"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_SUB = "#888888"
COLOR_BORDER = "#1F1F1F"
COLOR_INPUT_BG = "#090909"

class CoverTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main = main_window
        
        # State
        self.latest_cover_prompt = ""

        # IMPORTANT: Nav controls first (bottom)
        if hasattr(self.main, 'create_nav_controls'):
             self.main.create_nav_controls(self, 2) # Index 2 for Cover

        # Layout Container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Config Grid: Izquierda controles (Fijo), Derecha Resultado (Expansivo)
        self.container.grid_columnconfigure(0, weight=0, minsize=420)
        self.container.grid_columnconfigure(1, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.setup_ui()

    def setup_ui(self):
        # ==========================
        # LEFT PANEL: INGREDIENTS
        # ==========================
        self.left_panel = ctk.CTkScrollableFrame(self.container, fg_color=COLOR_BG, corner_radius=15, border_width=1, border_color=COLOR_BORDER)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        
        # Inner Content
        l_content = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        l_content.pack(fill="both", expand=True, padx=25, pady=25)

        # Header
        ctk.CTkLabel(l_content, text="3. DISEÑO DE PORTADA", font=("Impact", 28), text_color="#DDD").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(l_content, text="Define los elementos clave para tu miniatura de alto impacto.", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(0, 25))

        # --- INPUT 1: TRAMA / CONTEXTO ---
        ctk.CTkLabel(l_content, text="SINOPSIS / TRAMA PRINCIPAL", font=("Arial", 11, "bold"), text_color=COLOR_ACCENT).pack(anchor="w", pady=(0, 5))
        
        self.txt_trama = ctk.CTkTextbox(l_content, height=120, fg_color=COLOR_INPUT_BG, border_color="#222", border_width=1,
                                        font=("Consolas", 12), text_color="#DDD", wrap="word")
        self.txt_trama.pack(fill="x", pady=(0, 20))
        
        # Auto-fill from Trama Cache (from Tab 1)
        if hasattr(self.main, "current_trama_cache") and self.main.current_trama_cache:
            self.txt_trama.insert("0.0", self.main.current_trama_cache)

        # --- INPUT 2: DNA ---
        ctk.CTkLabel(l_content, text="ADN DEL MONSTRUO (Rasgos Visuales)", font=("Arial", 11, "bold"), text_color=COLOR_ACCENT).pack(anchor="w", pady=(0, 5))
        
        self.entry_adn = ctk.CTkEntry(l_content, placeholder_text="Ej: Piel pálida, ojos vacíos, corona de espinas...", 
                                      height=50, fg_color=COLOR_INPUT_BG, border_color="#222", border_width=1, font=("Arial", 13))
        self.entry_adn.pack(fill="x", pady=(0, 25))

        # --- ACTION BUTTON ---
        self.btn_generate = ctk.CTkButton(l_content, 
                                          text="DISEÑAR PORTADA  👹", 
                                          font=("Arial", 14, "bold"),
                                          height=60,
                                          fg_color=COLOR_ACCENT, 
                                          hover_color=COLOR_ACCENT_HOVER,
                                          text_color="white",
                                          command=self.run_generation_thread)
        self.btn_generate.pack(fill="x", pady=(10, 0))

        # Status
        self.lbl_status = ctk.CTkLabel(l_content, text="LISTO PARA CREAR", font=("Consolas", 11), text_color="gray")
        self.lbl_status.pack(pady=(10, 0))


        # ==========================
        # RIGHT PANEL: THE RESULT
        # ==========================
        self.right_panel = ctk.CTkFrame(self.container, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color=COLOR_BORDER)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        
        r_content = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        r_content.pack(fill="both", expand=True, padx=20, pady=20)

        # Header Right
        h_right = ctk.CTkFrame(r_content, fg_color="transparent")
        h_right.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(h_right, text="PROMPT GENERADO", font=("Impact", 20), text_color="#555").pack(side="left")
        
        self.btn_copy = ctk.CTkButton(h_right, text="COPIAR", width=80, height=25, fg_color="#222", hover_color="#333", command=self.copy_prompt)
        self.btn_copy.pack(side="right")

        # Output Area (Monospace for Prompt)
        self.txt_output = ctk.CTkTextbox(r_content, font=("Consolas", 13), fg_color="#080808", text_color="#FF5555", wrap="word", border_width=0)
        self.txt_output.pack(fill="both", expand=True)
        self.txt_output.insert("0.0", "El prompt para Midjourney/DALL-E aparecerá aquí...")

        # Visual Hint
        ctk.CTkLabel(r_content, text="Usar Aspect Ratio --ar 16:9 o 9:16", font=("Arial", 10), text_color="#444").pack(anchor="e", pady=(5,0))


    def run_generation_thread(self):
        threading.Thread(target=self.run_generation, daemon=True).start()

    def run_generation(self):
        trama = self.txt_trama.get("0.0", "end").strip()
        adn = self.entry_adn.get().strip()

        if not trama or not adn:
            self.update_status("❌ Faltan datos (Trama o ADN)", "orange")
            return
        provider = getattr(self.main, "llm_provider", "gemini")
        if provider == "groq":
            api_key = getattr(self.main, "groq_api_key", "")
            bot_name = "GROQ"
        else:
            api_key = getattr(self.main, "google_api_key", "")
            bot_name = "GEMINI"
            
        if not api_key:
            self.update_status(f"⚠️ Configura tu API Key de {bot_name}", "orange")
            return

        # UI Lock
        self.update_status(f"{bot_name} ESTÁ DISEÑANDO...", "#FFD700")
        self.btn_generate.configure(state="disabled", text="GENERANDO...")
        
        try:
            # Template
            current_template = prompts_cfg.COVER_PROMPT_TEMPLATE
            if not current_template:
                 with open(prompts_cfg.COVER_TEMPLATE_PATH, "r", encoding="utf-8") as f: 
                    current_template = f.read()

            final_prompt = current_template.replace("{TRAMA}", trama).replace("{ADN}", adn)
            
            # API
            if provider == "groq":
                result = groq_client.generate_content(final_prompt, api_key)
            else:
                result = gemini_client.generate_content(final_prompt, api_key)
            
            # Success
            self.after(0, lambda: self.on_success(result))

        except Exception as e:
            self.update_status(f"ERROR: {str(e)}", "red")
            self.after(0, lambda: self.btn_generate.configure(state="normal", text="DISEÑAR PORTADA 👹"))

    def on_success(self, text):
        self.latest_cover_prompt = text
        self.main.latest_cover_prompt = text # Cache in main
        
        self.txt_output.delete("0.0", "end")
        self.txt_output.insert("0.0", text)
        
        self.update_status("✅ PROMPT DE PORTADA LISTO", "#00E676")
        self.btn_generate.configure(state="normal", text="RE-DISEÑAR PORTADA 👹")

    def update_status(self, text, color):
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color))

    def copy_prompt(self):
        try:
            text = self.txt_output.get("0.0", "end")
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self.btn_copy.configure(text="✅")
            self.after(1000, lambda: self.btn_copy.configure(text="COPIAR"))
        except: pass

    def focus_set(self):
        """Override to refresh content when tab becomes visible"""
        super().focus_set()
        # Refresh Trama
        if hasattr(self.main, "current_trama_cache") and self.main.current_trama_cache:
            current_t = self.txt_trama.get("0.0", "end").strip()
            if current_t != self.main.current_trama_cache:
                self.txt_trama.delete("0.0", "end")
                self.txt_trama.insert("0.0", self.main.current_trama_cache)
        
        # Refresh ADN
        if hasattr(self.main, "entity_adn") and self.main.entity_adn:
            current_a = self.entry_adn.get().strip()
            if current_a != self.main.entity_adn:
                self.entry_adn.delete(0, "end")
                self.entry_adn.insert(0, self.main.entity_adn)
