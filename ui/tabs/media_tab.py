import customtkinter as ctk
import os
import threading
import subprocess
import random
from tkinter import filedialog
from PIL import Image
import queue

# Intentar importar dependencias del proyecto
try:
    from modules.video_render import render_final_video
    from modules.youtube_uploader import upload_video
except ImportError:
    pass

# --- PRO DESIGNER THEME (NEON HORROR) ---
COLOR_BG = "#020202"           # Absolute Black
COLOR_PANEL_BG = "#050505"     # Deep Charcoal
COLOR_CARD_BG = "#080808"      # Card Surface
COLOR_CARD_BORDER = "#141414"
COLOR_ACCENT = "#FF0000"       # Pure Neon Red
COLOR_ACCENT_HOVER = "#FF5252" # Light Red
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_SEC = "#666666"
COLOR_SUCCESS = "#00FF66"

FONT_MAIN = ("Inter", 12)
FONT_BOLD = ("Inter", 12, "bold")
FONT_HEADER = ("Impact", 32)
FONT_SECTION = ("Inter Medium", 13)

class MediaTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main = main_window
        try:
            # Estado - RUTA FORZADA A ASSETS (Prioridad absoluta del usuario)
            self.music_folder = os.path.abspath(os.path.join(os.getcwd(), "assets", "audio", "music"))
            if not os.path.exists(self.music_folder):
                try: os.makedirs(self.music_folder)
                except: pass
                
            self.assets_audio_folder = getattr(self.main, "assets_audio_folder", os.path.join(os.getcwd(), "assets"))
            self.img_download_folder = getattr(self.main, "img_download_folder", os.path.join(os.getcwd(), "assets"))
            
            self.audio_path = ""
            self.mixed_media = [] # Lista maestra unificada de activos
            self.media_mode = "mix" # MODO ÚNICO Y ESTÁNDAR
            self.video_format = "9:16" # FORMATO POR DEFECTO
            self.cover_path = ""
            self.current_music_path = ""
            self.preview_process = None
            self.thumbnails = {}
            self.image_labels = {}
            self.last_render_path = ""
            self.thumbnail_queue = queue.Queue()

            self.setup_ui()
            
            if os.path.exists(self.music_folder):
                self.reroll_music(silent=True)
            
            self.after(2000, self.check_layout_health)
            self.after(100, self.process_thumbnail_queue)
        except Exception as e:
            print(f">>> [MEDIA TAB ERROR]: {e}")

    def check_layout_health(self):
        try:
            print(f">>> [MEDIA_TAB] Width: {self.winfo_width()}px | Req: {self.winfo_reqwidth()}px")
        except: pass

    def setup_ui(self):
        # Grid Layout: Panel Control (Fijo) | Área de Trabajo (Elástico)
        self.grid_columnconfigure(0, weight=0, minsize=350) 
        self.grid_columnconfigure(1, weight=1)              
        self.grid_rowconfigure(0, weight=1)

        # === PANEL DE CONTROL (CORE ENGINE) ===
        self.left_container = ctk.CTkScrollableFrame(self, fg_color=COLOR_PANEL_BG, corner_radius=0, border_width=1, border_color="#111")
        self.left_container.grid(row=0, column=0, sticky="nsew")
        self.setup_left_panel(self.left_container)

        # === ÁREA DE PRODUCCIÓN (CANVAS) ===
        self.right_container = ctk.CTkFrame(self, fg_color="transparent")
        self.right_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.setup_right_panel(self.right_container)

    def create_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=12, border_width=1, border_color=COLOR_CARD_BORDER)
        card.pack(fill="x", padx=15, pady=10)
        
        lbl = ctk.CTkLabel(card, text=title, font=("Inter", 10, "bold"), text_color=COLOR_TEXT_SEC)
        lbl.pack(anchor="w", padx=15, pady=(12, 5))
        return card

    def setup_left_panel(self, parent):
        # Header del Engine
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=25, pady=(35, 15))
        
        ctk.CTkLabel(header, text="STUDIO", font=("Impact", 18), text_color=COLOR_ACCENT, anchor="w").pack(side="left")
        ctk.CTkLabel(header, text="CORE", font=("Impact", 18), text_color="white", anchor="w").pack(side="left", padx=5)

        # --- NARRACIÓN (VOICE) ---
        card_v = self.create_card(parent, "VOZ Y NARRACIÓN")
        self.btn_audio = ctk.CTkButton(card_v, text="📁 SELECCIONAR NARRACIÓN", 
                                       fg_color="#111", hover_color="#181818", border_width=1, border_color="#222",
                                       height=38, font=("Inter", 11, "bold"), command=self.select_audio)
        self.btn_audio.pack(fill="x", padx=15, pady=(5, 8))
        
        self.lbl_audio_name = ctk.CTkLabel(card_v, text="No hay audio activo", font=("Consolas", 10), text_color="#444")
        self.lbl_audio_name.pack(pady=(0, 10))

        # --- DISEÑO SONORO (BGM) ---
        card_m = self.create_card(parent, "AMBIENTACIÓN (BGM)")
        self.var_music = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card_m, text="ACTIVO", variable=self.var_music, 
                        fg_color=COLOR_ACCENT, border_width=2, font=("Inter", 10, "bold")).pack(anchor="w", padx=15, pady=5)
        
        self.combo_music = ctk.CTkComboBox(card_m, values=["Cargando..."], command=self.on_music_manual_select,
                                           fg_color="#050505", border_color="#181818", button_color="#111", 
                                           text_color=COLOR_ACCENT, font=("Consolas", 11), height=35)
        self.combo_music.pack(fill="x", padx=15, pady=5)
        
        row_m = ctk.CTkFrame(card_m, fg_color="transparent")
        row_m.pack(fill="x", padx=15, pady=(5, 15))
        
        b_sty = {"height": 30, "fg_color": "#0F0F0F", "hover_color": "#151515", "border_width": 1, "border_color": "#222", "font": ("Arial", 11, "bold")}
        ctk.CTkButton(row_m, text="▶", width=40, command=self.play_preview, **b_sty).pack(side="left", padx=(0, 4), expand=True, fill="x")
        ctk.CTkButton(row_m, text="⏸", width=40, command=self.stop_preview, **b_sty).pack(side="left", padx=4, expand=True, fill="x")
        ctk.CTkButton(row_m, text="🎲", width=40, command=self.reroll_music, **b_sty).pack(side="left", padx=(4, 0), expand=True, fill="x")

        # --- FILTRO VISUAL (LUT) ---
        card_l = self.create_card(parent, "FILTRO VISUAL (LUT)")
        self.combo_luts = ctk.CTkComboBox(card_l, values=["Ninguno", "Gore Rojo", "Terror Frío", "Misterio Oscuro", "Vintage VHS"],
                                           fg_color="#050505", border_color="#181818", button_color="#111", 
                                           text_color="white", font=("Inter", 11), height=35)
        self.combo_luts.pack(fill="x", padx=15, pady=(5, 15))
        self.combo_luts.set("Ninguno")

        # --- ESTILO DE SUBTÍTULOS ---
        card_sub = self.create_card(parent, "ESTILO DE SUBTÍTULOS")
        self.combo_sub_style = ctk.CTkComboBox(card_sub, values=["TikTok / Hormozi", "Reddit History"],
                                               fg_color="#050505", border_color="#181818", button_color="#111", 
                                               text_color="white", font=("Inter", 11), height=35)
        self.combo_sub_style.pack(fill="x", padx=15, pady=(5, 15))
        self.combo_sub_style.set("TikTok / Hormozi")

        # --- RITMO VISUAL ---
        card_pacing = self.create_card(parent, "RITMO DE EDICIÓN VISUAL")
        self.combo_pacing = ctk.CTkComboBox(card_pacing, values=["Ultra Rápido [1.2s]", "Dinámico [2.0s]", "Estándar [2.8s]"],
                                             fg_color="#050505", border_color="#181818", button_color="#111", 
                                             text_color="white", font=("Inter", 11), height=35)
        self.combo_pacing.pack(fill="x", padx=15, pady=(5, 15))
        self.combo_pacing.set("Dinámico [2.0s]")

        # --- MEZCLA DE AUDIO ---
        card_audio_mix = self.create_card(parent, "VOLUMEN DE MEZCLA AUDIO")
        
        # Slider Voz
        f_v = ctk.CTkFrame(card_audio_mix, fg_color="transparent")
        f_v.pack(fill="x", padx=15, pady=2)
        ctk.CTkLabel(f_v, text="Voz Narración", font=("Inter", 10), text_color="white").pack(side="left")
        self.lbl_vol_voice = ctk.CTkLabel(f_v, text="100%", font=("Inter", 10), text_color=COLOR_TEXT_SEC)
        self.lbl_vol_voice.pack(side="right")
        self.slider_voice = ctk.CTkSlider(card_audio_mix, from_=0, to=150, number_of_steps=30,
                                          fg_color="#080808", progress_color=COLOR_ACCENT, button_color=COLOR_ACCENT,
                                          command=lambda v: self.lbl_vol_voice.configure(text=f"{int(v)}%"))
        self.slider_voice.pack(fill="x", padx=15, pady=(0, 8))
        self.slider_voice.set(100)
        
        # Slider Música
        f_m = ctk.CTkFrame(card_audio_mix, fg_color="transparent")
        f_m.pack(fill="x", padx=15, pady=2)
        ctk.CTkLabel(f_m, text="Música BGM", font=("Inter", 10), text_color="white").pack(side="left")
        self.lbl_vol_music = ctk.CTkLabel(f_m, text="40%", font=("Inter", 10), text_color=COLOR_TEXT_SEC)
        self.lbl_vol_music.pack(side="right")
        self.slider_music = ctk.CTkSlider(card_audio_mix, from_=0, to=100, number_of_steps=20,
                                          fg_color="#080808", progress_color=COLOR_ACCENT, button_color=COLOR_ACCENT,
                                          command=lambda v: self.lbl_vol_music.configure(text=f"{int(v)}%"))
        self.slider_music.pack(fill="x", padx=15, pady=(0, 8))
        self.slider_music.set(40)
        
        # Slider SFX
        f_s = ctk.CTkFrame(card_audio_mix, fg_color="transparent")
        f_s.pack(fill="x", padx=15, pady=2)
        ctk.CTkLabel(f_s, text="Efectos SFX", font=("Inter", 10), text_color="white").pack(side="left")
        self.lbl_vol_sfx = ctk.CTkLabel(f_s, text="100%", font=("Inter", 10), text_color=COLOR_TEXT_SEC)
        self.lbl_vol_sfx.pack(side="right")
        self.slider_sfx = ctk.CTkSlider(card_audio_mix, from_=0, to=150, number_of_steps=30,
                                        fg_color="#080808", progress_color=COLOR_ACCENT, button_color=COLOR_ACCENT,
                                        command=lambda v: self.lbl_vol_sfx.configure(text=f"{int(v)}%"))
        self.slider_sfx.pack(fill="x", padx=15, pady=(0, 12))
        self.slider_sfx.set(100)

        self.refresh_music_list()

    def setup_right_panel(self, parent):
        # --- TOP: METADATOS (MODERN BAR) ---
        meta_bar = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=15, border_width=1, border_color=COLOR_CARD_BORDER)
        meta_bar.pack(side="top", fill="x", pady=(0, 10))
        
        meta_left = ctk.CTkFrame(meta_bar, fg_color="transparent")
        meta_left.pack(side="left", fill="both", expand=True, padx=20, pady=15)
        
        ctk.CTkLabel(meta_left, text="TÍTULO DEL PROYECTO", font=("Inter", 9, "bold"), text_color=COLOR_TEXT_SEC).pack(anchor="w")
        self.entry_title = ctk.CTkEntry(meta_left, placeholder_text="Nombre del video...", height=35, 
                                        fg_color="transparent", border_width=0, font=("Inter", 16, "bold"), text_color="white")
        self.entry_title.pack(fill="x", pady=(2, 8))
        
        ctk.CTkLabel(meta_left, text="TÍTULO DE TARJETA REDDIT (GANCHO VISUAL)", font=("Inter", 9, "bold"), text_color=COLOR_TEXT_SEC).pack(anchor="w")
        self.entry_card_title = ctk.CTkEntry(meta_left, placeholder_text="Ej: Confesión anónima: No juegues esto en auto 🤫 (Dejar vacío para título limpio)", height=35, 
                                             fg_color="#050505", border_width=1, border_color="#151515", font=("Inter", 11), text_color="white")
        self.entry_card_title.pack(fill="x", pady=(2, 8))
        
        ctk.CTkLabel(meta_left, text="DESCRIPCIÓN OPTIMIZADA", font=("Inter", 9, "bold"), text_color=COLOR_TEXT_SEC).pack(anchor="w")
        self.txt_desc = ctk.CTkTextbox(meta_left, height=60, fg_color="#050505", border_width=1, border_color="#151515", font=("Inter", 11))
        self.txt_desc.pack(fill="x", pady=(5, 0))
        
        # --- SELECTOR DE FORMATO (NUEVA UBICACIÓN) ---
        meta_right = ctk.CTkFrame(meta_bar, fg_color="transparent")
        meta_right.pack(side="right", padx=20, pady=15)
        
        ctk.CTkLabel(meta_right, text="FORMATO DE SALIDA", font=("Inter", 9, "bold"), text_color=COLOR_TEXT_SEC).pack(anchor="e")
        self.seg_format = ctk.CTkSegmentedButton(meta_right, values=["9:16", "16:9"], 
                                                 command=self.on_format_change,
                                                 fg_color="#050505", selected_color=COLOR_ACCENT,
                                                 selected_hover_color=COLOR_ACCENT_HOVER,
                                                 unselected_color="#111", unselected_hover_color="#181818",
                                                 font=("Inter", 11, "bold"), height=35, width=120)
        self.seg_format.pack(pady=(5, 0))
        self.seg_format.set("9:16")
        
        self.btn_viral = ctk.CTkButton(meta_right, text="Metadatos Virales ⚡", 
                                       command=self.run_viral_generation,
                                       fg_color="#4B0082", hover_color="#37006B",
                                       font=("Inter", 11, "bold"), height=35, width=120)
        self.btn_viral.pack(pady=(10, 0))
        
        # Tags ocultos o compactos (por simplicidad en este rediseño)
        self.entry_tags = ctk.CTkEntry(meta_bar, width=0, height=0) 

        # --- BOTTOM: ACTION BAR (Pack first at the bottom so it never gets cut off) ---
        action_bar = ctk.CTkFrame(parent, fg_color="transparent", height=100)
        action_bar.pack(side="bottom", fill="x", pady=(10, 0))
        
        status_frame = ctk.CTkFrame(action_bar, fg_color="#080808", corner_radius=12, border_width=1, border_color="#111")
        status_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))
        
        self.lbl_status = ctk.CTkLabel(status_frame, text="ESPERANDO CONFIGURACIÓN...", font=("Inter", 11, "bold"), text_color="#888")
        self.lbl_status.pack(pady=(15, 5))
        
        self.progress_render = ctk.CTkProgressBar(status_frame, fg_color="#111", progress_color=COLOR_ACCENT, height=6)
        self.progress_render.pack(fill="x", padx=20, pady=(0, 15))
        self.progress_render.set(0)
        
        self.btn_render = ctk.CTkButton(action_bar, text="INICIAR RENDERIZADO", width=220, height=60, 
                                        fg_color="#333", state="disabled", font=("Arial", 13, "bold"), 
                                        corner_radius=12, command=self.on_render_click)
        self.btn_render.pack(side="left")
        
        self.btn_upload = ctk.CTkButton(action_bar, text="SUBIR A SHORTS", width=180, height=60,
                                        fg_color="#002211", text_color="#00FF66", state="disabled", 
                                        font=("Arial", 13, "bold"), corner_radius=12, command=self.on_upload_click)
        self.btn_upload.pack(side="left", padx=(15, 0))

        # Barra de Ordenar (Sits above the bottom action bar)
        sort_bar = ctk.CTkFrame(parent, fg_color="transparent")
        sort_bar.pack(side="bottom", fill="x", pady=(5, 0))
        ctk.CTkLabel(sort_bar, text="ORDENAR POR:", font=("Inter", 9, "bold"), text_color="#333").pack(side="left", padx=10)
        ctk.CTkButton(sort_bar, text="FECHA", width=60, height=20, font=("Inter", 8, "bold"), fg_color="#080808", command=lambda: self.sort_media("date")).pack(side="left", padx=2)
        ctk.CTkButton(sort_bar, text="NOMBRE", width=60, height=20, font=("Inter", 8, "bold"), fg_color="#080808", command=lambda: self.sort_media("name")).pack(side="left", padx=2)

        # --- CENTER: TIMELINE (THE GRID) ---
        timeline_header = ctk.CTkFrame(parent, fg_color="transparent")
        timeline_header.pack(side="top", fill="x", pady=(0, 5))
        
        ctk.CTkLabel(timeline_header, text="VISUAL TIMELINE", font=("Impact", 24), text_color="white").pack(side="left")
        
        tool_bar = ctk.CTkFrame(timeline_header, fg_color="transparent")
        tool_bar.pack(side="right")
        
        btn_s = {"height": 28, "font": ("Inter", 10, "bold"), "fg_color": "#111", "hover_color": "#181818", "border_width": 1, "border_color": "#222"}
        ctk.CTkButton(tool_bar, text="+ MEDIA", command=self.select_media, **btn_s).pack(side="left", padx=5)
        
        btn_p = {"height": 28, "font": ("Inter", 10, "bold"), "fg_color": "#05A081", "hover_color": "#048067", "text_color": "white"}
        self.btn_pexels = ctk.CTkButton(tool_bar, text="🤖 AUTO STOCK", command=self.auto_stock_pexels, **btn_p)
        self.btn_pexels.pack(side="left", padx=5)
        
        btn_g = {"height": 28, "font": ("Inter", 10, "bold"), "fg_color": "#651FFF", "hover_color": "#4500C7", "text_color": "white"}
        self.btn_gameplay = ctk.CTkButton(tool_bar, text="🎮 AUTO GAMEPLAY", command=self.open_gameplay_dialog, **btn_g)
        self.btn_gameplay.pack(side="left", padx=5)
        
        ctk.CTkButton(tool_bar, text="🖼️ PORTADA", command=self.select_cover, **btn_s).pack(side="left", padx=5)
        
        self.lbl_cover_preview = ctk.CTkLabel(tool_bar, text="", width=30)
        self.lbl_cover_preview.pack(side="left", padx=5)
        
        # Botón de borrar explícito para evitar conflictos de argumentos duplicados
        ctk.CTkButton(tool_bar, text="🗑️", width=35, height=28,
                      fg_color="#1A0505", hover_color="#300", text_color="#F33", 
                      font=("Inter", 10, "bold"), border_width=1, border_color="#222",
                      command=self.clear_media).pack(side="left", padx=5)

        # --- MIDDLE: LINEA DE TIEMPO (AHORA CUADRÍCULA VERTICAL) ---
        self.scroll_grid = ctk.CTkScrollableFrame(parent, fg_color="#0a0a0a", corner_radius=15, 
                                                 border_width=1, border_color="#1a1a1a", orientation="vertical")
        self.scroll_grid.pack(side="top", fill="both", expand=True)
        
        # Configurar columnas para la cuadrícula
        self.cols = 6 # Ajustamos a 6 columnas por fila
        for i in range(self.cols):
            self.scroll_grid.grid_columnconfigure(i, weight=1)

    # --- UI CALLBACKS ---
    def on_format_change(self, value):
        self.video_format = value
        self.lbl_status.configure(text=f"MODO CAMBIADO A {value}", text_color=COLOR_ACCENT)
        # Podríamos añadir lógica aquí para refrescar miniaturas si fuera necesario

    # --- UI HELPERS ---
    # Ya no necesitamos create_card redundante ni animaciones viejas


    # --- REFRESH GRID (REDESIGNED ASYNC) ---
    def refresh_grid(self):
        # Limpiar widgets actuales
        for widget in self.scroll_grid.winfo_children():
            widget.destroy()
            
        self.image_labels = {}
        active_list = self.mixed_media

        if not active_list:
            self.lbl_placeholder = ctk.CTkLabel(self.scroll_grid, text="ARRASTRA O AÑADE TUS ACTIVOS", text_color="#222", font=("Impact", 30))
            self.lbl_placeholder.pack(pady=100)
            return

        for i, item in enumerate(active_list):
            path = item.get("path", "") if isinstance(item, dict) else item
            m_type = item.get("type", "image") if isinstance(item, dict) else "image"
            
            # Usar grid con cálculo de fila/columna
            row = i // self.cols
            col = i % self.cols
            
            item_frame = ctk.CTkFrame(self.scroll_grid, fg_color="#111", corner_radius=10, width=150)
            item_frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            item_frame.pack_propagate(False)

            # --- VISTA PREVIA ---
            img_to_show = "⌛"
            text_to_show = "⌛"
            
            if path in self.thumbnails:
                pil_img = self.thumbnails[path]
                img_to_show = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(110, 110))
                text_to_show = ""

            lbl_img = ctk.CTkLabel(item_frame, text=text_to_show, image=img_to_show if isinstance(img_to_show, ctk.CTkImage) else None,
                                  width=140, height=140, fg_color="#1a1a1a", corner_radius=8)
            lbl_img.pack(pady=(5, 2), padx=5)
            
            # Registrar label para actualización asíncrona
            if path not in self.image_labels:
                self.image_labels[path] = []
            self.image_labels[path].append(lbl_img)
            
            # Nombre del archivo
            name = os.path.basename(path)
            if len(name) > 12: name = name[:10] + ".."

            # --- CONTROLES DE ACTIVO ---
            controls_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            controls_frame.pack(fill="x", padx=5)

            if isinstance(item, dict):
                sub_var = ctk.BooleanVar(value=item.get("is_subliminal", False))
                def toggle_sub(v=sub_var, it=item): it["is_subliminal"] = v.get()
                
                ck_sub = ctk.CTkCheckBox(controls_frame, text="SUB", variable=sub_var, command=toggle_sub,
                                         font=("Inter", 8, "bold"), text_color="#FFD700", width=40, height=18)
                ck_sub.pack(side="left", padx=2)

                if item.get("type") == "video":
                    audio_var = ctk.BooleanVar(value=item.get("has_audio", True))
                    def toggle_audio(v=audio_var, it=item): it["has_audio"] = v.get()
                    sw = ctk.CTkCheckBox(controls_frame, text="AUD", variable=audio_var, command=toggle_audio,
                                         font=("Inter", 8, "bold"), text_color="#00E676", width=40, height=18)
                    sw.pack(side="right", padx=2)
            
            # Botones de movimiento y borrado
            btn_f = ctk.CTkFrame(item_frame, fg_color="transparent")
            btn_f.pack(fill="x", pady=2)
            
            ctk.CTkButton(btn_f, text="←", width=30, height=22, command=lambda idx=i: self.move_media(idx, -1)).pack(side="left", padx=2)
            ctk.CTkButton(btn_f, text="X", width=30, height=22, fg_color="#C62828", command=lambda idx=i: self.remove_media_item(idx)).pack(side="left", expand=True)
            ctk.CTkButton(btn_f, text="→", width=30, height=22, command=lambda idx=i: self.move_media(idx, 1)).pack(side="right", padx=2)

            ctk.CTkLabel(item_frame, text=f"{i+1}", font=("Arial", 9, "bold"), 
                        width=18, height=18, fg_color=COLOR_ACCENT, corner_radius=9).place(x=4, y=4)
            ctk.CTkLabel(item_frame, text=name, font=("Arial", 9), text_color="#888").pack(pady=2)

        # Lanzar procesamiento de miniaturas
        targets = list(self.image_labels.keys())
        threading.Thread(target=self.process_thumbnails_async, args=(targets,), daemon=True).start()

    def process_thumbnails_async(self, targets):
        """Procesa las imágenes en un hilo sin colisionar."""
        if getattr(self, "_is_thumb_running", False): return
        self._is_thumb_running = True
        
        temp_dir = os.path.join(os.getcwd(), "temp_render")
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)
        
        try:
            for path in targets:
                if not os.path.exists(path) or path in self.thumbnails: continue
                try:
                    ext = os.path.splitext(path)[1].lower()
                    is_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.m4v']
                    
                    if is_video:
                        safe_name = "".join([c for c in os.path.basename(path) if c.isalnum()])
                        thumb_path = os.path.join(temp_dir, f"vthumb_{safe_name}_{os.path.getsize(path)}.jpg")
                        if not os.path.exists(thumb_path):
                            subprocess.run(["ffmpeg", "-y", "-i", path, "-ss", "0.5", "-vframes", "1", "-f", "image2", thumb_path], 
                                         capture_output=True, creationflags=0x08000000)
                        pil_img = Image.open(thumb_path)
                    else:
                        pil_img = Image.open(path)
                    
                    pil_img.thumbnail((140, 140))
                    
                    # Poner en la cola segura para el hilo principal
                    self.thumbnail_queue.put((path, pil_img))
                except Exception as e:
                    print(f"Error procesando miniatura: {e}")
        finally:
            self._is_thumb_running = False

    def process_thumbnail_queue(self):
        """Revisa la cola de miniaturas de forma periódica en el hilo principal."""
        try:
            while not self.thumbnail_queue.empty():
                try:
                    path, pil_img = self.thumbnail_queue.get_nowait()
                    self.thumbnails[path] = pil_img
                    if path in self.image_labels:
                        for label in self.image_labels[path]:
                            self.apply_thumbnail(label, pil_img)
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error en cola de miniaturas: {e}")
        finally:
            self.after(100, self.process_thumbnail_queue)

    def apply_thumbnail(self, label, pil_img):
        """Crea el CTkImage y lo aplica (debe correr en el hilo principal)."""
        try:
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(110, 110))
            if label.winfo_exists():
                label.configure(image=ctk_img, text="")
        except Exception as e:
            print(f"Error aplicando miniatura: {e}")

    # --- LOGIC PRESERVED ---
    
    def select_audio(self):
        target_dir = r"D:\Descargas\Audio"
        file_path = filedialog.askopenfilename(initialdir=target_dir, filetypes=[("Audio files", "*.wav *.mp3 *.m4a")])
        if file_path:
            self.audio_path = file_path
            self.lbl_audio_name.configure(text=f"AUDIO ACTIVO: {os.path.basename(file_path)[:25]}", text_color=COLOR_SUCCESS)
            self.btn_audio.configure(border_color=COLOR_SUCCESS)
            self.check_ready_state()

    def select_cover(self):
        target_dir = r"D:\Descargas\Imagenes"
        if hasattr(self.main, 'settings'):
            target_dir = self.main.settings.get("images_folder_path", target_dir)

        if not os.path.exists(target_dir):
            try: os.makedirs(target_dir)
            except Exception: target_dir = self.img_download_folder

        path = filedialog.askopenfilename(initialdir=target_dir, filetypes=[("Images", "*.jpg *.png")])
        if path:
            self.cover_path = path
            self.lbl_status.configure(text=f"PORTADA: {os.path.basename(path)}", text_color=COLOR_SUCCESS)
            # Mostrar miniatura de la portada
            try:
                from PIL import Image
                img = Image.open(path)
                # Escalar manteniendo proporción
                img.thumbnail((40, 40))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.lbl_cover_preview.configure(image=ctk_img, text="")
            except Exception as e:
                print(f"Error cargando miniatura de portada: {e}")

    def on_media_type_change(self, value):
        if value == "IMÁGENES":
            self.media_mode = "image"
            self.btn_add_media.configure(text=" +  AÑADIR IMÁGENES ")
        elif value == "VIDEOS":
            self.media_mode = "video"
            self.btn_add_media.configure(text=" +  AÑADIR VIDEOS ")
        else:
            self.media_mode = "mix"
            self.btn_add_media.configure(text=" +  AÑADIR MEDIA (MIX) ")
            
        self.refresh_grid()
        self.check_ready_state()

    def auto_stock_pexels(self):
        import tkinter.messagebox as msgbox
        
        # 1. Validaciones
        api_key = getattr(self.main, "pexels_api_key", "")
        if not api_key:
            msgbox.showwarning("API Key Faltante", "Debes configurar tu API Key de Pexels en Ajustes (icono de engranaje) primero.")
            self.update_render_status("⚠️ CONFIGURA TU API KEY DE PEXELS EN AJUSTES", "orange")
            return
            
        prompts_text = getattr(self.main, "latest_visual_prompts", "")
        if not prompts_text:
            msgbox.showwarning("Prompts Faltantes", "Primero debes generar los Prompts Visuales en la pestaña 'Visual' para que podamos buscar escenas relacionadas.")
            self.update_render_status("⚠️ GENERA PRIMERO LOS PROMPTS EN LA PESTAÑA VISUAL", "orange")
            return
            
        # 2. Confirmación si ya hay clips en la línea de tiempo
        if self.mixed_media:
            if not msgbox.askyesno("Confirmar importación", "¿Deseas vaciar la línea de tiempo actual para importar los nuevos clips desde Pexels?"):
                return
                
        # 3. Bloquear UI e iniciar hilo
        self.btn_pexels.configure(state="disabled", text="PROCESANDO... ⏳")
        self.lbl_status.configure(text="🤖 INICIANDO AUTO-Sourcing DESDE PEXELS...", text_color="#FFD700")
        
        threading.Thread(target=self.run_auto_stock_pexels, args=(prompts_text, api_key), daemon=True).start()

    def run_auto_stock_pexels(self, prompts_text, api_key):
        import re
        from modules.pexels_client import extract_keywords_from_prompt, search_pexels_video, download_video_file
        
        try:
            # A) Parsear prompts visuales
            lines = prompts_text.split('\n')
            raw_prompts = []
            current_prompt = []
            for line in lines:
                s_line = line.strip()
                if not s_line:
                    continue
                is_new_prompt = re.match(r'^(\d+[:\.]|Imagen \d+|Prompt \d+|Prompt \d+[:\.]|scene \d+|Escena \d+)', s_line, re.IGNORECASE)
                is_metadata = "VARIABLE DE ENTIDAD" in s_line or "CONTEXTO:" in s_line
                
                if is_new_prompt:
                    if current_prompt:
                        raw_prompts.append(" ".join(current_prompt))
                    current_prompt = [s_line]
                elif is_metadata:
                    if current_prompt:
                        raw_prompts.append(" ".join(current_prompt))
                    current_prompt = []
                else:
                    if current_prompt:
                        current_prompt.append(s_line)
            if current_prompt:
                raw_prompts.append(" ".join(current_prompt))
                
            # Limpiar etiquetas
            clean_prompts = []
            for p in raw_prompts:
                p_clean = re.sub(r'^(\d+[:\.]|Imagen \d+[:\.]?|Prompt \d+[:\.]?|scene \d+[:\.]?|Escena \d+[:\.]?)\s*', '', p, flags=re.IGNORECASE)
                p_clean = p_clean.strip()
                if p_clean:
                    clean_prompts.append(p_clean)
                    
            if not clean_prompts:
                self.after(0, lambda: self.update_render_status("⚠️ No se pudieron identificar escenas en los prompts visuales.", "orange"))
                self.after(0, lambda: self.btn_pexels.configure(state="normal", text="🤖 AUTO STOCK"))
                return
                
            # Vaciar mixed_media si el usuario confirmó
            self.mixed_media = []
            
            provider = getattr(self.main, "llm_provider", "gemini")
            llm_key = getattr(self.main, "google_api_key" if provider == "gemini" else "groq_api_key", "")
            
            download_dir = self.main.img_download_folder
            os.makedirs(download_dir, exist_ok=True)
            
            # B) Buscar y descargar cada escena
            total = len(clean_prompts)
            for idx, p_text in enumerate(clean_prompts):
                self.after(0, lambda i=idx, t=total: self.update_render_status(f"🤖 Escena {i+1}/{t}: Extrayendo palabra clave...", "#FFD700"))
                
                # 1. Obtener palabra clave
                keyword = extract_keywords_from_prompt(p_text, llm_key, provider)
                if not keyword:
                    keyword = "dark mystery"
                    
                self.after(0, lambda i=idx, t=total, kw=keyword: self.update_render_status(f"🤖 Escena {i+1}/{t}: Buscando '{kw}' en Pexels...", "#FFD700"))
                
                # 2. Buscar video
                video_url = search_pexels_video(keyword, api_key, orientation="portrait")
                
                # Fallback si no hay resultados
                if not video_url:
                    keyword_fallback = "horror mystery"
                    video_url = search_pexels_video(keyword_fallback, api_key, orientation="portrait")
                    
                if not video_url:
                    # Fallback general si falla todo
                    video_url = search_pexels_video("spooky", api_key, orientation="portrait")
                    
                if not video_url:
                    print(f">>> [AUTO STOCK] No se pudo encontrar ningún video para la escena {idx+1}")
                    continue
                    
                self.after(0, lambda i=idx, t=total, kw=keyword: self.update_render_status(f"🤖 Escena {i+1}/{t}: Descargando clip '{kw}'...", "#FF9100"))
                
                # 3. Descargar
                clean_name = re.sub(r'[^a-zA-Z0-9]', '_', keyword.replace(' ', '_')).lower()[:15]
                output_name = f"pexels_scene_{idx+1}_{clean_name}.mp4"
                output_path = os.path.join(download_dir, output_name)
                
                downloaded_path = download_video_file(video_url, output_path)
                
                if downloaded_path and os.path.exists(downloaded_path):
                    # 4. Registrar en mixed_media
                    new_item = {
                        "path": downloaded_path,
                        "type": "video",
                        "has_audio": False,
                        "is_subliminal": False,
                        "ctime": os.path.getctime(downloaded_path)
                    }
                    self.mixed_media.append(new_item)
                    
                    # Refrescar grid incrementalmente para dar feedback visual
                    self.after(0, self.refresh_grid)
                    self.after(0, self.check_ready_state)
                    
            self.after(0, lambda: self.update_render_status("✨ ¡AUTO-STOCK COMPLETADO EXITOSAMENTE!", "#00FF66"))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda err=str(e): self.update_render_status(f"🛑 Error en Auto Stock: {err[:40]}", "red"))
            
        finally:
            self.after(0, lambda: self.btn_pexels.configure(state="normal", text="🤖 AUTO STOCK"))

    def open_gameplay_dialog(self):
        import tkinter.messagebox as msgbox
        
        # Calcular duración sugerida si hay audio activo
        suggested_dur = 60.0
        if self.audio_path and os.path.exists(self.audio_path):
            try:
                from modules.render_utils import get_video_duration
                dur = get_video_duration(self.audio_path)
                if dur > 0:
                    suggested_dur = dur
            except:
                pass
                
        # Confirmar sobreescritura si ya hay medios
        if self.mixed_media:
            if not msgbox.askyesno("Confirmar importación", "¿Deseas vaciar la línea de tiempo actual para importar los nuevos clips de gameplay?"):
                return
                
        # Abrir ventana de diálogo
        GameplaySourcingDialog(self, suggested_dur)

    def run_gameplay_sourcing(self, search_or_url, duration, aspect_ratio):
        from modules.gameplay_sourcing import download_youtube_gameplay, slice_video_segments
        
        self.btn_gameplay.configure(state="disabled", text="PROCESANDO... ⏳")
        self.lbl_status.configure(text="🎮 PREPARANDO VIDEO DE FONDO Y CORTANDO CLIPS...", text_color="#FFD700")
        
        try:
            # 1. Definir directorio de caché y descarga
            cache_dir = os.path.join(os.getcwd(), "cache", "gameplays")
            os.makedirs(cache_dir, exist_ok=True)
            download_dir = self.main.img_download_folder
            os.makedirs(download_dir, exist_ok=True)
            
            # 2. Descargar o usar de caché
            self.update_render_status("🌐 Conectando con YouTube...", "#FFD700")
            
            # Usar consultas de búsqueda por defecto en lugar de URLs estáticas propensas a borrarse
            default_gameplays = {
                "Minecraft Parkour": "Minecraft parkour gameplay long no commentary",
                "GTA 5 Stunts": "GTA 5 ramp stunts gameplay long no commentary",
                "Subway Surfers": "Subway Surfers gameplay long no commentary",
                "Satisfying Kinetic Sand": "satisfying kinetic sand cutting long no commentary"
            }
            
            query_str = default_gameplays.get(search_or_url, search_or_url)
            
            # Buscar si el archivo de gameplay ya está descargado localmente para ahorrar red
            import re
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '', query_str[:30].replace(' ', '_').lower())
            
            # Buscar en caché
            local_video_path = None
            for file in os.listdir(cache_dir):
                if file.startswith(clean_name) and file.endswith(('.mp4', '.mkv', '.webm')):
                    local_video_path = os.path.join(cache_dir, file)
                    break
                    
            if local_video_path and os.path.exists(local_video_path):
                self.update_render_status("♻️ USANDO VIDEO DE GAMEPLAY EN CACHÉ LOCAL", "#00FF66")
            else:
                self.update_render_status("🌐 Descargando video de YouTube (solo la primera vez)...", "#FFD700")
                local_video_path = download_youtube_gameplay(query_str, cache_dir, status_callback=self.update_render_status)
                
            # FALLBACK DE AUTO-CURACIÓN: Si la descarga falló (URL rota o privada), reintentar con Minecraft Parkour
            if not local_video_path or not os.path.exists(local_video_path):
                self.update_render_status("⚠️ Descarga fallida. Reintentando con búsqueda alternativa...", "orange")
                query_str = "Minecraft parkour gameplay long no commentary"
                clean_name = re.sub(r'[^a-zA-Z0-9_]', '', query_str[:30].replace(' ', '_').lower())
                
                # Buscar en caché
                for file in os.listdir(cache_dir):
                    if file.startswith(clean_name) and file.endswith(('.mp4', '.mkv', '.webm')):
                        local_video_path = os.path.join(cache_dir, file)
                        break
                
                # Descargar si no está en caché
                if not local_video_path:
                    local_video_path = download_youtube_gameplay(query_str, cache_dir, status_callback=self.update_render_status)
                
            if not local_video_path or not os.path.exists(local_video_path):
                raise Exception("No se pudo obtener el video de fondo.")
                
            # 3. Cortar en segmentos
            self.update_render_status("✂️ CORTANDO CLIPS DE VIDEO Y APLICANDO RESOLUCIÓN...", "#FF9100")
            clips = slice_video_segments(local_video_path, duration, download_dir, aspect_ratio=aspect_ratio, status_callback=self.update_render_status)
            
            if not clips:
                raise Exception("Fallo en la segmentación del video.")
                
            # 4. Asignar a la línea de tiempo
            self.mixed_media = clips
            
            # 5. UI Update
            self.after(0, self.refresh_grid)
            self.after(0, self.check_ready_state)
            self.after(0, lambda: self.update_render_status("✨ ¡GAMEPLAY IMPORTADO EXITOSAMENTE!", "#00FF66"))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda err=str(e): self.update_render_status(f"🛑 Error en Gameplay: {err[:40]}", "red"))
            
        finally:
            self.after(0, lambda: self.btn_gameplay.configure(state="normal", text="🎮 AUTO GAMEPLAY"))

    def select_media(self):
        # Usar rutas dinámicas de MainWindow
        default = getattr(self.main, "img_download_folder", "")
        if not os.path.exists(default):
            try: os.makedirs(default)
            except: pass

        paths = filedialog.askopenfilenames(initialdir=default, 
                                            filetypes=[("All Media", "*.jpg *.png *.webp *.mp4 *.mov *.avi *.mkv *.webm *.flv *.m4v")])
            
        if paths:
             new_items = []
             for p in paths:
                 ext = os.path.splitext(p)[1].lower()
                 is_vid = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.m4v']
                 new_items.append({
                     "path": p,
                     "type": "video" if is_vid else "image",
                     "has_audio": True if is_vid else False,
                     "ctime": os.path.getctime(p)
                 })

             self.mixed_media.extend(new_items)
             self.mixed_media.sort(key=lambda x: x["ctime"])
                 
             self.refresh_grid()
             self.check_ready_state()

    def clear_media(self):
        self.mixed_media = []
        self.cover_path = ""
        if hasattr(self, 'lbl_cover_preview'):
            self.lbl_cover_preview.configure(image=None, text="")
        self.lbl_status.configure(text="ESPERANDO CONFIGURACIÓN...", text_color="#444")
        
        self.refresh_grid()
        self.check_ready_state()

    def get_active_media(self):
        if self.media_mode == "image": return self.images_paths
        if self.media_mode == "video": return self.video_paths
        return self.mixed_media

    def move_media(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.mixed_media):
            self.mixed_media[index], self.mixed_media[new_index] = self.mixed_media[new_index], self.mixed_media[index]
            self.refresh_grid()
            self.check_ready_state()

    def remove_media_item(self, index):
        if 0 <= index < len(self.mixed_media):
            self.mixed_media.pop(index)
            self.refresh_grid()
            self.check_ready_state()

    def sort_media(self, criteria):
        if not self.mixed_media: return
        
        if criteria == "random":
            random.shuffle(self.mixed_media)
        elif criteria == "name":
            self.mixed_media.sort(key=lambda x: os.path.basename(x["path"]).lower())
        elif criteria == "date":
            # Alternar entre asc/desc
            if len(self.mixed_media) > 1 and self.mixed_media[0]["ctime"] < self.mixed_media[-1]["ctime"]:
                self.mixed_media.sort(key=lambda x: x["ctime"], reverse=True)
            else:
                self.mixed_media.sort(key=lambda x: x["ctime"])
        
        self.refresh_grid()
        self.check_ready_state()

    def check_ready_state(self):
        # 1. Verificar si podemos renderizar de cero
        if self.audio_path and self.mixed_media:
             self.lbl_status.configure(text="✅ LÍNEA DE TIEMPO LISTA PARA RENDER", text_color=COLOR_SUCCESS)
             self.btn_render.configure(state="normal", fg_color=COLOR_ACCENT)
             self.render_btn_pulsing = True
             self.animate_pulse_render()
        else:
             self.lbl_status.configure(text="ESPERANDO CONFIGURACIÓN...", text_color="#444")
             self.btn_render.configure(state="disabled", fg_color="#333", border_width=0)
             self.render_btn_pulsing = False

        # 2. AUTO-DETECTAR SI YA EXISTE UN RENDER FÍSICO
        # Esto permite subir un video anterior sin volver a renderizar
        title = self.entry_title.get().strip()
        if title:
            safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")
            output_folder = getattr(self.main, "ruta_drive", os.path.join(os.getcwd(), "dist"))
            potential_path = os.path.join(output_folder, f"{safe_title}.mp4")
            
            if os.path.exists(potential_path):
                self.last_render_path = potential_path
                self.btn_upload.configure(state="normal", fg_color=COLOR_SUCCESS)
                if not self.audio_path or not self.mixed_media:
                    self.lbl_status.configure(text="📽️ RENDER DETECTADO (LISTO PARA SUBIR)", text_color=COLOR_SUCCESS)
            else:
                if not hasattr(self, 'uploading') or not self.uploading:
                    self.btn_upload.configure(state="disabled", fg_color="#222")

    def animate_pulse_render(self):
        if not hasattr(self, 'render_btn_pulsing') or not self.render_btn_pulsing:
            return
        
        # Simple color oscillation or border flash
        import time
        t = time.time()
        # No heavy animation loop to avoid freezing UI, just subtle border check
        # For now, just a static glow is safer in Tkinter main thread without complex logic
        self.btn_render.configure(border_color="#FF5252", border_width=1)



    def refresh_music_list(self):
        if not os.path.exists(self.music_folder): return
        files = [f for f in os.listdir(self.music_folder) if f.lower().endswith(('.mp3', '.wav'))]
        if files:
            self.combo_music.configure(values=files)
            if not self.current_music_path or os.path.basename(self.current_music_path) not in files:
                self.combo_music.set(files[0])
                self.current_music_path = os.path.join(self.music_folder, files[0])
            else:
                self.combo_music.set(os.path.basename(self.current_music_path))
        else:
            self.combo_music.configure(values=["No music avail"])
            self.combo_music.set("No music avail")

    def on_music_manual_select(self, value):
        if value != "No music avail":
            self.stop_preview()
            self.current_music_path = os.path.join(self.music_folder, value)

    def reroll_music(self, silent=False):
        if not os.path.exists(self.music_folder): return
        files = [f for f in os.listdir(self.music_folder) if f.lower().endswith(('.mp3', '.wav'))]
        if files:
            was_playing = self.preview_process is not None
            self.stop_preview()
            
            chosen = random.choice(files)
            self.current_music_path = os.path.join(self.music_folder, chosen)
            self.combo_music.set(chosen)
            
            # Si el usuario NO pidió modo silencioso, sonar la nueva elección
            if not silent:
                self.play_preview()
        else:
            if not silent: 
                self.combo_music.set("No hay música disponible")

    def stop_preview(self):
        if self.preview_process:
            try:
                # Intentar cerrar amigablemente y luego forzar
                self.preview_process.terminate()
                self.preview_process.wait(timeout=0.2)
            except:
                try: self.preview_process.kill()
                except: pass
            self.preview_process = None
        
        # Limpieza de emergencia para Windows de cualquier ffplay huérfano
        try:
            if os.name == 'nt':
                subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe", "/T"], 
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass

    def play_preview(self):
        if self.current_music_path and os.path.exists(self.current_music_path):
            self.stop_preview()
            # Asegurarse de que el combo refleje lo que vamos a sonar
            self.combo_music.set(os.path.basename(self.current_music_path))
            
            # Lanzar ffplay sin ventana y con auto-salida
            cmd = ["ffplay", "-nodisp", "-autoexit", "-t", "15", self.current_music_path]
            try:
                self.preview_process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except Exception as e:
                print(f"Error al iniciar previsualización: {e}")
            
    def get_active_media(self):
        return self.mixed_media

    def on_render_click(self):
        active_list = self.get_active_media()
        if not self.audio_path or not active_list: return
        
        self.btn_render.configure(state="disabled", text="PROCESANDO... ⏳")
        self.lbl_status.configure(text="INICIANDO MOTOR DE RENDER...", text_color="#FFD700")
        
        title = self.entry_title.get().strip() or "SilencioRojo_Video"
        desc = self.txt_desc.get("0.0", "end").strip()
        music = self.current_music_path if self.var_music.get() else None

        lut_name = self.combo_luts.get()
        sub_style = self.combo_sub_style.get()
        output_folder = getattr(self.main, "ruta_drive", os.path.join(os.getcwd(), "dist"))
        
        card_title = self.entry_card_title.get().strip() if hasattr(self, "entry_card_title") else ""
        pacing = self.combo_pacing.get() if hasattr(self, "combo_pacing") else "Dinámico [2.0s]"
        vol_voice = self.slider_voice.get() if hasattr(self, "slider_voice") else 100.0
        vol_music = self.slider_music.get() if hasattr(self, "slider_music") else 40.0
        vol_sfx = self.slider_sfx.get() if hasattr(self, "slider_sfx") else 100.0

        args = (title, desc, output_folder, music, active_list, self.media_mode, self.video_format, lut_name, sub_style, card_title, pacing, vol_voice, vol_music, vol_sfx)
        threading.Thread(target=self.run_render, args=args, daemon=True).start()

    def run_render(self, title, desc, output_folder, music, active_list, media_mode, aspect_ratio, lut_name, sub_style="TikTok / Hormozi", card_title="", pacing="Dinámico [2.0s]", vol_voice=100.0, vol_music=40.0, vol_sfx=100.0):
        try:
            success = render_final_video(
                audio_path=self.audio_path,
                images_paths=active_list,
                cover_path=self.cover_path,
                output_folder=output_folder,
                title=title,
                description=desc,
                vhs_enabled=True,
                music_path=music,
                media_mode=media_mode,
                status_callback=self.update_render_status,
                groq_key=self.main.settings.get("groq_api_key"),
                aspect_ratio=aspect_ratio,
                lut_name=lut_name,
                sub_style=sub_style,
                reddit_card_title=card_title,
                pacing=pacing,
                vol_voice=vol_voice,
                vol_music=vol_music,
                vol_sfx=vol_sfx
            )
            
            if success:
                self.update_render_status("✨ ¡RENDERIZADO EXITOSO!", COLOR_SUCCESS)
                # ... resto del código de éxito ...
                # (He simplificado aquí para la herramienta, pero el código original se mantiene)
                safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).strip().replace(" ", "_")
                if not safe_title: safe_title = "Render_SilencioRojo"
                self.last_render_path = os.path.join(output_folder, f"{safe_title}.mp4")
                
                if os.path.exists(self.last_render_path):
                    try:
                        if os.name == 'nt': os.startfile(self.last_render_path)
                        else: subprocess.run(['xdg-open', self.last_render_path], check=False)
                    except: pass

                # Habilitar botones de acción
                self.after(0, lambda: self.btn_upload.configure(state="normal", fg_color=COLOR_SUCCESS))
                
                # Crear botón dinámico para abrir el archivo si no existe
                if not hasattr(self, 'btn_open_result'):
                    self.btn_open_result = ctk.CTkButton(self.lbl_status.master, text="📂 ABRIR RESULTADO", 
                                                        font=("Arial", 10, "bold"), fg_color="#222", hover_color="#333",
                                                        width=120, height=24, command=lambda: os.startfile(os.path.dirname(self.last_render_path)))
                    self.btn_open_result.place(relx=0.5, rely=0.5, anchor="center") # Ajustar posición según UI
                else:
                    self.btn_open_result.place(relx=0.5, rely=0.5, anchor="center")
            else:
                # El error ya fue reportado detalladamente por el motor
                pass
                
        except Exception as e:
            self.update_render_status(f"CRITICAL ERROR: {e}", "red")
            
        self.after(0, lambda: self.btn_render.configure(state="normal", text="⚡ RENDERIZAR VIDEO FINAL ⚡"))

    def update_render_status(self, text, color):
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color))
        
        # Lógica para detectar progreso en el texto (ej: "5/15")
        if "/" in text and any(char.isdigit() for char in text):
            try:
                parts = text.split(":")[-1].split("/")
                current = float(parts[0].strip().split()[-1])
                total = float(parts[1].strip().split()[0])
                progress = current / total
                self.after(0, lambda: self.progress_render.set(progress))
            except: pass
        elif "COMPLETADO" in text or "EXITOSO" in text:
            self.after(0, lambda: self.progress_render.set(1.0))
        elif "INICIANDO" in text:
            self.after(0, lambda: self.progress_render.set(0.05))

    # --- YOUTUBE UPLOAD LOGIC ---
    def on_upload_click(self):
        if not self.last_render_path or not os.path.exists(self.last_render_path):
            # Intentar re-detectar por si el usuario cambió el título
            title = self.entry_title.get().strip()
            safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")
            output_folder = getattr(self.main, "ruta_drive", os.path.join(os.getcwd(), "dist"))
            self.last_render_path = os.path.join(output_folder, f"{safe_title}.mp4")

        if not os.path.exists(self.last_render_path):
            self.update_render_status("❌ NO SE ENCONTRÓ EL ARCHIVO MP4", "red")
            return
        
        self.uploading = True
        self.btn_upload.configure(state="disabled", text="SUBIENDO... 🚀")
        title = self.entry_title.get().strip() or "Terror Short"
        desc = self.txt_desc.get("0.0", "end").strip()
        tags = self.entry_tags.get().strip()
        
        threading.Thread(target=self.run_upload, args=(self.last_render_path, title, desc, tags), daemon=True).start()

    def run_upload(self, file_path, title, desc, tags):
        try:
            success, result = upload_video(
                file_path=file_path,
                title=title,
                description=desc,
                keywords=tags,
                status_callback=self.update_render_status
            )
            
            if success:
                self.update_render_status(f"✅ SUBIDO: youtube.com/watch?v={result}", COLOR_SUCCESS)
                # Abrir en navegador
                import webbrowser
                webbrowser.open(f"https://www.youtube.com/watch?v={result}")
            else:
                self.update_render_status(f"❌ ERROR SUBIDA: {result[:40]}", "red")
                if "No se encontró el archivo de credenciales" in result:
                     import tkinter.messagebox as msgbox
                     msgbox.showwarning("Faltan Credenciales", "Debes colocar 'client_secrets.json' en la carpeta 'config/' para subir a YouTube.")
                
        except Exception as e:
            self.update_render_status(f"UPLOAD ERROR: {e}", "red")
            
        self.uploading = False
        self.after(0, lambda: self.btn_upload.configure(state="normal", text="📤 SUBIR A SHORTS"))


    # --- PROJECT MANAGEMENT ---
    def get_state(self):
        return {
            "meta_title": self.entry_title.get(),
            "meta_card_title": self.entry_card_title.get() if hasattr(self, "entry_card_title") else "",
            "meta_desc": self.txt_desc.get("0.0", "end"),
            "audio_path": self.audio_path,
            "music_enabled": self.var_music.get(),
            "music_path": self.current_music_path,
            "media_mode": "mix",
            "mixed_media": self.mixed_media,
            "cover_path": self.cover_path,
            "last_render_path": self.last_render_path,
            "lut_name": self.combo_luts.get(),
            "sub_style": self.combo_sub_style.get(),
            "pacing": self.combo_pacing.get() if hasattr(self, "combo_pacing") else "Dinámico [2.0s]",
            "vol_voice": self.slider_voice.get() if hasattr(self, "slider_voice") else 100,
            "vol_music": self.slider_music.get() if hasattr(self, "slider_music") else 40,
            "vol_sfx": self.slider_sfx.get() if hasattr(self, "slider_sfx") else 100
        }

    def restore_state(self, state):
        if not state: return
        
        # Meta - Usando nombres de widgets rediseñados
        try:
            self.entry_title.delete(0, "end")
            self.entry_title.insert(0, state.get("meta_title", ""))
            
            if hasattr(self, "entry_card_title"):
                self.entry_card_title.delete(0, "end")
                self.entry_card_title.insert(0, state.get("meta_card_title", ""))
            
            self.txt_desc.delete("0.0", "end")
            self.txt_desc.insert("0.0", state.get("meta_desc", ""))
            
            if hasattr(self, "combo_pacing") and "pacing" in state:
                self.combo_pacing.set(state.get("pacing", "Dinámico [2.0s]"))
                
            if "vol_voice" in state and hasattr(self, "slider_voice"):
                v = state.get("vol_voice", 100)
                self.slider_voice.set(v)
                self.lbl_vol_voice.configure(text=f"{int(v)}%")
                
            if "vol_music" in state and hasattr(self, "slider_music"):
                m = state.get("vol_music", 40)
                self.slider_music.set(m)
                self.lbl_vol_music.configure(text=f"{int(m)}%")
                
            if "vol_sfx" in state and hasattr(self, "slider_sfx"):
                s = state.get("vol_sfx", 100)
                self.slider_sfx.set(s)
                self.lbl_vol_sfx.configure(text=f"{int(s)}%")
        except Exception as e:
            print(f"Error restoring UI state: {e}")
             
        # Media Lists - Forzando modo MIX
        self.media_mode = "mix"
        self.mixed_media = state.get("mixed_media", [])
        self.cover_path = state.get("cover_path", "")
        self.last_render_path = state.get("last_render_path", "")
        self.combo_luts.set(state.get("lut_name", "Ninguno"))
        self.combo_sub_style.set(state.get("sub_style", "TikTok / Hormozi"))
        
        # Refresh visuals
        self.refresh_grid()
        self.check_ready_state()

    def focus_set(self):
        """Override to refresh content when tab becomes visible"""
        super().focus_set()
        
        # Sync Title
        if hasattr(self.main, "generated_title") and self.main.generated_title:
            current_t = self.entry_title.get().strip()
            # If empty or placeholder, update it
            if not current_t or current_t == "SilencioRojo_Video":
                self.entry_title.delete(0, "end")
                self.entry_title.insert(0, self.main.generated_title)
        
        # Sync Description
        if hasattr(self.main, "generated_desc") and self.main.generated_desc:
            current_d = self.txt_desc.get("0.0", "end").strip()
            # If placeholder, update it
            if "Descripción generada automáticamente" in current_d:
                self.txt_desc.delete("0.0", "end")
                self.txt_desc.insert("0.0", self.main.generated_desc)

    def run_viral_generation(self):
        # Check if story is available
        story = getattr(self.main, "generated_story", "").strip()
        if not story:
            # Fallback to current_trama_cache or show error
            story = getattr(self.main, "current_trama_cache", "").strip()
            
        if not story or "El guion generado por la IA" in story:
            self.update_render_status("⚠️ Primero genera un guion en la pestaña Concepto", "orange")
            return
            
        provider = getattr(self.main, "llm_provider", "gemini")
        if provider == "groq":
            api_key = getattr(self.main, "groq_api_key", "")
        else:
            api_key = getattr(self.main, "google_api_key", "")
            
        if not api_key:
            self.update_render_status("⚠️ Configura tu API Key en los ajustes", "orange")
            return

        self.btn_viral.configure(state="disabled", text="GENERANDO...")
        
        def thread_run():
            try:
                prompt = (
                    "Actúa como un experto en SEO de YouTube Shorts y viralidad. "
                    "A partir del siguiente guion de un Short de terror, genera lo siguiente de forma precisa:\n\n"
                    f"GUION:\n{story}\n\n"
                    "Genera tu respuesta en este formato exacto:\n"
                    "---SEO_TITLE---\n"
                    "[Escribe aquí un título optimizado para búsquedas de YouTube de menos de 80 caracteres. Debe incluir palabras clave del nicho como HILO DE REDDIT, Reddit Stories, Terror o Horror, y hashtags indexables como #terror #misterio #backrooms #shorts. Añade algún emoji interesante]\n"
                    "---CARD_TITLE---\n"
                    "[Escribe aquí el gancho de intriga visual para la tarjeta de Reddit. Debe ser una pregunta o confesión de terror muy intrigante de máximo 70 caracteres, sin hashtags, sin links, muy limpio y auténtico como un post real de r/nosleep. Añade un emoji intrigante]\n"
                    "---DESCRIPTION---\n"
                    "[Escribe aquí una descripción intrigante y optimizada de 2 o 3 párrafos cortos. Añade hashtags relevantes, una pregunta para incentivar comentarios en el feed de Shorts, y la siguiente marca de capítulos temporales:\n"
                    "00:00 - La captura de Reddit\n"
                    "00:15 - El secreto perturbador\n"
                    "00:35 - La confesión final\n]\n"
                )
                
                from modules import gemini_client, groq_client
                if provider == "groq":
                    res = groq_client.generate_content(prompt, api_key)
                else:
                    res = gemini_client.generate_content(prompt, api_key)
                    
                import re
                seo_title = ""
                card_title = ""
                description = ""
                
                seo_match = re.search(r"---SEO_TITLE---\n(.*?)(?=\n---|$$)", res, re.DOTALL | re.IGNORECASE)
                if seo_match:
                    seo_title = seo_match.group(1).strip().strip('\"')
                
                card_match = re.search(r"---CARD_TITLE---\n(.*?)(?=\n---|$$)", res, re.DOTALL | re.IGNORECASE)
                if card_match:
                    card_title = card_match.group(1).strip().strip('\"')
                    
                desc_match = re.search(r"---DESCRIPTION---\n(.*?)(?=\n---|$$)", res, re.DOTALL | re.IGNORECASE)
                if desc_match:
                    description = desc_match.group(1).strip()
                    
                # Update UI elements in main thread
                def update_ui():
                    if seo_title:
                        self.entry_title.delete(0, "end")
                        self.entry_title.insert(0, seo_title)
                    if card_title:
                        self.entry_card_title.delete(0, "end")
                        self.entry_card_title.insert(0, card_title)
                    if description:
                        self.txt_desc.delete("0.0", "end")
                        self.txt_desc.insert("0.0", description)
                    self.btn_viral.configure(state="normal", text="Metadatos Virales ⚡")
                    self.update_render_status("✨ ¡METADATOS VIRALES APLICADOS!", "#00E676")
                    
                self.after(0, update_ui)
                
            except Exception as e:
                print(f"Error generating viral metadata: {e}")
                self.after(0, lambda: [
                    self.btn_viral.configure(state="normal", text="Metadatos Virales ⚡"),
                    self.update_render_status(f"❌ Error en metadatos: {str(e)[:40]}", "red")
                ])
                
        threading.Thread(target=thread_run, daemon=True).start()

class GameplaySourcingDialog(ctk.CTkToplevel):
    def __init__(self, parent_tab, default_duration):
        super().__init__(parent_tab)
        self.tab = parent_tab
        self.title("CREADOR DE FONDO GAMEPLAY")
        self.geometry("520x380")
        self.configure(fg_color="#0F0F0F")
        self.transient(parent_tab)
        self.grab_set()
        self.resizable(False, False)
        
        # Centrar diálogo
        if hasattr(parent_tab.main, 'winfo_x'):
            main_x = parent_tab.main.winfo_x()
            main_y = parent_tab.main.winfo_y()
            main_w = parent_tab.main.winfo_width()
            main_h = parent_tab.main.winfo_height()
            x = main_x + (main_w // 2) - (520 // 2)
            y = main_y + (main_h // 2) - (380 // 2)
            self.geometry(f"+{x}+{y}")
            
        from core.utils import force_focus
        force_focus(self)
        
        self.setup_ui(default_duration)
        
    def setup_ui(self, default_duration):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(25, 15))
        
        ctk.CTkLabel(header, text="GAMEPLAY BACKGROUND", font=("Impact", 22), text_color="#651FFF").pack(side="left")
        
        # Card
        card = ctk.CTkFrame(self, fg_color="#141414", corner_radius=10, border_width=1, border_color="#222")
        card.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        
        # Selection
        ctk.CTkLabel(card, text="TIPO DE VIDEO DE FONDO:", font=("Arial", 11, "bold"), text_color="#888").pack(anchor="w", padx=20, pady=(15, 5))
        self.combo_type = ctk.CTkComboBox(card, values=["Minecraft Parkour", "GTA 5 Stunts", "Subway Surfers", "Satisfying Kinetic Sand", "Personalizado / URL"], 
                                           width=400, fg_color="#050505", border_color="#222", button_color="#1A1A1A",
                                           command=self.on_selection_change)
        self.combo_type.pack(fill="x", padx=20, pady=(0, 15))
        self.combo_type.set("Minecraft Parkour")
        
        # Custom input (URL or query)
        self.lbl_custom = ctk.CTkLabel(card, text="URL DE YOUTUBE O BÚSQUEDA:", font=("Arial", 11, "bold"), text_color="#888")
        self.entry_custom = ctk.CTkEntry(card, placeholder_text="Ej: GTA 5 gameplay ramp stunts long no commentary...", fg_color="#050505", border_color="#222")
        
        # Target Duration
        ctk.CTkLabel(card, text="DURACIÓN TOTAL OBJETIVO (SEG):", font=("Arial", 11, "bold"), text_color="#888").pack(anchor="w", padx=20, pady=(0, 5))
        self.entry_dur = ctk.CTkEntry(card, fg_color="#050505", border_color="#222", font=("Consolas", 12))
        self.entry_dur.pack(fill="x", padx=20, pady=(0, 15))
        self.entry_dur.insert(0, f"{default_duration:.1f}")
        
        # Action button
        self.btn_action = ctk.CTkButton(self, text="GENERAR FONDO GAMEPLAY ⚡", height=50, 
                                         fg_color="#651FFF", hover_color="#4500C7", text_color="white",
                                         font=("Arial", 12, "bold"), command=self.on_generate)
        self.btn_action.pack(fill="x", padx=30, pady=(0, 25))
        
    def on_selection_change(self, value):
        if value == "Personalizado / URL":
            # Mostrar entrada personalizada
            self.lbl_custom.pack(anchor="w", padx=20, pady=(0, 5))
            self.entry_custom.pack(fill="x", padx=20, pady=(0, 15))
            # Ajustar alto de la ventana
            self.geometry("520x450")
        else:
            # Ocultar
            self.lbl_custom.pack_forget()
            self.entry_custom.pack_forget()
            self.geometry("520x380")
            
    def on_generate(self):
        import threading
        
        sel_type = self.combo_type.get()
        if sel_type == "Personalizado / URL":
            search_str = self.entry_custom.get().strip()
            if not search_str:
                self.entry_custom.configure(border_color="red")
                return
        else:
            search_str = sel_type
            
        dur_str = self.entry_dur.get().strip()
        try:
            dur = float(dur_str)
            if dur <= 0:
                raise ValueError()
        except ValueError:
            self.entry_dur.configure(border_color="red")
            return
            
        # Lanzar hilo en la pestaña padre
        aspect_ratio = self.tab.video_format
        
        self.destroy()
        
        threading.Thread(target=self.tab.run_gameplay_sourcing, args=(search_str, dur, aspect_ratio), daemon=True).start()

