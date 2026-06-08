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
        self.lbl_audio_name.pack(pady=(0, 5))
        
        row_v = ctk.CTkFrame(card_v, fg_color="transparent")
        row_v.pack(fill="x", padx=15, pady=(0, 8))
        
        b_sty_v = {"height": 30, "fg_color": "#0F0F0F", "hover_color": "#151515", "border_width": 1, "border_color": "#222", "font": ("Arial", 11, "bold")}
        self.btn_play_narration = ctk.CTkButton(row_v, text="▶ REPRODUCIR", command=self.play_narration_preview, **b_sty_v)
        self.btn_play_narration.pack(side="left", padx=(0, 4), expand=True, fill="x")
        
        self.btn_stop_narration = ctk.CTkButton(row_v, text="⏸ DETENER", command=self.stop_narration_preview, **b_sty_v)
        self.btn_stop_narration.pack(side="left", padx=(4, 0), expand=True, fill="x")
        
        self.btn_translate_audio = ctk.CTkButton(card_v, text="🌐 TRADUCIR NARRACIÓN ⚡", 
                                                 fg_color="#1A1F38", hover_color="#2A3358", border_width=1, border_color="#3B487A",
                                                 height=32, font=("Arial", 11, "bold"), command=self.on_translate_audio_click)
        self.btn_translate_audio.pack(fill="x", padx=15, pady=(0, 10))

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

        # --- ESTILO DE SUBTÍTULOS ---
        card_sub = self.create_card(parent, "ESTILO DE SUBTÍTULOS")
        self.combo_sub_style = ctk.CTkComboBox(card_sub, values=["TikTok / Hormozi", "Reddit History"],
                                               fg_color="#050505", border_color="#181818", button_color="#111", 
                                               text_color="white", font=("Inter", 11), height=35)
        self.combo_sub_style.pack(fill="x", padx=15, pady=(5, 15))
        self.combo_sub_style.set("TikTok / Hormozi")

        self.refresh_music_list()

    def setup_right_panel(self, parent):
        # --- TOP: METADATOS (MODERN BAR) ---
        meta_bar = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=15, border_width=1, border_color=COLOR_CARD_BORDER)
        meta_bar.pack(fill="x", pady=(0, 20))
        
        meta_left = ctk.CTkFrame(meta_bar, fg_color="transparent")
        meta_left.pack(side="left", fill="both", expand=True, padx=20, pady=15)
        
        ctk.CTkLabel(meta_left, text="TÍTULO DEL PROYECTO", font=("Inter", 9, "bold"), text_color=COLOR_TEXT_SEC).pack(anchor="w")
        self.entry_title = ctk.CTkEntry(meta_left, placeholder_text="Nombre del video...", height=35, 
                                        fg_color="transparent", border_width=0, font=("Inter", 16, "bold"), text_color="white")
        self.entry_title.pack(fill="x", pady=(2, 8))
        
        ctk.CTkLabel(meta_left, text="DESCRIPCIÓN OPTIMIZADA", font=("Inter", 9, "bold"), text_color=COLOR_TEXT_SEC).pack(anchor="w")
        self.txt_desc = ctk.CTkTextbox(meta_left, height=60, fg_color="#050505", border_width=1, border_color="#151515", font=("Inter", 11))
        self.txt_desc.pack(fill="x", pady=(5, 0))
        
        # Tags ocultos o compactos (por simplicidad en este rediseño)
        self.entry_tags = ctk.CTkEntry(meta_bar, width=0, height=0) 

        # --- BOTTOM: ACTION BAR (Pack first at bottom to reserve space) ---
        action_bar = ctk.CTkFrame(parent, fg_color="transparent", height=100)
        action_bar.pack(side="bottom", fill="x", pady=(15, 0))
        
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

        # --- SORT BAR (Pack above action bar) ---
        sort_bar = ctk.CTkFrame(parent, fg_color="transparent")
        sort_bar.pack(side="bottom", fill="x", pady=(5, 0))
        ctk.CTkLabel(sort_bar, text="ORDENAR POR:", font=("Inter", 9, "bold"), text_color="#333").pack(side="left", padx=10)
        ctk.CTkButton(sort_bar, text="FECHA", width=60, height=20, font=("Inter", 8, "bold"), fg_color="#080808", command=lambda: self.sort_media("date")).pack(side="left", padx=2)
        ctk.CTkButton(sort_bar, text="NOMBRE", width=60, height=20, font=("Inter", 8, "bold"), fg_color="#080808", command=lambda: self.sort_media("name")).pack(side="left", padx=2)

        # --- CENTER: TIMELINE HEADER (Pack below meta_bar) ---
        timeline_header = ctk.CTkFrame(parent, fg_color="transparent")
        timeline_header.pack(side="top", fill="x", pady=(0, 10))
        
        ctk.CTkLabel(timeline_header, text="VISUAL TIMELINE", font=("Impact", 24), text_color="white").pack(side="left")
        
        tool_bar = ctk.CTkFrame(timeline_header, fg_color="transparent")
        tool_bar.pack(side="right")
        
        btn_s = {"height": 28, "font": ("Inter", 10, "bold"), "fg_color": "#111", "hover_color": "#181818", "border_width": 1, "border_color": "#222"}
        ctk.CTkButton(tool_bar, text="+ MEDIA", command=self.select_media, **btn_s).pack(side="left", padx=5)
        
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

        # --- MIDDLE: LINEA DE TIEMPO (Pack last to fill remaining space) ---
        self.scroll_grid = ctk.CTkScrollableFrame(parent, fg_color="#0a0a0a", corner_radius=15, 
                                                 border_width=1, border_color="#1a1a1a", orientation="vertical")
        self.scroll_grid.pack(side="top", fill="both", expand=True)
        
        # Configurar columnas para la cuadrícula
        self.cols = 6 # Ajustamos a 6 columnas por fila
        for i in range(self.cols):
            self.scroll_grid.grid_columnconfigure(i, weight=1)

    # --- UI CALLBACKS ---

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
        
        temp_dir = os.path.join(os.getcwd(), "cache", "thumbnails")
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
            self.stop_narration_preview()
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
            
    def play_narration_preview(self):
        if self.audio_path and os.path.exists(self.audio_path):
            self.stop_narration_preview()
            
            cmd = ["ffplay", "-nodisp", "-autoexit", self.audio_path]
            try:
                self.narration_preview_process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except Exception as e:
                print(f"Error al iniciar previsualización de narración: {e}")

    def stop_narration_preview(self):
        if hasattr(self, "narration_preview_process") and self.narration_preview_process:
            try:
                self.narration_preview_process.terminate()
            except:
                try: self.narration_preview_process.kill()
                except: pass
            self.narration_preview_process = None
        
        try:
            if os.name == 'nt':
                subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe", "/T"], 
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass

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

        # Selección aleatoria del filtro visual (LUT) para variedad
        lut_name = random.choice(["Ninguno", "Gore Rojo", "Terror Frío", "Misterio Oscuro"])
        sub_style = self.combo_sub_style.get()
        output_folder = getattr(self.main, "ruta_drive", os.path.join(os.getcwd(), "dist"))
        
        # Generación automática de tarjeta de Reddit
        if sub_style == "Reddit History":
            import re
            clean_title = re.sub(r'#\S+', '', title) # Quitar hashtags
            clean_title = "".join(c for c in clean_title if c.isalnum() or c in " ,.¡!¿?()\"'-").strip() # Quitar emojis
            card_title = clean_title if clean_title else "Pregunta intrigante de Reddit..."
        else:
            card_title = ""
            
        pacing = "Dinámico [2.0s]"
        vol_voice = 100.0
        vol_music = 40.0
        vol_sfx = 100.0
        self.video_format = "9:16"

        args = (title, desc, output_folder, music, active_list, self.media_mode, self.video_format, lut_name, sub_style, card_title, pacing, vol_voice, vol_music, vol_sfx)
        threading.Thread(target=self.run_render, args=args, daemon=True).start()

    def run_render(self, title, desc, output_folder, music, active_list, media_mode, aspect_ratio, lut_name, sub_style="TikTok / Hormozi", card_title="", pacing="Dinámico [2.0s]", vol_voice=100.0, vol_music=40.0, vol_sfx=100.0):
        try:
            safe_title = "".join([c for c in title if c.isalnum() or c==' ']).strip().replace(" ", "_")
            if not safe_title: safe_title = "Render_SilencioRojo"
            
            # 1. Determinar ruta local de render en la carpeta del proyecto
            project_id = getattr(self.main, "current_project_id", None)
            render_dest_folder = output_folder
            if project_id:
                local_renders_dir = os.path.join(os.getcwd(), "projects", project_id, "renders")
                os.makedirs(local_renders_dir, exist_ok=True)
                render_dest_folder = local_renders_dir
                
            success = render_final_video(
                audio_path=self.audio_path,
                images_paths=active_list,
                cover_path=self.cover_path,
                output_folder=render_dest_folder,
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
                
                # Ruta del render dentro del proyecto (o fallback en output_folder)
                self.last_render_path = os.path.join(render_dest_folder, f"{safe_title}.mp4")
                
                # 2. Copiar el render al directorio de salida externo si está configurado y es diferente
                if project_id and os.path.exists(self.last_render_path):
                    external_path = os.path.join(output_folder, f"{safe_title}.mp4")
                    if os.path.abspath(self.last_render_path) != os.path.abspath(external_path):
                        try:
                            import shutil
                            os.makedirs(output_folder, exist_ok=True)
                            shutil.copy2(self.last_render_path, external_path)
                            print(f">>> [RENDER] Copiado render final a la carpeta externa: {external_path}")
                            self.last_render_path = external_path
                        except Exception as copy_err:
                            print(f">>> [RENDER COPY ERROR] No se pudo copiar a {external_path}: {copy_err}")
                
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

    def on_translate_audio_click(self):
        if not self.audio_path or not os.path.exists(self.audio_path):
            self.update_render_status("⚠️ Selecciona un audio de narración válido primero", "orange")
            return
            
        self.btn_translate_audio.configure(state="disabled", text="TRADUCIENDO... ⏳")
        self.update_render_status("🎙️ INICIANDO TRADUCCIÓN DE VOZ BAJO DEMANDA...", "#FFD700")
        
        title = self.entry_title.get().strip() or "SilencioRojo_Video"
        desc = self.txt_desc.get("0.0", "end").strip()
        safe_title = "".join([c for c in title if c.isalnum() or c==' ']).rstrip().replace(" ", "_") or "Video_Render_Mix"
        output_folder = getattr(self.main, "ruta_drive", os.path.join(os.getcwd(), "dist"))
        music = self.current_music_path if self.var_music.get() else None
        vol_voice = 100.0
        vol_music = 40.0
        
        # Obtener el directorio del proyecto activo para guardar doblajes ordenadamente
        project_id = getattr(self.main, "current_project_id", None)
        project_dir = os.path.join(os.getcwd(), "projects", project_id) if project_id else None
        
        def run():
            try:
                from modules.render_mix import auto_generate_translated_dubs
                auto_generate_translated_dubs(
                    audio_path=self.audio_path,
                    music_path=music,
                    vol_voice=vol_voice,
                    vol_music=vol_music,
                    output_folder=output_folder,
                    safe_title=safe_title,
                    title=title,
                    description=desc,
                    status_callback=self.update_render_status,
                    project_dir=project_dir
                )
                self.after(0, lambda: [
                    self.btn_translate_audio.configure(state="normal", text="🌐 TRADUCIR NARRACIÓN ⚡"),
                    self.update_render_status("✨ ¡TRADUCCIONES Y DOBLAJES LISTOS!", COLOR_SUCCESS)
                ])
            except Exception as e:
                print(f"Error in on_translate_audio_click: {e}")
                self.after(0, lambda: [
                    self.btn_translate_audio.configure(state="normal", text="🌐 TRADUCIR NARRACIÓN ⚡"),
                    self.update_render_status(f"❌ Error en traducción: {str(e)[:30]}", "red")
                ])
                
        threading.Thread(target=run, daemon=True).start()

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
            "meta_card_title": "",
            "meta_desc": self.txt_desc.get("0.0", "end"),
            "audio_path": self.audio_path,
            "music_enabled": self.var_music.get(),
            "music_path": self.current_music_path,
            "media_mode": "mix",
            "mixed_media": self.mixed_media,
            "cover_path": self.cover_path,
            "last_render_path": self.last_render_path,
            "lut_name": "Ninguno",
            "sub_style": self.combo_sub_style.get(),
            "pacing": "Dinámico [2.0s]",
            "vol_voice": 100,
            "vol_music": 40,
            "vol_sfx": 100
        }

    def restore_state(self, state):
        if not state: return
        
        try:
            self.entry_title.delete(0, "end")
            self.entry_title.insert(0, state.get("meta_title", ""))
            
            self.txt_desc.delete("0.0", "end")
            self.txt_desc.insert("0.0", state.get("meta_desc", ""))
        except Exception as e:
            print(f"Error restoring UI state: {e}")
             
        self.media_mode = "mix"
        self.mixed_media = state.get("mixed_media", [])
        self.cover_path = state.get("cover_path", "")
        self.last_render_path = state.get("last_render_path", "")
        self.combo_sub_style.set(state.get("sub_style", "TikTok / Hormozi"))
        
        # Restore audio and BGM paths
        self.audio_path = state.get("audio_path", "")
        if self.audio_path and os.path.exists(self.audio_path):
            self.lbl_audio_name.configure(text=f"AUDIO ACTIVO: {os.path.basename(self.audio_path)[:25]}", text_color=COLOR_SUCCESS)
            self.btn_audio.configure(border_color=COLOR_SUCCESS)
        else:
            self.lbl_audio_name.configure(text="No hay audio activo", text_color="#444")
            self.btn_audio.configure(border_color="#222")

        self.var_music.set(state.get("music_enabled", True))
        self.current_music_path = state.get("music_path", "")
        if self.current_music_path and os.path.exists(self.current_music_path):
            self.combo_music.set(os.path.basename(self.current_music_path))
        
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
                
        # Sync Audio path generated in VoiceTab
        if hasattr(self.main, "audio_path") and self.main.audio_path:
            if self.audio_path != self.main.audio_path and os.path.exists(self.main.audio_path):
                self.audio_path = self.main.audio_path
                self.lbl_audio_name.configure(text=f"AUDIO ACTIVO: {os.path.basename(self.audio_path)[:25]}", text_color=COLOR_SUCCESS)
                self.btn_audio.configure(border_color=COLOR_SUCCESS)
                self.check_ready_state()

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

