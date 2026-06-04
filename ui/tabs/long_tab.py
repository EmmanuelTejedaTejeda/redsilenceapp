import os
import threading
import json
import random
import re
import customtkinter as ctk
from tkinter import filedialog
import config.prompts as prompts_cfg
from core import utils as prompts_utils
from modules import gemini_client, groq_client, voice_generator
from modules.render_long import render_long_video_project

# --- THEME CONSTANTS (Premium Dark Neon Red) ---
COLOR_BG = "#101010"
COLOR_CARD = "#141414"
COLOR_ACCENT = "#D32F2F"
COLOR_ACCENT_HOVER = "#B71C1C"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_SUB = "#666666"
COLOR_SUCCESS = "#00E676"
FONT_TITLE = ("Impact", 32)
FONT_SECTION = ("Arial", 12, "bold")
FONT_MONO = ("Consolas", 11)

class LongTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main = main_window
        
        # Inyectar navegación
        if hasattr(self.main, 'create_nav_controls'):
            self.main.create_nav_controls(self, 0)
            
        # Directorio de música
        self.music_folder = os.path.abspath(os.path.join(os.getcwd(), "assets", "audio", "music"))
        if not os.path.exists(self.music_folder):
            try:
                os.makedirs(self.music_folder)
            except:
                pass
                
        # Estado del proyecto de videos largos
        self.project_name = "Proyecto_Video_Largo"
        self.output_folder = os.path.join(os.path.expanduser("~"), "Videos")
        self.music_enabled = True
        self.chapters_data = [] # Lista de diccionarios: {"title": "", "guion": "", "voice_audio": "", "media": [], "music_path": ""}
        
        self.chapter_widgets = []
        self.rendering = False
        self.segmenting = False

        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)
        
        # Grid layout: Col 0 (Fijo - Entrada), Col 1 (Expansiva - Capítulos)
        self.grid_container.grid_columnconfigure(0, weight=0, minsize=420)
        self.grid_container.grid_columnconfigure(1, weight=1)
        self.grid_container.grid_rowconfigure(0, weight=1)
        
        self.setup_ui()
        self.refresh_music_dropdowns()

    def setup_ui(self):
        # ==========================
        # LEFT PANEL: CONTROLS & SCRIPT
        # ==========================
        left_panel = ctk.CTkFrame(self.grid_container, fg_color=COLOR_BG, corner_radius=15, border_width=1, border_color="#1F1F1F")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=10)
        
        # Scrollable container inside left panel to avoid overflows
        scroll_left = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        
        # Status Label (Fixed at bottom of left panel)
        self.lbl_status = ctk.CTkLabel(left_panel, text="LISTO", font=FONT_MONO, text_color=COLOR_TEXT_SUB)
        self.lbl_status.pack(side="bottom", pady=5)

        # Hero Render Button (Fixed at bottom of left panel)
        self.btn_render = ctk.CTkButton(left_panel, text="⚡ RENDERIZAR VIDEO LARGO ⚡", font=("Arial", 14, "bold"), height=55, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.run_render_thread)
        self.btn_render.pack(side="bottom", fill="x", padx=15, pady=(5, 5))
        
        scroll_left.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        
        # Title
        ctk.CTkLabel(scroll_left, text="VIDEOS LARGOS 16:9", font=FONT_TITLE, text_color="#333").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(scroll_left, text="Crea producciones de larga duración...", font=("Arial", 11), text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(0, 15))
        
        # Full Script Input Label
        ctk.CTkLabel(scroll_left, text="GUION COMPLETO (BASE)", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(5, 2))
        
        # Full Script Textbox
        self.txt_full_script = ctk.CTkTextbox(scroll_left, height=220, fg_color="#080808", border_width=1, border_color="#222", text_color="#DDD", wrap="word")
        self.txt_full_script.pack(fill="x", pady=(0, 10))
        self.txt_full_script.insert("0.0", "Pega tu historia completa aquí para segmentarla con Inteligencia Artificial por capítulos...")
        
        # IA Segment Button
        self.btn_segment = ctk.CTkButton(scroll_left, text="✂️ SEGMENTAR GUION CON IA ⚡", font=("Arial", 12, "bold"), height=42, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.run_segmentation_thread)
        self.btn_segment.pack(fill="x", pady=(0, 15))
        
        # Settings Card
        settings_card = ctk.CTkFrame(scroll_left, fg_color=COLOR_CARD, corner_radius=10, border_width=1, border_color="#1A1A1A")
        settings_card.pack(fill="x", pady=(5, 15), padx=2)
        
        # Project Name
        ctk.CTkLabel(settings_card, text="NOMBRE DEL PROYECTO", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(anchor="w", padx=15, pady=(10, 2))
        self.entry_proj_name = ctk.CTkEntry(settings_card, placeholder_text="Proyecto_Video_Largo", height=32, fg_color="#080808", border_color="#222")
        self.entry_proj_name.pack(fill="x", padx=15, pady=(0, 10))
        self.entry_proj_name.insert(0, self.project_name)
        
        # Output Folder Selection
        ctk.CTkLabel(settings_card, text="CARPETA DE SALIDA", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(anchor="w", padx=15, pady=(5, 2))
        out_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        out_row.pack(fill="x", padx=15, pady=(0, 10))
        
        self.entry_output = ctk.CTkEntry(out_row, placeholder_text="Selecciona carpeta...", height=32, fg_color="#080808", border_color="#222")
        self.entry_output.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_output.insert(0, self.output_folder)
        
        ctk.CTkButton(out_row, text="📂", width=35, height=32, fg_color="#222", hover_color="#333", command=self.browse_output_folder).pack(side="right")
        
        # Music Global Checkbox
        self.var_music_enabled = ctk.BooleanVar(value=self.music_enabled)
        self.chk_music = ctk.CTkCheckBox(settings_card, text="HABILITAR MÚSICA DE FONDO (BGM)", variable=self.var_music_enabled, command=self.toggle_music_option, fg_color=COLOR_ACCENT, border_width=2, font=("Arial", 10, "bold"))
        self.chk_music.pack(anchor="w", padx=15, pady=(5, 12))

        # Filter LUT Combo Box
        ctk.CTkLabel(settings_card, text="ESTILO VISUAL (LUT)", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(anchor="w", padx=15, pady=(5, 2))
        self.combo_luts = ctk.CTkComboBox(settings_card, values=["Ninguno", "Gore Rojo", "Terror Frío", "Misterio Oscuro", "Vintage VHS"],
                                           fg_color="#080808", border_color="#222", button_color="#1A1A1A",
                                           text_color="white", font=("Arial", 11), height=32)
        self.combo_luts.pack(fill="x", padx=15, pady=(0, 12))
        self.combo_luts.set("Ninguno")

        # ==========================
        # RIGHT PANEL: CHAPTER CARDS
        # ==========================
        right_panel = ctk.CTkFrame(self.grid_container, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#181818")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        
        # Header Right
        header_r = ctk.CTkFrame(right_panel, fg_color="transparent", height=45)
        header_r.pack(fill="x", padx=20, pady=(15, 10))
        ctk.CTkLabel(header_r, text="CAPÍTULOS TEMÁTICOS Y COMPOSICIÓN", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(side="left")
        
        # Clear/Add Manual Chapter Buttons
        ctk.CTkButton(header_r, text="+ CAPÍTULO MANUAL", width=130, height=28, fg_color="#1A1A1A", hover_color="#262626", font=("Arial", 10, "bold"), command=self.add_manual_chapter).pack(side="right", padx=5)
        ctk.CTkButton(header_r, text="🗑️ BORRAR CACHÉ", width=110, height=28, fg_color="#222", hover_color="#333", font=("Arial", 10, "bold"), command=self.clear_project_cache).pack(side="right", padx=5)
        ctk.CTkButton(header_r, text="🗑️ LIMPIAR TODO", width=100, height=28, fg_color="#250808", hover_color="#3A0D0D", font=("Arial", 10, "bold"), text_color="#FFAAAA", command=self.clear_all_chapters).pack(side="right", padx=5)

        # Scrollable Area for Chapters list
        self.scroll_chapters = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.scroll_chapters.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Initial empty state message
        self.lbl_empty_message = ctk.CTkLabel(self.scroll_chapters, text="No hay capítulos creados.\n\nEscribe un guion a la izquierda y pulsa 'Segmentar Guion con IA'\no agrega capítulos manualmente para empezar la producción.", font=("Arial", 12), text_color=COLOR_TEXT_SUB, pady=100)
        self.lbl_empty_message.pack(fill="both", expand=True)

    def browse_output_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_folder)
        if folder:
            self.output_folder = folder
            self.entry_output.delete(0, "end")
            self.entry_output.insert(0, folder)

    def toggle_music_option(self):
        self.music_enabled = self.var_music_enabled.get()
        # Actualizar visibilidad de dropdowns de música
        self.refresh_music_dropdowns()

    def add_manual_chapter(self):
        # Ocultar mensaje vacío si existe
        if self.lbl_empty_message:
            self.lbl_empty_message.pack_forget()
            
        new_cap = {
            "title": f"Capítulo {len(self.chapters_data) + 1}",
            "guion": "",
            "voice_audio": "",
            "media": [],
            "music_path": ""
        }
        self.chapters_data.append(new_cap)
        self.rebuild_chapters_ui()

    def clear_all_chapters(self):
        self.chapters_data = []
        self.rebuild_chapters_ui()

    def run_segmentation_thread(self):
        guion = self.txt_full_script.get("0.0", "end").strip()
        if not guion or "Pega tu historia completa aquí" in guion:
            self.update_status("⚠️ Por favor, introduce un guion válido primero.", "orange")
            return
            
        provider = getattr(self.main, "llm_provider", "gemini")
        if provider == "groq":
            api_key = getattr(self.main, "groq_api_key", "")
            bot_name = "GROQ"
        else:
            api_key = getattr(self.main, "google_api_key", "")
            bot_name = "GEMINI"
            
        if not api_key:
            self.update_status(f"⚠️ Configura tu API Key de {bot_name} en el menú de engranaje ⚙️", "orange")
            return
            
        self.segmenting = True
        self.btn_segment.configure(state="disabled", text="SEGMENTANDO GUION...")
        self.update_status(f"🧠 SEGMENTANDO GUION CON {bot_name}...", "#FFD700")
        
        threading.Thread(target=self.segment_guion, args=(guion, api_key, provider), daemon=True).start()

    def clean_json_string(self, raw_str):
        # Quitar bloques de código markdown si los hay
        s = raw_str.strip()
        if s.startswith("```json"):
            s = s[7:]
        elif s.startswith("```"):
            s = s[3:]
        if s.endswith("```"):
            s = s[:-3]
        return s.strip()

    def segment_guion(self, guion, api_key, provider):
        try:
            # Plantilla estructurada para segmentación limpia
            prompt = (
                "Toma el siguiente guion y divídelo en capítulos temáticos lógicos de aproximadamente 30-90 segundos de duración al hablar.\n"
                "Devuelve el resultado únicamente en formato JSON estructurado como una lista de objetos.\n"
                "Cada objeto debe tener la siguiente estructura exacta:\n"
                "[\n"
                "  {\n"
                "    \"chapter_index\": 0,\n"
                "    \"title\": \"Breve título descriptivo\",\n"
                "    \"guion\": \"El texto del guion de este capítulo únicamente\"\n"
                "  },\n"
                "  ...\n"
                "]\n"
                "Devuelve ÚNICAMENTE el JSON crudo, sin bloques de código ```json o explicaciones de texto adicionales, para poder parsearlo directamente con json.loads().\n\n"
                f"Guion a segmentar:\n{guion}"
            )
            
            if provider == "groq":
                result = groq_client.generate_content(prompt, api_key)
            else:
                result = gemini_client.generate_content(prompt, api_key)
                
            clean_result = self.clean_json_string(result)
            
            # Buscar el patrón JSON si hay texto adicional involuntario
            json_match = re.search(r"\[\s*\{.*\}\s*\]", clean_result, re.DOTALL)
            if json_match:
                clean_result = json_match.group(0)

            chapters_list = json.loads(clean_result)
            
            # Inyectar en chapters_data
            parsed_chapters = []
            for item in chapters_list:
                parsed_chapters.append({
                    "title": item.get("title", f"Capítulo {item.get('chapter_index', 0)+1}"),
                    "guion": item.get("guion", ""),
                    "voice_audio": "",
                    "media": [],
                    "music_path": ""
                })
                
            self.after(0, lambda: self.on_segmentation_success(parsed_chapters))
        except Exception as e:
            print("Error segmentando guion:")
            traceback_msg = traceback.format_exc() if 'traceback' in globals() else str(e)
            print(traceback_msg)
            self.after(0, lambda: self.on_segmentation_error(str(e)))

    def on_segmentation_success(self, parsed_chapters):
        self.segmenting = False
        self.btn_segment.configure(state="normal", text="✂️ SEGMENTAR GUION CON IA ⚡")
        self.chapters_data = parsed_chapters
        self.rebuild_chapters_ui()
        self.update_status("✅ GUION SEGMENTADO EXITOSAMENTE", COLOR_SUCCESS)

    def on_segmentation_error(self, err_msg):
        self.segmenting = False
        self.btn_segment.configure(state="normal", text="✂️ SEGMENTAR GUION CON IA ⚡")
        self.update_status(f"❌ ERROR AL SEGMENTAR: {err_msg[:40]}", "red")
        
        # Diálogo interactivo
        import tkinter.messagebox as msgbox
        msgbox.showerror("Error de Segmentación", f"La IA no devolvió un JSON válido. Inténtalo de nuevo o agrega capítulos manualmente.\nDetalle: {err_msg}")

    def rebuild_chapters_ui(self):
        # Destruir widgets antiguos
        for w in self.scroll_chapters.winfo_children():
            w.destroy()
        self.chapter_widgets = []

        if not self.chapters_data:
            self.lbl_empty_message = ctk.CTkLabel(self.scroll_chapters, text="No hay capítulos creados.\n\nEscribe un guion a la izquierda y pulsa 'Segmentar Guion con IA'\no agrega capítulos manualmente para empezar la producción.", font=("Arial", 12), text_color=COLOR_TEXT_SUB, pady=100)
            self.lbl_empty_message.pack(fill="both", expand=True)
            return

        self.lbl_empty_message = None

        # Obtener lista de archivos de música locales para llenar los dropdowns
        music_files = []
        if os.path.exists(self.music_folder):
            music_files = [f for f in os.listdir(self.music_folder) if f.endswith(('.mp3', '.wav', '.ogg'))]

        for i, cap in enumerate(self.chapters_data):
            card = ctk.CTkFrame(self.scroll_chapters, fg_color="#0A0A0A", corner_radius=12, border_width=1, border_color="#1A1A1A")
            card.pack(fill="x", pady=8, padx=5)
            
            # Cabecera de tarjeta
            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=15, pady=(12, 5))
            
            title_lbl = ctk.CTkLabel(hdr, text=f"Capítulo {i+1}:", font=("Arial", 13, "bold"), text_color="white")
            title_lbl.pack(side="left")
            
            title_entry = ctk.CTkEntry(hdr, width=220, height=24, fg_color="#050505", border_color="#181818", text_color="white")
            title_entry.pack(side="left", padx=5)
            title_entry.insert(0, cap.get("title", ""))
            title_entry.bind("<KeyRelease>", lambda event, idx=i, entry=title_entry: self.update_chapter_title(idx, entry))
            
            # Botón de borrar capítulo individual
            ctk.CTkButton(hdr, text="✖", width=24, height=24, fg_color="transparent", hover_color="#220000", text_color="#666", command=lambda idx=i: self.delete_chapter(idx)).pack(side="right", padx=(2, 0))

            # Botón de borrar caché de capítulo individual (si existe el archivo)
            proj_name_curr = self.entry_proj_name.get().strip() or "Proyecto_Video_Largo"
            chunk_file_path = os.path.join(os.getcwd(), "projects", "videos_largos", proj_name_curr, "chunks", f"chapter_{i}.mp4")
            has_cache = os.path.exists(chunk_file_path) and os.path.getsize(chunk_file_path) > 0
            cache_color = COLOR_SUCCESS if has_cache else "#444"
            
            btn_clear_cap_cache = ctk.CTkButton(hdr, text="♻️", width=24, height=24, fg_color="transparent", hover_color="#222", text_color=cache_color, command=lambda idx=i: self.clear_chapter_cache(idx))
            btn_clear_cap_cache.pack(side="right", padx=2)
            
            # Contenedor de 2 columnas para Contenido e Inputs
            body_frame = ctk.CTkFrame(card, fg_color="transparent")
            body_frame.pack(fill="x", padx=15, pady=(5, 12))
            body_frame.grid_columnconfigure(0, weight=1)
            body_frame.grid_columnconfigure(1, weight=1, minsize=320)
            
            # Columna izquierda: Guion del Capítulo
            left_col = ctk.CTkFrame(body_frame, fg_color="transparent")
            left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            
            ctk.CTkLabel(left_col, text="GUION DEL CAPÍTULO", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(anchor="w")
            txt_area = ctk.CTkTextbox(left_col, height=110, fg_color="#050505", border_width=1, border_color="#151515", text_color="#CCC", wrap="word")
            txt_area.pack(fill="both", expand=True, pady=(3, 0))
            txt_area.insert("0.0", cap["guion"])
            
            # Guardado interactivo en tiempo real al escribir
            txt_area.bind("<KeyRelease>", lambda event, idx=i, txt=txt_area: self.update_chapter_text(idx, txt))
            
            # Columna derecha: Activos multimedia e audio
            right_col = ctk.CTkFrame(body_frame, fg_color="transparent")
            right_col.grid(row=0, column=1, sticky="nsew")
            
            # Fila 1: Narración (Voz)
            ctk.CTkLabel(right_col, text="VOZ DEL CAPÍTULO (NARRACIÓN)", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(anchor="w")
            voice_row = ctk.CTkFrame(right_col, fg_color="transparent")
            voice_row.pack(fill="x", pady=(2, 8))
            
            voice_label_text = os.path.basename(cap["voice_audio"]) if cap["voice_audio"] else "No seleccionado"
            voice_label_color = COLOR_SUCCESS if cap["voice_audio"] else "#555"
            lbl_voice = ctk.CTkLabel(voice_row, text=voice_label_text, font=FONT_MONO, text_color=voice_label_color, anchor="w")
            lbl_voice.pack(side="left", fill="x", expand=True)
            
            btn_load_voice = ctk.CTkButton(voice_row, text="📁", width=35, height=28, fg_color="#151515", hover_color="#222", command=lambda idx=i, lbl=lbl_voice: self.select_chapter_voice(idx, lbl))
            btn_load_voice.pack(side="right")
            
            btn_generate_voice = ctk.CTkButton(voice_row, text="TTS", width=40, height=28, fg_color="#300A0A", hover_color="#B71C1C", text_color="white", font=("Arial", 10, "bold"), command=lambda idx=i, lbl=lbl_voice: self.open_voice_generator_dialog(idx, lbl))
            btn_generate_voice.pack(side="right", padx=(0, 4))
            
            # Fila 2: Media visual
            ctk.CTkLabel(right_col, text="IMÁGENES / VIDEOS", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(anchor="w")
            media_row = ctk.CTkFrame(right_col, fg_color="transparent")
            media_row.pack(fill="x", pady=(2, 8))
            
            media_label_text = f"🎥 {len(cap['media'])} recursos visuales" if cap["media"] else "Sin recursos visuales"
            media_label_color = COLOR_SUCCESS if cap["media"] else "#555"
            lbl_media = ctk.CTkLabel(media_row, text=media_label_text, font=("Arial", 11), text_color=media_label_color, anchor="w")
            lbl_media.pack(side="left", fill="x", expand=True)
            
            btn_clear_media = ctk.CTkButton(media_row, text="🗑️", width=35, height=28, fg_color="#220505", hover_color="#300", text_color="#F55", command=lambda idx=i, lbl=lbl_media: self.clear_chapter_media(idx, lbl))
            btn_clear_media.pack(side="right", padx=(0, 4))
            
            btn_add_media = ctk.CTkButton(media_row, text="+", width=35, height=28, fg_color="#151515", hover_color="#222", command=lambda idx=i, lbl=lbl_media: self.add_chapter_media(idx, lbl))
            btn_add_media.pack(side="right")
            
            # Fila 3: Música de fondo (BGM)
            lbl_bgm_title = ctk.CTkLabel(right_col, text="MÚSICA DE FONDO (BGM)", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB)
            lbl_bgm_title.pack(anchor="w")
            
            music_row = ctk.CTkFrame(right_col, fg_color="transparent")
            music_row.pack(fill="x", pady=(2, 0))
            
            dropdown_values = music_files if music_files else ["No tracks found"]
            combo_music = ctk.CTkComboBox(music_row, values=dropdown_values, height=28, fg_color="#050505", border_color="#181818", text_color=COLOR_ACCENT)
            combo_music.pack(side="left", fill="x", expand=True, padx=(0, 4))
            
            # Seleccionar el guardado anterior
            if cap["music_path"] and os.path.exists(cap["music_path"]):
                combo_music.set(os.path.basename(cap["music_path"]))
            elif music_files:
                # Asignar el primero por defecto si está vacío
                combo_music.set(music_files[0])
                cap["music_path"] = os.path.join(self.music_folder, music_files[0])
            else:
                combo_music.set("No tracks found")
                
            # Escuchar cambios en el dropdown
            combo_music.configure(command=lambda val, idx=i: self.update_chapter_music(idx, val))
            
            btn_roll = ctk.CTkButton(music_row, text="🎲", width=35, height=28, fg_color="#151515", hover_color="#222", command=lambda idx=i, combo=combo_music: self.roll_chapter_music(idx, combo))
            btn_roll.pack(side="right")
            
            # Desactivar dropdowns visualmente si la música está deshabilitada globalmente
            if not self.music_enabled:
                combo_music.configure(state="disabled")
                btn_roll.configure(state="disabled")
                lbl_bgm_title.configure(text_color="#333")
            
            # Guardamos referencias a widgets dinámicos por si necesitamos actualizarlos externamente
            self.chapter_widgets.append({
                "lbl_voice": lbl_voice,
                "lbl_media": lbl_media,
                "combo_music": combo_music,
                "btn_roll": btn_roll,
                "lbl_bgm_title": lbl_bgm_title
            })

    def delete_chapter(self, index):
        if 0 <= index < len(self.chapters_data):
            self.chapters_data.pop(index)
            self.rebuild_chapters_ui()

    def clear_chapter_cache(self, index):
        proj_name = self.entry_proj_name.get().strip() or "Proyecto_Video_Largo"
        chunk_output = os.path.join(os.getcwd(), "projects", "videos_largos", proj_name, "chunks", f"chapter_{index}.mp4")
        if os.path.exists(chunk_output):
            try:
                os.remove(chunk_output)
                import tkinter.messagebox as msgbox
                msgbox.showinfo("Caché Borrada", f"Caché del Capítulo {index+1} eliminada con éxito.")
                self.rebuild_chapters_ui() # Refrescar colores
            except Exception as e:
                import tkinter.messagebox as msgbox
                msgbox.showerror("Error", f"No se pudo eliminar el archivo de caché:\n{e}")
        else:
            import tkinter.messagebox as msgbox
            msgbox.showinfo("Información", f"No hay caché existente para el Capítulo {index+1}.")

    def clear_project_cache(self):
        proj_name = self.entry_proj_name.get().strip() or "Proyecto_Video_Largo"
        project_chunks_dir = os.path.join(os.getcwd(), "projects", "videos_largos", proj_name, "chunks")
        if os.path.exists(project_chunks_dir):
            try:
                files = os.listdir(project_chunks_dir)
                deleted_count = 0
                for f in files:
                    if f.endswith(".mp4"):
                        os.remove(os.path.join(project_chunks_dir, f))
                        deleted_count += 1
                import tkinter.messagebox as msgbox
                msgbox.showinfo("Caché Borrada", f"Se han eliminado {deleted_count} archivos de caché (.mp4) de este proyecto largo.")
                self.rebuild_chapters_ui() # Refrescar colores
            except Exception as e:
                import tkinter.messagebox as msgbox
                msgbox.showerror("Error", f"No se pudo eliminar la caché del proyecto:\n{e}")
        else:
            import tkinter.messagebox as msgbox
            msgbox.showinfo("Información", "No existe caché para este proyecto.")

    def update_chapter_text(self, index, textbox):
        if 0 <= index < len(self.chapters_data):
            self.chapters_data[index]["guion"] = textbox.get("0.0", "end").strip()

    def select_chapter_voice(self, index, label_widget):
        file_path = filedialog.askopenfilename(
            title="Seleccionar Audio de Voz Narrada",
            filetypes=[("Archivos de Audio", "*.mp3 *.wav *.m4a *.ogg *.aac *.flac")]
        )
        if file_path:
            self.chapters_data[index]["voice_audio"] = file_path
            label_widget.configure(text=os.path.basename(file_path)[:30], text_color=COLOR_SUCCESS)

    def add_chapter_media(self, index, label_widget):
        files = filedialog.askopenfilenames(
            title="Agregar Imágenes o Videos",
            filetypes=[("Imágenes/Videos", "*.jpg *.jpeg *.png *.webp *.mp4 *.mov *.avi *.mkv *.webm")]
        )
        if files:
            # Unir a la lista existente
            self.chapters_data[index]["media"].extend(list(files))
            label_widget.configure(text=f"🎥 {len(self.chapters_data[index]['media'])} recursos visuales", text_color=COLOR_SUCCESS)

    def clear_chapter_media(self, index, label_widget):
        self.chapters_data[index]["media"] = []
        label_widget.configure(text="Sin recursos visuales", text_color="#555")

    def update_chapter_music(self, index, value):
        if value and value != "No tracks found":
            self.chapters_data[index]["music_path"] = os.path.join(self.music_folder, value)

    def roll_chapter_music(self, index, combo_widget):
        if not os.path.exists(self.music_folder):
            return
        files = [f for f in os.listdir(self.music_folder) if f.endswith(('.mp3', '.wav', '.ogg'))]
        if files:
            rolled = random.choice(files)
            combo_widget.set(rolled)
            self.update_chapter_music(index, rolled)

    def refresh_music_dropdowns(self):
        # Buscar todos los archivos de música
        music_files = []
        if os.path.exists(self.music_folder):
            music_files = [f for f in os.listdir(self.music_folder) if f.endswith(('.mp3', '.wav', '.ogg'))]
            
        # Actualizar dropdowns existentes en los widgets de capítulos
        for i, widgets in enumerate(self.chapter_widgets):
            combo = widgets["combo_music"]
            btn_roll = widgets["btn_roll"]
            lbl_bgm_title = widgets["lbl_bgm_title"]
            
            if self.music_enabled:
                combo.configure(state="readonly")
                btn_roll.configure(state="normal")
                lbl_bgm_title.configure(text_color=COLOR_TEXT_SUB)
                
                # Actualizar la lista de tracks disponibles
                if music_files:
                    combo.configure(values=music_files)
                    # Si no hay selección válida, poner la primera
                    curr = combo.get()
                    if curr not in music_files:
                        combo.set(music_files[0])
                        self.chapters_data[i]["music_path"] = os.path.join(self.music_folder, music_files[0])
                else:
                    combo.configure(values=["No tracks found"])
                    combo.set("No tracks found")
            else:
                combo.configure(state="disabled")
                btn_roll.configure(state="disabled")
                lbl_bgm_title.configure(text_color="#333")

    def run_render_thread(self):
        # Validar proyecto
        proj_name = self.entry_proj_name.get().strip()
        if not proj_name:
            self.update_status("⚠️ El nombre del proyecto es obligatorio", "orange")
            return
            
        out_folder = self.entry_output.get().strip()
        if not out_folder or not os.path.exists(out_folder):
            self.update_status("⚠️ Selecciona una carpeta de salida válida", "orange")
            return
            
        if not self.chapters_data:
            self.update_status("⚠️ No hay capítulos asignados para renderizar", "orange")
            return
            
        # Verificar que todos los capítulos tengan audios cargados
        missing_voice = []
        for idx, cap in enumerate(self.chapters_data):
            if not cap.get("voice_audio") or not os.path.exists(cap["voice_audio"]):
                missing_voice.append(idx + 1)
                
        if missing_voice:
            self.update_status(f"⚠️ Faltan audios en Caps: {missing_voice}", "orange")
            import tkinter.messagebox as msgbox
            msgbox.showwarning("Faltan Archivos", f"Debes asignar un audio de voz a cada uno de los capítulos antes de renderizar.\nCapítulos faltantes: {missing_voice}")
            return

        self.project_name = proj_name
        self.output_folder = out_folder
        
        # Deshabilitar botones de render
        self.rendering = True
        self.btn_render.configure(state="disabled", text="CONSTRUYENDO MONTAJE...")
        self.btn_segment.configure(state="disabled")
        self.update_status("🚀 PREPARANDO MOTOR DE RENDER...", "#00E5FF")
        
        # En Windows, para proteger el procesador de 4ta generación (U-series) con hyperthreading (4 threads),
        # limitamos la mezcla en paralelo en el backend y forzamos prioridad del proceso a IDLE.
        # Esto se maneja directamente dentro de render_long.py mediante sub_kwargs y max_workers=1 secuencial.
        
        state_to_render = {
            "project_name": self.project_name,
            "output_folder": self.output_folder,
            "music_enabled": self.music_enabled,
            "chapters": self.chapters_data
        }
        
        groq_key = getattr(self.main, "groq_api_key", "")
        lut_name = self.combo_luts.get()
        
        threading.Thread(
            target=self.render_project_bg,
            args=(state_to_render, groq_key, lut_name),
            daemon=True
        ).start()

    def render_project_bg(self, state, groq_key, lut_name):
        try:
            output_file = render_long_video_project(
                project_state=state,
                output_final_mp4="", # Se genera dentro en base al nombre del proyecto
                status_callback=self.update_render_status,
                groq_key=groq_key,
                aspect_ratio="16:9",
                lut_name=lut_name
            )
            
            if output_file:
                self.after(0, lambda: self.on_render_success(output_file))
            else:
                self.after(0, lambda: self.on_render_error("El motor de render reportó un error."))
        except Exception as e:
            print("Error en render background:")
            traceback.print_exc()
            self.after(0, lambda: self.on_render_error(str(e)))

    def update_render_status(self, text, color=None):
        # Actualiza el estado tanto en el hilo principal
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color if color else "#FFD700"))
        # Sincronizar con la barra de estado de la ventana principal
        if hasattr(self.main, 'update_status'):
            self.after(0, lambda: self.main.update_status(text, color))

    def update_status(self, text, color=None):
        self.update_render_status(text, color)

    def on_render_success(self, output_file):
        self.rendering = False
        self.btn_render.configure(state="normal", text="⚡ RENDERIZAR VIDEO LARGO ⚡")
        self.btn_segment.configure(state="normal")
        self.update_status("✅ PROCESO COMPLETADO", COLOR_SUCCESS)
        
        # Diálogo y reproducción directa del archivo compilado
        import tkinter.messagebox as msgbox
        msgbox.showinfo("Render Exitoso", f"Video renderizado correctamente en:\n{output_file}")
        
        # Abrir el directorio del video
        try:
            if os.name == 'nt':
                os.startfile(os.path.dirname(output_file))
        except:
            pass

    def on_render_error(self, err_msg):
        self.rendering = False
        self.btn_render.configure(state="normal", text="⚡ RENDERIZAR VIDEO LARGO ⚡")
        self.btn_segment.configure(state="normal")
        self.update_status(f"❌ FALLO EN EL RENDER: {err_msg[:40]}", "red")
        
        import tkinter.messagebox as msgbox
        msgbox.showerror("Error de Render", f"No se pudo completar el renderizado de la producción larga.\nDetalle: {err_msg}")

    # --- PROJECT STATE LOGIC (Compatibilidad con ProjectManager) ---
    def get_state(self):
        return {
            "project_name": self.project_name,
            "output_folder": self.output_folder,
            "music_enabled": self.music_enabled,
            "chapters": self.chapters_data,
            "lut_name": self.combo_luts.get()
        }

    def restore_state(self, state):
        if not state:
            return
            
        self.project_name = state.get("project_name", "Proyecto_Video_Largo")
        self.output_folder = state.get("output_folder", os.path.join(os.path.expanduser("~"), "Videos"))
        self.music_enabled = state.get("music_enabled", True)
        self.chapters_data = state.get("chapters", [])
        self.combo_luts.set(state.get("lut_name", "Ninguno"))
        
        # Inyectar en inputs
        self.entry_proj_name.delete(0, "end")
        self.entry_proj_name.insert(0, self.project_name)
        
        self.entry_output.delete(0, "end")
        self.entry_output.insert(0, self.output_folder)
        
        self.var_music_enabled.set(self.music_enabled)
        
        # Redibujar UI
        self.rebuild_chapters_ui()
        self.refresh_music_dropdowns()

    def focus_set(self):
        """Override para sincronizar el guion principal si el usuario viene de ConceptTab"""
        super().focus_set()
        
        # Si el usuario generó una historia en la pestaña concept, se la traemos por defecto
        if hasattr(self.main, "generated_story") and self.main.generated_story:
            full_txt = self.txt_full_script.get("0.0", "end").strip()
            if not full_txt or "Pega tu historia completa aquí" in full_txt:
                self.txt_full_script.delete("0.0", "end")
                self.txt_full_script.insert("0.0", self.main.generated_story)
                
        # Sincronizar dropdowns de música
        self.refresh_music_dropdowns()

    def update_chapter_title(self, index, entry):
        if 0 <= index < len(self.chapters_data):
            self.chapters_data[index]["title"] = entry.get().strip()

    def open_voice_generator_dialog(self, index, label_widget):
        # 1. Obtener API Key y validar
        api_key = getattr(self.main, "google_api_key", "")
        if not api_key:
            self.update_status("Configura tu API Key de Gemini en el menu de engranaje", "orange")
            import tkinter.messagebox as msgbox
            msgbox.showwarning("API Key Faltante", "Por favor, configura tu API Key de Gemini en los ajustes globales (icono de engranaje en el Command Center).")
            return

        # 2. Obtener plantilla de instrucciones
        voice_instructions_path = os.path.join(os.getcwd(), "config", "prompts", "voice", "voice_instructions2.txt")
        if not os.path.exists(voice_instructions_path):
            voice_instructions_path = os.path.join(os.getcwd(), "config", "prompts", "voice", "voice_instructions.txt")

        # 3. Crear ventana emergente
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Generar Voz Narracion - Capitulo {index+1}")
        dialog.geometry("600x480")
        dialog.configure(fg_color="#0F0F0F")
        dialog.transient(self) # Mantener sobre la ventana principal
        dialog.grab_set()      # Bloquear interacción con ventana principal
        dialog.resizable(False, False)

        # Centrar diálogo respecto a la ventana principal
        self.center_toplevel(dialog)

        # Contenedor principal
        main_frame = ctk.CTkFrame(dialog, fg_color="#0F0F0F", corner_radius=0)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Título
        ctk.CTkLabel(main_frame, text="GENERADOR DE VOZ GEMINI 2.5", font=("Impact", 24), text_color="#D32F2F").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(main_frame, text="Voz predeterminada: Charon  |  Estilo: Horror Paranoico v2", font=("Arial", 11), text_color="#666666").pack(anchor="w", pady=(0, 15))

        # Cuadro de texto
        ctk.CTkLabel(main_frame, text="TEXTO DEL NARRADOR (PEGA O EDITA EL GUION):", font=("Arial", 10, "bold"), text_color="#888888").pack(anchor="w", pady=(5, 2))
        
        txt_input = ctk.CTkTextbox(main_frame, height=200, fg_color="#050505", border_width=1, border_color="#222", text_color="#DDD", wrap="word")
        txt_input.pack(fill="x", pady=(0, 15))
        
        # Cargar texto actual del capítulo por defecto
        current_text = self.chapters_data[index].get("guion", "")
        txt_input.insert("0.0", current_text)

        # Indicador de estado del proceso
        lbl_status = ctk.CTkLabel(main_frame, text="Listo para generar", font=("Consolas", 11), text_color="#666666")
        lbl_status.pack(anchor="w", pady=(0, 10))

        # Fila de botones
        btn_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        def on_generate():
            # Deshabilitar botones mientras genera
            btn_gen.configure(state="disabled", text="Generando...")
            btn_cancel.configure(state="disabled")
            lbl_status.configure(text="Llamando a la API de Gemini 2.5 (esto puede tomar unos segundos)...", text_color="#FFD700")
            
            text_to_send = txt_input.get("0.0", "end").strip()
            if not text_to_send:
                lbl_status.configure(text="El texto no puede estar vacio.", text_color="orange")
                btn_gen.configure(state="normal", text="Generar Audio")
                btn_cancel.configure(state="normal")
                return

            def thread_func():
                try:
                    proj_name = self.entry_proj_name.get().strip() or "Proyecto_Video_Largo"
                    
                    # Obtener carpeta de audios configurada en los ajustes del usuario
                    audio_dir = None
                    if hasattr(self.main, "settings") and self.main.settings:
                        audio_dir = self.main.settings.get("audio_folder_path")
                    
                    if not audio_dir:
                        audio_dir = os.path.join(os.path.expanduser("~"), "Videos", "SilencioRojo", "Audio")
                        
                    os.makedirs(audio_dir, exist_ok=True)
                    output_file = os.path.join(audio_dir, f"{proj_name}_cap_{index+1}_voz.wav")
                    
                    # Llamar al generador de voz
                    voice_generator.generate_voice(
                        text=text_to_send,
                        api_key=api_key,
                        voice_instructions_path=voice_instructions_path,
                        output_path=output_file,
                        model_name="gemini-2.5-flash-preview-tts"
                    )
                    
                    self.after(0, lambda: success_callback(output_file))
                except Exception as e:
                    self.after(0, lambda err=str(e): error_callback(err))

            threading.Thread(target=thread_func, daemon=True).start()

        def success_callback(file_path):
            self.chapters_data[index]["voice_audio"] = file_path
            # Actualizar etiqueta en la UI del capítulo
            label_widget.configure(text=os.path.basename(file_path)[:30], text_color=COLOR_SUCCESS)
            self.update_status(f"Audio generado para Cap {index+1}: {os.path.basename(file_path)}", COLOR_SUCCESS)
            
            btn_gen.configure(state="normal", text="Generar Audio")
            btn_cancel.configure(state="normal")
            lbl_status.configure(text="Audio generado y guardado correctamente.", text_color=COLOR_SUCCESS)
            
            import tkinter.messagebox as msgbox
            msgbox.showinfo("Exito", f"Voz del Capitulo {index+1} generada y asignada correctamente.\nArchivo: {file_path}")
            dialog.destroy()

        def error_callback(err_msg):
            btn_gen.configure(state="normal", text="Generar Audio")
            btn_cancel.configure(state="normal")
            lbl_status.configure(text=f"Error: {err_msg[:60]}...", text_color="red")
            
            import tkinter.messagebox as msgbox
            msgbox.showerror("Error de Generacion", f"No se pudo generar la voz con Gemini:\n{err_msg}")

        btn_gen = ctk.CTkButton(btn_row, text="Generar Audio", font=("Arial", 12, "bold"), fg_color="#D32F2F", hover_color="#B71C1C", height=36, command=on_generate)
        btn_gen.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_cancel = ctk.CTkButton(btn_row, text="Cancelar", font=("Arial", 12), fg_color="#222", hover_color="#333", height=36, command=dialog.destroy)
        btn_cancel.pack(side="right", width=120)

    def center_toplevel(self, toplevel):
        toplevel.update_idletasks()
        width = toplevel.winfo_width()
        height = toplevel.winfo_height()
        
        main_x = self.main.winfo_x()
        main_y = self.main.winfo_y()
        main_w = self.main.winfo_width()
        main_h = self.main.winfo_height()
        
        x = main_x + (main_w // 2) - (width // 2)
        y = main_y + (main_h // 2) - (height // 2)
        
        toplevel.geometry(f"+{x}+{y}")
