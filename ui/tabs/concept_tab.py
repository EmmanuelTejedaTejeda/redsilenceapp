import customtkinter as ctk
import threading
import random
import os
import time
import re
import platform
from modules import gemini_client, groq_client, voice_generator
import config.prompts as prompts_cfg
from core import utils as prompts_utils

# --- THEME CONSTANTS ---
COLOR_BG = "#101010"
COLOR_CARD = "#141414"
COLOR_ACCENT = "#D32F2F"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_SUB = "#666666"
COLOR_SUCCESS = "#00E676"

class ConceptTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main = main_window
        
        # Grid Layout: 2 Columns equivalent to Split View
        # IMPORTANT: Create Nav Controls FIRST so they pack at bottom
        if hasattr(self.main, 'create_nav_controls'):
            self.main.create_nav_controls(self, 0)

        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)
        
        # Col 0 Fija, Col 1 Expansiva
        self.grid_container.grid_columnconfigure(0, weight=0, minsize=420) # Standarized to 420
        self.grid_container.grid_columnconfigure(1, weight=1)              # Resultados
        self.grid_container.grid_rowconfigure(0, weight=1)
        
        self.setup_ui()

    def setup_ui(self):
        # ==========================
        # LEFT PANEL: INPUT (THE SEED)
        # ==========================
        left_panel = ctk.CTkFrame(self.grid_container, fg_color=COLOR_BG, corner_radius=15, border_width=1, border_color="#1F1F1F")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=10)
        
        # Center container for Input
        input_container = ctk.CTkFrame(left_panel, fg_color="transparent")
        input_container.place(relx=0.5, rely=0.4, anchor="center", relwidth=0.85)
        
        # Title
        ctk.CTkLabel(input_container, text="SEMILLA DEL TERROR", font=("Impact", 32), text_color="#333").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(input_container, text="Describe el núcleo de tu pesadilla...", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(0, 20))
        
        # Input Field (Styled) - Ahora es un cuadro de texto multilínea para semillas largas
        self.entry_idea = ctk.CTkTextbox(input_container, 
                                         height=120,
                                         font=("Arial", 12),
                                         fg_color="#080808",
                                         border_color="#222",
                                         border_width=1,
                                         text_color="white",
                                         wrap="word")
        self.entry_idea.pack(fill="x", pady=(0, 15))
        self.entry_idea.insert("0.0", "Introduce aquí la semilla del terror (ideas, relatos o hilos de Reddit)...")
        
        # Duration Selector Frame
        duration_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        duration_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(duration_frame, text="Duración Objetivo:", font=("Arial", 11, "bold"), text_color=COLOR_TEXT_SUB).pack(side="left")
        
        self.seg_duration = ctk.CTkSegmentedButton(duration_frame,
                                                  values=["30s", "45s", "60s"],
                                                  selected_color=COLOR_ACCENT,
                                                  selected_hover_color="#B71C1C",
                                                  fg_color="#080808",
                                                  text_color="white")
        self.seg_duration.pack(side="right")
        self.seg_duration.set("30s")
        
        # Action Button (Hero)
        self.btn_generate = ctk.CTkButton(input_container, 
                                          text="MATERIALIZAR GUION  ⚡", 
                                          font=("Arial", 14, "bold"),
                                          height=55,
                                          fg_color=COLOR_ACCENT, 
                                          hover_color="#B71C1C",
                                          text_color="white",
                                          command=self.run_generation_thread)
        self.btn_generate.pack(fill="x")

        # Autopilot Button (Purple Neon)
        self.btn_autopilot = ctk.CTkButton(input_container, 
                                           text="🚀 AUTOPILOTO: CREAR SHORT (1-CLIC) ⚡", 
                                           font=("Arial", 14, "bold"),
                                           height=55,
                                           fg_color="#651FFF", 
                                           hover_color="#4500C7",
                                           text_color="white",
                                           command=self.run_autopilot_thread)
        self.btn_autopilot.pack(fill="x", pady=(10, 0))

        # Re-Generate Button (Hidden initially)
        self.btn_regenerate = ctk.CTkButton(input_container, 
                                            text="🔄 RE-GENERAR OTRA VERSIÓN", 
                                            font=("Arial", 12, "bold"),
                                            height=40,
                                            fg_color="#333", 
                                            hover_color="#444",
                                            text_color="#AAA",
                                            command=self.run_generation_thread)
        # Don't pack immediately, or pack with pady=10 but state disabled/hidden?
        # Better: pack it but remove it until needed? Or just state=disabled.
        # Let's pack it but disable it.
        self.btn_regenerate.pack(fill="x", pady=(10, 0))
        self.btn_regenerate.configure(state="disabled", fg_color="transparent", text="") # Hide visually

        # Reddit Scraper Button
        self.btn_reddit = ctk.CTkButton(input_container,
                                         text="👾 BUSCAR TENDENCIAS EN REDDIT",
                                         font=("Arial", 12, "bold"),
                                         height=40,
                                         fg_color="#FF4500", # Reddit Orange
                                         hover_color="#CC3700",
                                         text_color="white",
                                         command=self.open_reddit_scraper_dialog)
        self.btn_reddit.pack(fill="x", pady=(10, 0))

        
        # Status
        self.lbl_status = ctk.CTkLabel(input_container, text="", font=("Consolas", 11), text_color=COLOR_ACCENT)
        self.lbl_status.pack(pady=(15, 0))

        # ==========================
        # RIGHT PANEL: OUTPUT (THE SCRIPT)
        # ==========================
        right_panel = ctk.CTkFrame(self.grid_container, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#181818")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        
        # Header Right
        header_r = ctk.CTkFrame(right_panel, fg_color="transparent", height=40)
        header_r.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(header_r, text="MANUSCRITO GENERADO", font=("Arial", 12, "bold"), text_color=COLOR_TEXT_SUB).pack(side="left")
        
        # Copy Script Button
        ctk.CTkButton(header_r, text="COPIAR GUION", width=100, height=25, fg_color="#222", hover_color="#333", 
                      font=("Arial", 10), command=self.copy_output).pack(side="right", padx=5)

        # Copy Voice Instructions Button
        ctk.CTkButton(header_r, text="COPIAR INSTR. VOZ 🎤", width=140, height=25, fg_color="#222", hover_color="#333", 
                      font=("Arial", 10), command=self.copy_voice_instructions).pack(side="right", padx=5)
        
        # Text Area (Paper feel)
        self.txt_output = ctk.CTkTextbox(right_panel, 
                                         font=("Consolas", 13), 
                                         fg_color="#080808", 
                                         text_color="#DDD", 
                                         wrap="word",
                                         border_width=0)
        self.txt_output.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Placeholder text
        self.txt_output.insert("0.0", "El guion generado por la IA aparecerá aquí...\n\nEsperando señal...")
        self.txt_output.configure(state="disabled") # Read-only initially

    def run_generation_thread(self):
        idea = self.entry_idea.get("0.0", "end").strip()
        
        # --- VALIDATIONS ---
        if not idea or "Introduce aquí la semilla del terror" in idea:
            self.update_status("⚠️ La pesadilla necesita un origen (Escribe una idea)", "orange")
            return
            
        provider = getattr(self.main, "llm_provider", "gemini")
        if provider == "groq":
            api_key = getattr(self.main, "groq_api_key", "")
            bot_name = "GROQ"
        else:
            api_key = getattr(self.main, "google_api_key", "")
            bot_name = "GEMINI"
            
        if not api_key:
            self.update_status(f"⚠️ Configura tu API Key de {bot_name} en el menú de engranaje", "orange")
            return

        # --- UI LOCK (Main Thread) ---
        self.update_status(f"INVOCANDO A {bot_name}...", "#FFD700")
        self.btn_generate.configure(state="disabled", text="GENERANDO...")
        self.btn_regenerate.configure(state="disabled")
        self.main.current_trama_cache = idea # Save for later tabs
        duration = self.seg_duration.get()
        
        # Start Thread
        threading.Thread(target=self.run_generation, args=(idea, api_key, provider, duration), daemon=True).start()

    def run_generation(self, idea, api_key, provider, duration):
        try:
            # --- LOGIC (Background Thread) ---
            # 1. Update paths and reload template to ensure the latest selection is used
            prompts_cfg.update_paths_from_settings()
            current_template = prompts_cfg.STORY_PROMPT_TEMPLATE
            
            if not current_template:
                 with open(prompts_cfg.STORY_TEMPLATE_PATH, "r", encoding="utf-8") as f: 
                    current_template = f.read()

            # 2. Randomize Narrative Vars
            prompts_cfg.load_narrative_vars()
            sel_gancho = random.choice(prompts_cfg.LISTA_GANCHOS) if prompts_cfg.LISTA_GANCHOS else "Sin definir"
            sel_monstruo = random.choice(prompts_cfg.LISTA_MONSTRUOS) if prompts_cfg.LISTA_MONSTRUOS else "Sin definir"
            sel_atmosfera = random.choice(prompts_cfg.LISTA_ATMOSFERA) if prompts_cfg.LISTA_ATMOSFERA else "Sin definir"
            sel_cierre = random.choice(prompts_cfg.LISTA_CIERRES) if prompts_cfg.LISTA_CIERRES else "Sin definir"

            # 3. Inject
            full_prompt = current_template.replace("{TRAMA}", idea)\
                                          .replace("{GANCHO}", sel_gancho)\
                                          .replace("{MONSTRUO}", sel_monstruo)\
                                          .replace("{ATMOSFERA}", sel_atmosfera)\
                                          .replace("{CIERRE}", sel_cierre)
            
            # 3.1. Inject dynamic target duration rule
            if duration == "30s":
                word_limit = "El guion para la IA de voz (limpio) DEBE tener entre 100 y 115 palabras en total. Esto es un límite ESTRICTO. Mantén las frases muy cortas, dinámicas y directas al grano."
            elif duration == "45s":
                word_limit = "El guion para la IA de voz (limpio) DEBE tener entre 150 y 165 palabras en total. Esto es un límite ESTRICTO. Mantén las frases dinámicas y directas al grano."
            else: # "60s"
                word_limit = "El guion para la IA de voz (limpio) DEBE tener entre 190 y 210 palabras en total. Esto es un límite ESTRICTO. Mantén las frases dinámicas y directas al grano."
            
            full_prompt += f"\n\n[INSTRUCCIÓN CRÍTICA DE DURACIÓN Y LÍMITE DE PALABRAS]:\n{word_limit}\n"
            
            # 4. Call API
            if provider == "groq":
                result = groq_client.generate_content(full_prompt, api_key)
            else:
                result = gemini_client.generate_content(full_prompt, api_key)
            
            # 5. Success -> Schedule UI Update
            self.after(0, lambda: self.show_result(result))
            
        except Exception as e:
            # Error -> Schedule UI Reset
            self.after(0, lambda: self.handle_generation_error(str(e)))

    def handle_generation_error(self, error_msg):
        self.update_status(f"ERROR: {error_msg}", "red")
        self.btn_generate.configure(state="normal", text="MATERIALIZAR GUION ⚡")
        self.btn_regenerate.configure(state="normal")

    def show_result(self, text):
        self.txt_output.configure(state="normal")
        self.txt_output.delete("0.0", "end")
        self.txt_output.insert("0.0", text)
        
        # --- NEW: AUTO-EXTRACTION LOGIC ---
        import re
        try:
            # 1. Extract Title
            title_match = re.search(r"---TITULOS---\n1\.\s*(.+)", text, re.IGNORECASE)
            if title_match:
                self.main.generated_title = title_match.group(1).strip()
            
            # 2. Extract Description
            desc_match = re.search(r"---DESCRIPCION---\n(.*?)(?=\n---|$)", text, re.DOTALL | re.IGNORECASE)
            if desc_match:
                self.main.generated_desc = desc_match.group(1).strip()
            
            # 3. Extract Story (Clean version for Voice/Context)
            story_match = re.search(r"---GUION PARA IA DE VOZ \(LIMPIO\)---\n(.*?)(?=\n---|$)", text, re.DOTALL | re.IGNORECASE)
            if story_match:
                clean_story = story_match.group(1).strip()
                self.main.generated_story = clean_story
                # Override cache with the actual story for better prompt results in P2/P3
                self.main.current_trama_cache = clean_story
            
        except Exception as e:
            print(f">>> [CONCEPT PARSE ERROR]: {e}")

        self.update_status("✅ GUION MATERIALIZADO + DATOS SINCRONIZADOS", COLOR_SUCCESS)
        self.btn_generate.configure(state="normal", text="MATERIALIZAR GUION ⚡")
        
        # Show regenerate option
        self.btn_regenerate.configure(state="normal", fg_color="#222", text="PROBAR OTRA NARRATIVA 🎲", text_color="#DDD")

    def update_status(self, text, color):
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color))

    def copy_output(self):
        result = prompts_utils.copy_to_clipboard_persistent(self.txt_output.get("0.0", "end"))
        if result:
            self.update_status("📋 Copiado al portapapeles (Persistente)", "white")
        else:
            self.update_status("⚠️ Error copiando (Intenta Ctrl+C)", "orange")

    def copy_voice_instructions(self):
        try:
            with open(prompts_cfg.VOICE_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                instructions = f.read()
        except Exception as e:
            print(f"Error loading voice instructions: {e}")
            instructions = "Error: No se pudo cargar el archivo de instrucciones de voz."
        result = prompts_utils.copy_to_clipboard_persistent(instructions)
        if result:
             self.update_status("🎤 Instrucciones de voz copiadas", "white")
        else:
             self.update_status("❌ Error al copiar", "red")

    # --- PROJECT MANAGEMENT ---
    def get_state(self):
        return {
            "trama": self.entry_idea.get("0.0", "end").strip(),
            "guion": self.txt_output.get("0.0", "end")
        }

    def restore_state(self, state):
        if not state: return
        
        trama = state.get("trama", "")
        guion = state.get("guion", "")
        
        self.entry_idea.delete("0.0", "end")
        self.entry_idea.insert("0.0", trama)
        
        self.txt_output.configure(state="normal")
        self.txt_output.delete("0.0", "end")
        self.txt_output.insert("0.0", guion)

    def open_reddit_scraper_dialog(self):
        RedditScraperWindow(self)

    def run_autopilot_thread(self):
        idea = self.entry_idea.get("0.0", "end").strip()
        
        # --- VALIDATIONS ---
        if not idea or "Introduce aquí la semilla del terror" in idea:
            self.update_status("⚠️ La pesadilla necesita un origen (Escribe una idea)", "orange")
            return
            
        provider = getattr(self.main, "llm_provider", "gemini")
        if provider == "groq":
            api_key = getattr(self.main, "groq_api_key", "")
            bot_name = "GROQ"
        else:
            api_key = getattr(self.main, "google_api_key", "")
            bot_name = "GEMINI"
            
        if not api_key:
            self.update_status(f"⚠️ Configura tu API Key de {bot_name} en el menú de engranaje", "orange")
            return

        # UI Lock
        self.update_status("🚀 INICIANDO AUTOPILOTO (1-CLIC)...", "#FFD700")
        self.btn_generate.configure(state="disabled")
        self.btn_autopilot.configure(state="disabled", text="EJECUTANDO AUTOPILOTO... ⏳")
        self.btn_regenerate.configure(state="disabled")
        duration = self.seg_duration.get()
        
        threading.Thread(target=self.run_autopilot_pipeline, args=(idea, api_key, provider, duration), daemon=True).start()

    def run_autopilot_pipeline(self, idea, api_key, provider, duration):
        try:
            # FASE 1: GENERACIÓN DE GUION
            self.after(0, lambda: self.update_status("🚀 [AUTOPILOTO] 1/5 - GENERANDO GUION CON IA...", "#FFD700"))
            
            # Reload template and settings
            prompts_cfg.update_paths_from_settings()
            current_template = prompts_cfg.STORY_PROMPT_TEMPLATE
            if not current_template:
                 with open(prompts_cfg.STORY_TEMPLATE_PATH, "r", encoding="utf-8") as f: 
                    current_template = f.read()

            # Randomize Narrative Vars
            prompts_cfg.load_narrative_vars()
            sel_gancho = random.choice(prompts_cfg.LISTA_GANCHOS) if prompts_cfg.LISTA_GANCHOS else "Sin definir"
            sel_monstruo = random.choice(prompts_cfg.LISTA_MONSTRUOS) if prompts_cfg.LISTA_MONSTRUOS else "Sin definir"
            sel_atmosfera = random.choice(prompts_cfg.LISTA_ATMOSFERA) if prompts_cfg.LISTA_ATMOSFERA else "Sin definir"
            sel_cierre = random.choice(prompts_cfg.LISTA_CIERRES) if prompts_cfg.LISTA_CIERRES else "Sin definir"

            # Inject
            full_prompt = current_template.replace("{TRAMA}", idea)\
                                          .replace("{GANCHO}", sel_gancho)\
                                          .replace("{MONSTRUO}", sel_monstruo)\
                                          .replace("{ATMOSFERA}", sel_atmosfera)\
                                          .replace("{CIERRE}", sel_cierre)
            
            if duration == "30s":
                word_limit = "El guion para la IA de voz (limpio) DEBE tener entre 100 y 115 palabras en total. Esto es un límite ESTRICTO. Mantén las frases muy cortas, dinámicas y directas al grano."
            elif duration == "45s":
                word_limit = "El guion para la IA de voz (limpio) DEBE tener entre 150 y 165 palabras en total. Esto es un límite ESTRICTO. Mantén las frases dinámicas y directas al grano."
            else: # "60s"
                word_limit = "El guion para la IA de voz (limpio) DEBE tener entre 190 y 210 palabras en total. Esto es un límite ESTRICTO. Mantén las frases dinámicas y directas al grano."
            
            full_prompt += f"\n\n[INSTRUCCIÓN CRÍTICA DE DURACIÓN Y LÍMITE DE PALABRAS]:\n{word_limit}\n"
            
            # Call API
            if provider == "groq":
                result = groq_client.generate_content(full_prompt, api_key)
            else:
                result = gemini_client.generate_content(full_prompt, api_key)
                
            # Parse result (Title, Desc, Story)
            # Update UI on main thread
            self.after(0, lambda: self.show_result(result))
            
            # Esperar un instante para que se aplique la sincronización de variables
            time.sleep(1.0)
            
            # FASE 2: GENERACIÓN DE VOZ (TTS)
            self.after(0, lambda: self.update_status("🚀 [AUTOPILOTO] 2/5 - GENERANDO VOZ NARRACIÓN...", "#FFD700"))
            
            text_voice = getattr(self.main, "generated_story", "").strip()
            if not text_voice:
                raise Exception("No se pudo extraer el guion limpio del texto generado.")
                
            # Configurar nombre de archivo
            clean_title = "".join([c for c in getattr(self.main, "generated_title", "Video") if c.isalnum() or c==' ']).rstrip().replace(" ", "_")
            if not clean_title:
                clean_title = "narracion_autopilot"
            filename = f"POV_{clean_title[:30]}.wav"
            
            voice_instructions_path = os.path.join(os.getcwd(), "config", "prompts", "voice", "voice_instructions2.txt")
            if not os.path.exists(voice_instructions_path):
                voice_instructions_path = os.path.join(os.getcwd(), "config", "prompts", "voice", "voice_instructions.txt")
                
            model_name = "gemini-2.5-flash-preview-tts"
            voice_tab = self.main.view_cache.get("voice_gen")
            if voice_tab:
                audio_dir = voice_tab.get_audio_folder()
                self.after(0, lambda: [
                    voice_tab.entry_filename.delete(0, "end"),
                    voice_tab.entry_filename.insert(0, filename.replace(".wav", "")),
                    voice_tab.txt_script.delete("0.0", "end"),
                    voice_tab.txt_script.insert("0.0", text_voice)
                ])
            else:
                audio_dir = os.path.join(os.path.expanduser("~"), "Videos", "SilencioRojo", "Audio")
                os.makedirs(audio_dir, exist_ok=True)
                
            output_voice_path = os.path.join(audio_dir, filename)
            
            # Generate TTS voice
            voice_generator.generate_voice(
                text=text_voice,
                api_key=api_key,
                voice_instructions_path=voice_instructions_path,
                output_path=output_voice_path,
                model_name=model_name
            )
            
            if voice_tab:
                self.after(0, lambda: [
                    voice_tab.on_generation_success(output_voice_path)
                ])
                
            # Set global audio path
            self.main.audio_path = output_voice_path
            
            # FASE 3: CONFIGURACIÓN DE METADATOS Y AUDIO ACTIVO
            self.after(0, lambda: self.update_status("🚀 [AUTOPILOTO] 3/5 - SINCRONIZANDO AUDIO Y METADATOS...", "#FF9100"))
            
            media_tab = self.main.view_cache.get("media")
            if media_tab:
                self.after(0, lambda: [
                    media_tab.entry_title.delete(0, "end"),
                    media_tab.entry_title.insert(0, self.main.generated_title),
                    media_tab.entry_card_title.delete(0, "end"),
                    media_tab.entry_card_title.insert(0, self.main.generated_title),
                    media_tab.txt_desc.delete("0.0", "end"),
                    media_tab.txt_desc.insert("0.0", self.main.generated_desc),
                    media_tab.lbl_audio_name.configure(text=f"AUDIO ACTIVO: {os.path.basename(output_voice_path)[:25]}", text_color=COLOR_SUCCESS),
                    media_tab.btn_audio.configure(border_color=COLOR_SUCCESS),
                ])
                media_tab.audio_path = output_voice_path
                
            # FASE 4: SOURCING VISUAL (AUTO GAMEPLAY)
            self.after(0, lambda: self.update_status("🚀 [AUTOPILOTO] 4/5 - OBTENIENDO CLIPS DE GAMEPLAY (MINECRAFT)...", "#FF9100"))
            
            from modules.render_utils import get_video_duration
            dur = get_video_duration(output_voice_path)
            if dur <= 0:
                dur = 60.0
                
            if media_tab:
                media_tab.run_gameplay_sourcing("Minecraft Parkour", dur, "9:16")
                
            # FASE 5: CONFIGURAR MÚSICA Y GUARDAR SESIÓN
            self.after(0, lambda: self.update_status("🚀 [AUTOPILOTO] 5/5 - SELECCIONANDO MÚSICA Y FILTROS...", "#00FF66"))
            
            if media_tab:
                self.after(0, lambda: [
                    media_tab.chk_music.select(),
                    media_tab.reroll_music(silent=True),
                    media_tab.combo_luts.set("Vintage VHS"),
                    media_tab.combo_sub_style.set("Reddit History"),
                    media_tab.check_ready_state()
                ])
                media_tab.music_enabled = True
                
            time.sleep(1.0)
            self.after(0, lambda: self.main.save_current_state())
            
            # FINALIZACIÓN
            self.after(0, lambda: [
                self.update_status("✅ AUTOPILOTO COMPLETADO - PROYECTO LISTO", COLOR_SUCCESS),
                self.btn_generate.configure(state="normal"),
                self.btn_autopilot.configure(state="normal", text="🚀 AUTOPILOTO: CREAR SHORT (1-CLIC) ⚡"),
                self.main.show_view("media")
            ])
            
            # Sound notification
            try:
                if platform.system() == "Windows":
                    import winsound
                    winsound.MessageBeep()
            except: pass
            
        except Exception as err:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: [
                self.update_status(f"🛑 ERROR EN AUTOPILOTO: {str(err)[:45]}", "red"),
                self.btn_generate.configure(state="normal"),
                self.btn_autopilot.configure(state="normal", text="🚀 AUTOPILOTO: CREAR SHORT (1-CLIC) ⚡"),
                self.btn_regenerate.configure(state="normal")
            ])

class RedditScraperWindow(ctk.CTkToplevel):
    def __init__(self, parent_tab):
        super().__init__(parent_tab)
        self.tab = parent_tab
        self.title("TENDENCIAS DE TERROR EN REDDIT")
        self.geometry("700x550")
        self.configure(fg_color="#0F0F0F")
        self.transient(parent_tab)
        self.grab_set()
        self.resizable(False, False)
        
        # Centrar diálogo respecto a la ventana principal
        if hasattr(parent_tab.main, 'winfo_x'):
            main_x = parent_tab.main.winfo_x()
            main_y = parent_tab.main.winfo_y()
            main_w = parent_tab.main.winfo_width()
            main_h = parent_tab.main.winfo_height()
            
            x = main_x + (main_w // 2) - (700 // 2)
            y = main_y + (main_h // 2) - (550 // 2)
            self.geometry(f"+{x}+{y}")

        self.setup_ui()
        self.load_stories()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(header, text="REDDIT HORROR SCRAPER", font=("Impact", 24), text_color="#FF4500").pack(side="left")
        
        # Subreddit Selector
        self.combo_sub = ctk.CTkComboBox(header, values=["shortscarystories", "creepypasta", "nosleep"], width=180,
                                         fg_color="#050505", border_color="#222", button_color="#1A1A1A",
                                         command=lambda v: self.load_stories())
        self.combo_sub.pack(side="right", padx=10)
        ctk.CTkLabel(header, text="Subreddit:", font=("Arial", 11, "bold"), text_color="#888").pack(side="right")

        # Scrollable container for list of stories
        self.scroll_stories = ctk.CTkScrollableFrame(self, fg_color="#080808", border_width=1, border_color="#181818")
        self.scroll_stories.pack(fill="both", expand=True, padx=20, pady=10)

        # Status Label
        self.lbl_status = ctk.CTkLabel(self, text="Cargando historias...", font=("Consolas", 11), text_color="#888")
        self.lbl_status.pack(pady=10)

    def load_stories(self):
        self.lbl_status.configure(text="Conectando con Reddit...", text_color="#FFD700")
        for widget in self.scroll_stories.winfo_children():
            widget.destroy()
            
        subreddit = self.combo_sub.get()
        
        def scrape_thread():
            import urllib.request
            import json
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=12"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/100.0.0.0'}
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as response:
                    data = json.loads(response.read().decode('utf-8'))
                stories = []
                for child in data.get("data", {}).get("children", []):
                    post = child.get("data", {})
                    if post.get("pinned") or post.get("stickied") or not post.get("selftext"):
                        continue
                    stories.append({
                        "title": post.get("title", ""),
                        "text": post.get("selftext", ""),
                        "score": post.get("score", 0),
                        "author": post.get("author", "")
                    })
                self.after(0, lambda: self.display_stories(stories))
            except Exception as e:
                self.after(0, lambda err=str(e): self.handle_error(err))
                
        threading.Thread(target=scrape_thread, daemon=True).start()

    def display_stories(self, stories):
        self.lbl_status.configure(text="Selecciona una historia para importarla como semilla", text_color="#00E676")
        
        if not stories:
            ctk.CTkLabel(self.scroll_stories, text="No se encontraron historias o Reddit bloqueó la conexión.", text_color="#FF8888").pack(pady=50)
            return

        for story in stories:
            card = ctk.CTkFrame(self.scroll_stories, fg_color="#121212", corner_radius=8, border_width=1, border_color="#1F1F1F")
            card.pack(fill="x", padx=10, pady=8)
            
            title_text = f"🔥 {story['title']} (Score: {story['score']}) - u/{story['author']}"
            ctk.CTkLabel(card, text=title_text, font=("Arial", 12, "bold"), text_color="white", anchor="w", justify="left", wrap="word").pack(anchor="w", padx=15, pady=(10, 5))
            
            # Vista previa corta
            preview = story['text']
            if len(preview) > 180:
                preview = preview[:177] + "..."
            
            ctk.CTkLabel(card, text=preview, font=("Arial", 11), text_color="#888", anchor="w", justify="left", wrap="word").pack(anchor="w", padx=15, pady=(0, 10))
            
            # Botón de importar
            def on_import(txt=story['text']):
                self.tab.entry_idea.delete("0.0", "end")
                self.tab.entry_idea.insert("0.0", txt[:2000])
                self.tab.update_status("📥 Historia importada de Reddit (Lista para editar).", "#00E676")
                self.destroy()

            ctk.CTkButton(card, text="IMPORTAR COMO SEMILLA", fg_color="#FF4500", hover_color="#CC3700", height=28, font=("Arial", 10, "bold"), command=on_import).pack(anchor="e", padx=15, pady=(0, 10))

    def handle_error(self, err_msg):
        self.lbl_status.configure(text=f"Error al conectar con Reddit: {err_msg[:45]}", text_color="red")
        ctk.CTkLabel(self.scroll_stories, text="Fallo de conexión.\nReddit podría estar limitando el tráfico temporalmente.", text_color="red", font=("Arial", 12)).pack(pady=50)
