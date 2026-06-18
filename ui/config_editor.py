import customtkinter as ctk
import os
import webbrowser
import config.prompts as prompts_cfg
from core.utils import get_resource_path

# --- THEME CONSTANTS ---
COLOR_BG = "#0A0A0A"
COLOR_SIDEBAR = "#111111"
COLOR_PANEL = "#161616"
COLOR_ACCENT = "#2962FF"      # Blue for tech/config feel
COLOR_ACCENT_HOVER = "#0039CB"
COLOR_SUCCESS = "#00C853"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_DIM = "#888888"
COLOR_BORDER = "#222"

FONT_HEADER = ("Impact", 24)
FONT_LABEL = ("Arial", 12, "bold")
FONT_MONO = ("Consolas", 13)

class ConfigEditor(ctk.CTkToplevel):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.main_window = parent_window
        
        self.title("CONFIGURACIÓN DEL SISTEMA | SILENCIO ROJO")
        self.geometry("1100x800")
        self.configure(fg_color=COLOR_BG)
        
        from core.utils import force_focus
        force_focus(self)
        
        self.current_tab = "API" # API, PROMPTS, PATHS
        
        self.setup_ui()
        self.load_current_values()

    def setup_ui(self):
        # Layout: Sidebar 20% | Content 80%
        self.grid_columnconfigure(0, weight=0, minsize=220)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="SETTINGS", font=("Impact", 30), text_color="#444").pack(pady=(30, 40))
        
        self.btn_api = self.create_nav_btn("🔑  API KEYS", "API")
        self.btn_paths = self.create_nav_btn("📂  RUTAS DE SISTEMA", "PATHS")
        self.btn_prompts = self.create_nav_btn("📝  PLANTILLAS PROMPT", "PROMPTS")
        
        # Footer Sidebar
        ctk.CTkLabel(self.sidebar, text=f"v10.0 Modular", font=("Arial", 10), text_color="#333").pack(side="bottom", pady=20)

        # --- CONTENT AREA ---
        self.content_area = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        
        # We will mount frames here dynamically
        self.frame_api = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        self.frame_paths = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        self.frame_prompts = ctk.CTkFrame(self.content_area, fg_color="transparent")
        
        self.init_api_ui()
        self.init_paths_ui()
        self.init_prompts_ui()
        
        # Bottom Save Bar
        self.save_bar = ctk.CTkFrame(self.content_area, fg_color="transparent", height=60)
        self.save_bar.pack(side="bottom", fill="x", pady=(20, 0))
        
        self.lbl_status = ctk.CTkLabel(self.save_bar, text="", text_color=COLOR_SUCCESS)
        self.lbl_status.pack(side="left", padx=10)
        
        self.btn_save = ctk.CTkButton(self.save_bar, text="GUARDAR CAMBIOS 💾", 
                                      fg_color=COLOR_SUCCESS, hover_color="#009624", text_color="black", font=("Arial", 12, "bold"),
                                      height=45, width=200, command=self.save_all)
        self.btn_save.pack(side="right")

        # Initial View
        self.show_tab("API")

    def create_nav_btn(self, text, code):
        btn = ctk.CTkButton(self.sidebar, text=text, anchor="w", fg_color="transparent", hover_color="#222", 
                            height=50, corner_radius=0, font=("Arial", 12, "bold"), text_color="#AAA",
                            command=lambda: self.show_tab(code))
        btn.pack(fill="x")
        return btn

    def show_tab(self, tab_code):
        self.current_tab = tab_code
        
        # Update Buttons
        # Update Buttons
        self.btn_api.configure(fg_color="#222" if tab_code == "API" else "transparent", text_color="white" if tab_code == "API" else "#AAA")
        self.btn_paths.configure(fg_color="#222" if tab_code == "PATHS" else "transparent", text_color="white" if tab_code == "PATHS" else "#AAA")
        self.btn_prompts.configure(fg_color="#222" if tab_code == "PROMPTS" else "transparent", text_color="white" if tab_code == "PROMPTS" else "#AAA")
        
        # Switch Frames
        self.frame_api.pack_forget()
        self.frame_paths.pack_forget()
        self.frame_prompts.pack_forget()
        
        if tab_code == "API":
            self.frame_api.pack(fill="both", expand=True)
        elif tab_code == "PATHS":
            self.frame_paths.pack(fill="both", expand=True)
        elif tab_code == "PROMPTS":
            self.frame_prompts.pack(fill="both", expand=True)

    # --- API UI ---
    def init_api_ui(self):
        f = self.frame_api
        
        ctk.CTkLabel(f, text="LLAVES DE ACCESO (API KEYS)", font=FONT_HEADER, text_color=COLOR_TEXT_MAIN).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(f, text="Configura las credenciales para los servicios de IA.", font=("Arial", 12), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 30))
        
        # LLM Provider Selection
        prov_frame = ctk.CTkFrame(f, fg_color="transparent")
        prov_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(prov_frame, text="MOTOR DE IA ACTIVO:", font=FONT_LABEL).pack(side="left", padx=(0, 15))
        self.seg_provider = ctk.CTkSegmentedButton(prov_frame, values=["gemini", "groq"], font=("Arial", 12, "bold"), selected_color=COLOR_ACCENT, selected_hover_color=COLOR_ACCENT_HOVER)
        self.seg_provider.pack(side="left")
        
        # Google Gemini
        card = ctk.CTkFrame(f, fg_color=COLOR_PANEL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card, text="GOOGLE GEMINI FLASH 2.0 (Google AI Studio)", font=FONT_LABEL, text_color="#4FC3F7").pack(anchor="w", padx=20, pady=(20, 5))
        
        self.entry_gemini = ctk.CTkEntry(card, placeholder_text="AIzaSq...", height=45, fg_color="#090909", border_color="#333", font=FONT_MONO)
        self.entry_gemini.pack(fill="x", padx=20, pady=(0, 20))
        
        link = ctk.CTkLabel(card, text="🔗 Conseguir API Key gratis aqui", font=("Arial", 10, "underline"), text_color="#666", cursor="hand2")
        link.pack(anchor="w", padx=20, pady=(0, 20))
        link.bind("<Button-1>", lambda e: webbrowser.open("https://aistudio.google.com/app/apikey"))

        # Groq
        card_groq = ctk.CTkFrame(f, fg_color=COLOR_PANEL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_groq.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_groq, text="GROQ API (Llama 3.3 Versatile)", font=FONT_LABEL, text_color="#F55036").pack(anchor="w", padx=20, pady=(20, 5))
        
        self.entry_groq = ctk.CTkEntry(card_groq, placeholder_text="gsk_...", height=45, fg_color="#090909", border_color="#333", font=FONT_MONO)
        self.entry_groq.pack(fill="x", padx=20, pady=(0, 20))
        
        link_groq = ctk.CTkLabel(card_groq, text="🔗 Conseguir API Key de Groq", font=("Arial", 10, "underline"), text_color="#666", cursor="hand2")
        link_groq.pack(anchor="w", padx=20, pady=(0, 20))
        link_groq.bind("<Button-1>", lambda e: webbrowser.open("https://console.groq.com/keys"))

        # Pexels
        card_pexels = ctk.CTkFrame(f, fg_color=COLOR_PANEL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_pexels.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_pexels, text="PEXELS API (Videos de Stock)", font=FONT_LABEL, text_color="#05A081").pack(anchor="w", padx=20, pady=(20, 5))
        
        self.entry_pexels = ctk.CTkEntry(card_pexels, placeholder_text="Tu API Key de Pexels...", height=45, fg_color="#090909", border_color="#333", font=FONT_MONO)
        self.entry_pexels.pack(fill="x", padx=20, pady=(0, 20))
        
        link_pexels = ctk.CTkLabel(card_pexels, text="🔗 Conseguir API Key de Pexels gratis", font=("Arial", 10, "underline"), text_color="#666", cursor="hand2")
        link_pexels.pack(anchor="w", padx=20, pady=(0, 20))
        link_pexels.bind("<Button-1>", lambda e: webbrowser.open("https://www.pexels.com/api/"))

        # TikTok API
        card_tiktok = ctk.CTkFrame(f, fg_color=COLOR_PANEL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_tiktok.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_tiktok, text="TIKTOK API V2 (Creador de Contenido)", font=FONT_LABEL, text_color="#FE2C55").pack(anchor="w", padx=20, pady=(20, 5))
        
        row_tt = ctk.CTkFrame(card_tiktok, fg_color="transparent")
        row_tt.pack(fill="x", padx=20, pady=(0, 10))
        
        col1 = ctk.CTkFrame(row_tt, fg_color="transparent")
        col1.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(col1, text="TikTok Client Key:", font=("Arial", 10, "bold"), text_color="#888").pack(anchor="w", pady=(0, 2))
        self.entry_tiktok_key = ctk.CTkEntry(col1, placeholder_text="Client Key...", height=40, fg_color="#090909", border_color="#333", font=FONT_MONO)
        self.entry_tiktok_key.pack(fill="x")
        
        col2 = ctk.CTkFrame(row_tt, fg_color="transparent")
        col2.pack(side="left", fill="x", expand=True, padx=(10, 0))
        ctk.CTkLabel(col2, text="TikTok Client Secret:", font=("Arial", 10, "bold"), text_color="#888").pack(anchor="w", pady=(0, 2))
        self.entry_tiktok_secret = ctk.CTkEntry(col2, placeholder_text="Client Secret...", height=40, fg_color="#090909", border_color="#333", font=FONT_MONO, show="*")
        self.entry_tiktok_secret.pack(fill="x")
        
        link_tt = ctk.CTkLabel(card_tiktok, text="🔗 Ir al TikTok Developer Portal", font=("Arial", 10, "underline"), text_color="#666", cursor="hand2")
        link_tt.pack(anchor="w", padx=20, pady=(0, 15))
        link_tt.bind("<Button-1>", lambda e: webbrowser.open("https://developers.tiktok.com/"))

    # --- PROMPTS UI ---
    def get_template_files(self, category):
        d = get_resource_path(os.path.join("config", "prompts", category))
        if not os.path.exists(d): return []
        return [f for f in os.listdir(d) if f.endswith(".txt")]
        
    def init_prompts_ui(self):
        f = self.frame_prompts
        
        ctk.CTkLabel(f, text="PLANTILLAS MAESTRAS (SYSTEM PROMPTS)", font=FONT_HEADER, text_color=COLOR_TEXT_MAIN).pack(anchor="w", pady=(0, 10))
        
        # Tabview for sub-sections
        self.ptabs = ctk.CTkTabview(f, fg_color=COLOR_PANEL, segmented_button_selected_color=COLOR_ACCENT, segmented_button_selected_hover_color=COLOR_ACCENT_HOVER)
        self.ptabs.pack(fill="both", expand=True, pady=10)
        
        t1 = self.ptabs.add("HISTORIA (P1)")
        t2 = self.ptabs.add("VISUALES (P2)")
        t3 = self.ptabs.add("PORTADA (P3)")
        t4 = self.ptabs.add("VOZ (P4)")
        
        # Version Selectors for ALL categories
        h1 = ctk.CTkFrame(t1, fg_color="transparent")
        h1.pack(fill="x", pady=5)
        story_files = self.get_template_files("story")
        self.combo_story = ctk.CTkOptionMenu(h1, values=story_files if story_files else ["None"], command=self.on_story_template_change)
        self.combo_story.pack(side="right")
        ctk.CTkLabel(h1, text="Plantilla Historia: ", font=FONT_LABEL).pack(side="right", padx=10)

        h2 = ctk.CTkFrame(t2, fg_color="transparent")
        h2.pack(fill="x", pady=5)
        visual_files = self.get_template_files("visuals")
        self.combo_visual = ctk.CTkOptionMenu(h2, values=visual_files if visual_files else ["None"], command=self.on_visual_template_change)
        self.combo_visual.pack(side="right")
        ctk.CTkLabel(h2, text="Plantilla Visuales: ", font=FONT_LABEL).pack(side="right", padx=10)

        h3 = ctk.CTkFrame(t3, fg_color="transparent")
        h3.pack(fill="x", pady=5)
        cover_files = self.get_template_files("cover")
        self.combo_cover = ctk.CTkOptionMenu(h3, values=cover_files if cover_files else ["None"], command=self.on_cover_template_change)
        self.combo_cover.pack(side="right")
        ctk.CTkLabel(h3, text="Plantilla Portada: ", font=FONT_LABEL).pack(side="right", padx=10)

        h4 = ctk.CTkFrame(t4, fg_color="transparent")
        h4.pack(fill="x", pady=5)
        voice_files = self.get_template_files("voice")
        self.combo_voice = ctk.CTkOptionMenu(h4, values=voice_files if voice_files else ["None"], command=self.on_voice_template_change)
        self.combo_voice.pack(side="right")
        ctk.CTkLabel(h4, text="Plantilla Voz: ", font=FONT_LABEL).pack(side="right", padx=10)
        
        # Editors
        self.txt_p1 = self.create_editor(t1)
        self.txt_p2 = self.create_editor(t2)
        self.txt_p3 = self.create_editor(t3)
        self.txt_p4 = self.create_editor(t4)
        
    def on_story_template_change(self, filename):
        pth = get_resource_path(os.path.join("config", "prompts", "story", filename))
        txt = self.read_file_safe(pth, "")
        self.txt_p1.delete("0.0", "end"); self.txt_p1.insert("0.0", txt); self.highlight_syntax(self.txt_p1)

    def on_visual_template_change(self, filename):
        pth = get_resource_path(os.path.join("config", "prompts", "visuals", filename))
        txt = self.read_file_safe(pth, "")
        self.txt_p2.delete("0.0", "end"); self.txt_p2.insert("0.0", txt); self.highlight_syntax(self.txt_p2)

    def on_cover_template_change(self, filename):
        pth = get_resource_path(os.path.join("config", "prompts", "cover", filename))
        txt = self.read_file_safe(pth, "")
        self.txt_p3.delete("0.0", "end"); self.txt_p3.insert("0.0", txt); self.highlight_syntax(self.txt_p3)

    def on_voice_template_change(self, filename):
        pth = get_resource_path(os.path.join("config", "prompts", "voice", filename))
        txt = self.read_file_safe(pth, "")
        self.txt_p4.delete("0.0", "end"); self.txt_p4.insert("0.0", txt); self.highlight_syntax(self.txt_p4)

    # --- PATHS UI ---
    def init_paths_ui(self):
        f = self.frame_paths
        
        ctk.CTkLabel(f, text="RUTAS DE SISTEMA", font=FONT_HEADER, text_color=COLOR_TEXT_MAIN).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(f, text="Configura las carpetas predeterminadas para buscar archivos.", font=("Arial", 12), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 30))
        
        # Audio Folder
        card_audio = ctk.CTkFrame(f, fg_color=COLOR_PANEL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_audio.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_audio, text="CARPETA DE AUDIOS / NARRACIONES", font=FONT_LABEL, text_color="#FFA726").pack(anchor="w", padx=20, pady=(20, 5))
        
        row_audio = ctk.CTkFrame(card_audio, fg_color="transparent")
        row_audio.pack(fill="x", padx=20, pady=(0, 20))
        
        self.entry_audio_path = ctk.CTkEntry(row_audio, placeholder_text=r"D:\Descargas\Audio", height=40, fg_color="#090909", border_color="#333", font=FONT_MONO)
        self.entry_audio_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(row_audio, text="📂", width=40, height=40, fg_color="#333", hover_color="#444", 
                      command=lambda: self.browse_folder(self.entry_audio_path)).pack(side="right")

        # Images Folder
        card_imgs = ctk.CTkFrame(f, fg_color=COLOR_PANEL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_imgs.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_imgs, text="CARPETA DE IMÁGENES / PORTADAS", font=FONT_LABEL, text_color="#AB47BC").pack(anchor="w", padx=20, pady=(20, 5))
        
        row_imgs = ctk.CTkFrame(card_imgs, fg_color="transparent")
        row_imgs.pack(fill="x", padx=20, pady=(0, 20))
        
        self.entry_imgs_path = ctk.CTkEntry(row_imgs, placeholder_text=r"D:\Descargas\Imagenes", height=40, fg_color="#090909", border_color="#333", font=FONT_MONO)
        self.entry_imgs_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(row_imgs, text="📂", width=40, height=40, fg_color="#333", hover_color="#444",
                      command=lambda: self.browse_folder(self.entry_imgs_path)).pack(side="right")

        # Videos Folder
        card_vids = ctk.CTkFrame(f, fg_color=COLOR_PANEL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_vids.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_vids, text="CARPETA DE VIDEOS / CLIPS", font=FONT_LABEL, text_color="#EF5350").pack(anchor="w", padx=20, pady=(20, 5))
        
        row_vids = ctk.CTkFrame(card_vids, fg_color="transparent")
        row_vids.pack(fill="x", padx=20, pady=(0, 20))
        
        self.entry_vids_path = ctk.CTkEntry(row_vids, placeholder_text=r"D:\Descargas\Videos", height=40, fg_color="#090909", border_color="#333", font=FONT_MONO)
        self.entry_vids_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(row_vids, text="📂", width=40, height=40, fg_color="#333", hover_color="#444",
                      command=lambda: self.browse_folder(self.entry_vids_path)).pack(side="right")

    def browse_folder(self, entry_widget):
        from tkinter import filedialog
        path = filedialog.askdirectory()
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    # --- SYNTAX HIGHLIGHTING ---
    def create_editor(self, parent):
        # Container
        container = ctk.CTkFrame(parent, fg_color="#1E1E1E", corner_radius=8, border_width=1, border_color="#333")
        container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="#252526", height=25, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text=" SYSTEM PROMPT ", font=("Consolas", 10, "bold"), text_color="#569CD6").pack(side="left", padx=10)

        # Textbox
        txt = ctk.CTkTextbox(container, 
                             font=("Consolas", 14), 
                             fg_color="#1E1E1E", 
                             text_color="#D4D4D4", 
                             wrap="word", 
                             border_width=0,
                             corner_radius=0)
        txt.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        # Bind for live highlighting
        txt.bind("<KeyRelease>", lambda e: self.highlight_syntax(txt))
        return txt

    def highlight_syntax(self, textbox):
        """Applies faux-syntax highlighting to CTkTextbox"""
        try:
            # Access underlying tkinter Text widget
            text_widget = textbox._textbox
            full_text = text_widget.get("1.0", "end")
            
            # 1. Clean old tags
            tags = ["tag_var", "tag_header", "tag_key", "tag_quote", "tag_number"]
            for tag in tags:
                text_widget.tag_remove(tag, "1.0", "end")
            
            # 2. Define Styles (VS Code / Monokai ish)
            # Variables {TRAMA} -> Pink/Magenta
            text_widget.tag_config("tag_var", foreground="#C586C0", font=("Consolas", 14, "bold")) 
            # Headers [SECTION] -> Blue
            text_widget.tag_config("tag_header", foreground="#569CD6", font=("Consolas", 14, "bold"))
            # Keys INPUT: -> Light Blue
            text_widget.tag_config("tag_key", foreground="#9CDCFE")
            # Quotes "..." -> Orange/Brown
            text_widget.tag_config("tag_quote", foreground="#CE9178")
            # Numbers 1. -> Green
            text_widget.tag_config("tag_number", foreground="#B5CEA8")

            # 3. Apply Regex Patterns
            import re
            
            # Pattern: {VARIABLE}
            for match in re.finditer(r"\{[^}]+\}", full_text):
                text_widget.tag_add("tag_var", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

            # Pattern: [SECTION]
            for match in re.finditer(r"\[.+?\]", full_text):
                text_widget.tag_add("tag_header", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

            # Pattern: ITEM: (Start of line)
            for match in re.finditer(r"^[A-Z0-9 _]+:", full_text, re.MULTILINE):
                text_widget.tag_add("tag_key", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

            # Pattern: Quotes
            for match in re.finditer(r'".*?"', full_text):
                 text_widget.tag_add("tag_quote", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

        except Exception as e:
            print(f"Highlight Error: {e}")

    # --- LOGIC ---
    def load_current_values(self):
        # API Key
        key = getattr(self.main_window, "google_api_key", "")
        if key: self.entry_gemini.insert(0, key)
        
        groq_key = getattr(self.main_window, "groq_api_key", "")
        if groq_key: self.entry_groq.insert(0, groq_key)
        
        pexels_key = getattr(self.main_window, "pexels_api_key", "")
        if pexels_key: self.entry_pexels.insert(0, pexels_key)
        
        tiktok_key = getattr(self.main_window, "tiktok_client_key", "")
        if tiktok_key: self.entry_tiktok_key.insert(0, tiktok_key)
        
        tiktok_secret = getattr(self.main_window, "tiktok_client_secret", "")
        if tiktok_secret: self.entry_tiktok_secret.insert(0, tiktok_secret)
        
        provider = getattr(self.main_window, "llm_provider", "gemini")
        self.seg_provider.set(provider)
        
        # Paths
        settings = self.main_window.settings
        audio_path = settings.get("audio_folder_path", r"D:\Descargas\Audio")
        imgs_path = settings.get("images_folder_path", r"D:\Descargas\Imagenes")
        vids_path = settings.get("videos_folder_path", r"D:\Descargas\Videos") # Default
        
        self.entry_audio_path.insert(0, audio_path)
        self.entry_imgs_path.insert(0, imgs_path)
        self.entry_vids_path.insert(0, vids_path)
        
        # Prompts Combos
        story_file = settings.get("story_template", prompts_cfg.DEFAULT_STORY_FILE)
        visual_file = settings.get("visual_template", prompts_cfg.DEFAULT_VISUAL_FILE)
        cover_file = settings.get("cover_template", prompts_cfg.DEFAULT_COVER_FILE)
        voice_file = settings.get("voice_template", prompts_cfg.DEFAULT_VOICE_FILE)
        
        self.combo_story.set(story_file)
        self.combo_visual.set(visual_file)
        self.combo_cover.set(cover_file)
        self.combo_voice.set(voice_file)

        # Prompts (Insert & Highlight)
        p1 = self.read_file_safe(prompts_cfg.STORY_TEMPLATE_PATH, prompts_cfg.STORY_PROMPT_TEMPLATE)
        self.txt_p1.insert("0.0", p1)
        self.highlight_syntax(self.txt_p1)
        
        p2 = self.read_file_safe(prompts_cfg.VISUAL_TEMPLATE_PATH, prompts_cfg.VISUAL_PROMPT_TEMPLATE)
        self.txt_p2.insert("0.0", p2)
        self.highlight_syntax(self.txt_p2)
        
        p3 = self.read_file_safe(prompts_cfg.COVER_TEMPLATE_PATH, prompts_cfg.COVER_PROMPT_TEMPLATE)
        self.txt_p3.insert("0.0", p3)
        self.highlight_syntax(self.txt_p3)
        
        # Voice Instructions (Insert & Highlight)
        p4 = self.read_file_safe(prompts_cfg.VOICE_TEMPLATE_PATH, prompts_cfg.VOICE_PROMPT_TEMPLATE)
        self.txt_p4.insert("0.0", p4)
        self.highlight_syntax(self.txt_p4)

    def read_file_safe(self, path, fallback):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: return f.read()
        return fallback

    def save_all(self):
        # 1. API Key & Provider
        new_key = self.entry_gemini.get().strip()
        self.main_window.google_api_key = new_key
        
        new_groq = self.entry_groq.get().strip()
        self.main_window.groq_api_key = new_groq
        
        new_pexels = self.entry_pexels.get().strip()
        self.main_window.pexels_api_key = new_pexels
        
        new_tiktok_key = self.entry_tiktok_key.get().strip()
        self.main_window.tiktok_client_key = new_tiktok_key
        
        new_tiktok_secret = self.entry_tiktok_secret.get().strip()
        self.main_window.tiktok_client_secret = new_tiktok_secret
        
        self.main_window.settings["tiktok_client_key"] = new_tiktok_key
        self.main_window.settings["tiktok_client_secret"] = new_tiktok_secret
        
        self.main_window.llm_provider = self.seg_provider.get()
        # Note: save_settings_to_file is called after updating dict below
        
        # 2. Paths
        audio_path = self.entry_audio_path.get().strip()
        imgs_path = self.entry_imgs_path.get().strip()
        vids_path = self.entry_vids_path.get().strip()
        
        self.main_window.settings["audio_folder_path"] = audio_path
        self.main_window.settings["images_folder_path"] = imgs_path
        self.main_window.settings["videos_folder_path"] = vids_path
        
        self.main_window.save_settings_to_file()
        
        # 3. Prompts
        p1_file = self.combo_story.get()
        p2_file = self.combo_visual.get()
        p3_file = self.combo_cover.get()
        p4_file = self.combo_voice.get()
        
        self.main_window.settings["story_template"] = p1_file
        self.main_window.settings["visual_template"] = p2_file
        self.main_window.settings["cover_template"] = p3_file
        self.main_window.settings["voice_template"] = p4_file
        self.main_window.save_settings_to_file()
        
        p1 = self.txt_p1.get("0.0", "end").strip()
        p2 = self.txt_p2.get("0.0", "end").strip()
        p3 = self.txt_p3.get("0.0", "end").strip()
        p4 = self.txt_p4.get("0.0", "end").strip()
        
        try:
            path_p1 = get_resource_path(os.path.join(prompts_cfg.PROMPTS_ROOT, "story", p1_file))
            path_p2 = get_resource_path(os.path.join(prompts_cfg.PROMPTS_ROOT, "visuals", p2_file))
            path_p3 = get_resource_path(os.path.join(prompts_cfg.PROMPTS_ROOT, "cover", p3_file))
            path_p4 = get_resource_path(os.path.join(prompts_cfg.PROMPTS_ROOT, "voice", p4_file))
            
            with open(path_p1, "w", encoding="utf-8") as f: f.write(p1)
            with open(path_p2, "w", encoding="utf-8") as f: f.write(p2)
            with open(path_p3, "w", encoding="utf-8") as f: f.write(p3)
            with open(path_p4, "w", encoding="utf-8") as f: f.write(p4)
            
            # Update memory refs
            prompts_cfg.update_paths_from_settings()

            self.lbl_status.configure(text="✅ CAMBIOS GUARDADOS CORRECTAMENTE")
            self.after(2000, lambda: self.lbl_status.configure(text=""))
            
        except Exception as e:
            self.lbl_status.configure(text=f"ERROR: {e}", text_color="red")
