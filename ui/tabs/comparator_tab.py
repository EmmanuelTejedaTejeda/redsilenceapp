import os
import threading
import json
import traceback
import customtkinter as ctk
from tkinter import filedialog
from modules.video_benchmark import (
    download_youtube_audio,
    transcribe_audio_benchmark,
    calculate_pacing_metrics,
    compare_narrative_ai
)

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

class ComparatorTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main = main_window
        
        # Sincronizar controles de navegación si existen
        if hasattr(self.main, 'create_nav_controls'):
            self.main.create_nav_controls(self, 0)
            
        self.cache_dir = os.path.abspath(os.path.join(os.getcwd(), "cache", "benchmark"))
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Estado del módulo
        self.my_video_data = {"script": "", "metrics": None}
        self.ref_video_data = {"script": "", "metrics": None}
        
        self.my_script_full = ""
        self.ref_script_full = ""
        self.my_txt_path = ""
        self.ref_txt_path = ""
        
        self.processing_my = False
        self.processing_ref = False
        self.comparing = False
        
        self.setup_ui()

    def setup_ui(self):
        # Grid layout: Col 0 (Fijo - Entrada de URLs), Col 1 (Expansivo - Visores y Reporte)
        self.grid_columnconfigure(0, weight=0, minsize=420)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==========================
        # LEFT PANEL: URLS & ACTIONS
        # ==========================
        left_panel = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=15, border_width=1, border_color="#1F1F1F")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=10)
        
        scroll_left = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        scroll_left.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        
        # Título del Panel
        ctk.CTkLabel(scroll_left, text="BENCHMARK NARRATIVO", font=FONT_TITLE, text_color="#222").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(scroll_left, text="Compara y optimiza tus guiones largos...", font=("Arial", 11), text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(0, 15))
        
        # --- MI VIDEO ---
        ctk.CTkLabel(scroll_left, text="1. MI VIDEO (URL / ARCHIVO LOCAL)", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(5, 2))
        self.entry_my_url = ctk.CTkEntry(scroll_left, placeholder_text="Pega URL o ruta de archivo local...", height=35, fg_color="#080808", border_color="#222")
        self.entry_my_url.pack(fill="x", pady=(0, 5))
        
        btn_frame_my = ctk.CTkFrame(scroll_left, fg_color="transparent")
        btn_frame_my.pack(fill="x", pady=(0, 20))
        btn_frame_my.grid_columnconfigure(0, weight=3)
        btn_frame_my.grid_columnconfigure(1, weight=2)
        
        self.btn_my_analyze = ctk.CTkButton(btn_frame_my, text="📥 ANALIZAR", font=("Arial", 11, "bold"), height=35, fg_color="#1A1A1A", hover_color="#262626", command=lambda: self.run_analyze_thread("my"))
        self.btn_my_analyze.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        self.btn_my_browse = ctk.CTkButton(btn_frame_my, text="📂 LOCAL", font=("Arial", 11, "bold"), height=35, fg_color="#222", hover_color="#333", command=lambda: self.browse_local_file("my"))
        self.btn_my_browse.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        # --- COMPETENCIA / REFERENCIA ---
        ctk.CTkLabel(scroll_left, text="2. COMPETIDOR / REFERENCIA (URL / LOCAL)", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(5, 2))
        self.entry_ref_url = ctk.CTkEntry(scroll_left, placeholder_text="Pega URL o ruta de archivo local...", height=35, fg_color="#080808", border_color="#222")
        self.entry_ref_url.pack(fill="x", pady=(0, 5))
        
        btn_frame_ref = ctk.CTkFrame(scroll_left, fg_color="transparent")
        btn_frame_ref.pack(fill="x", pady=(0, 20))
        btn_frame_ref.grid_columnconfigure(0, weight=3)
        btn_frame_ref.grid_columnconfigure(1, weight=2)
        
        self.btn_ref_analyze = ctk.CTkButton(btn_frame_ref, text="📥 ANALIZAR", font=("Arial", 11, "bold"), height=35, fg_color="#1A1A1A", hover_color="#262626", command=lambda: self.run_analyze_thread("ref"))
        self.btn_ref_analyze.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        self.btn_ref_browse = ctk.CTkButton(btn_frame_ref, text="📂 LOCAL", font=("Arial", 11, "bold"), height=35, fg_color="#222", hover_color="#333", command=lambda: self.browse_local_file("ref"))
        self.btn_ref_browse.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        # --- BOTÓN DE ACCIÓN COMPARATIVA (FIJO EN EL FONDO) ---
        self.lbl_status = ctk.CTkLabel(left_panel, text="LISTO", font=FONT_MONO, text_color=COLOR_TEXT_SUB)
        self.lbl_status.pack(side="bottom", pady=5)
        
        self.btn_compare = ctk.CTkButton(left_panel, text="⚡ COMPARAR GUIONES Y RITMO ⚡", font=("Arial", 13, "bold"), height=50, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.run_comparison_thread)
        self.btn_compare.pack(side="bottom", fill="x", padx=15, pady=(5, 5))

        # ==========================
        # RIGHT PANEL: METRICS, SCRIPTS & REPORT
        # ==========================
        right_panel = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#181818")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(2, 10), pady=10)
        
        # Usar Scrollable Frame para evitar desbordamiento vertical de todo el reporte
        scroll_right = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        scroll_right.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Fila de Métricas (Mi Video vs Referencia)
        metrics_frame = ctk.CTkFrame(scroll_right, fg_color="transparent")
        metrics_frame.pack(fill="x", pady=(0, 15))
        metrics_frame.grid_columnconfigure(0, weight=1)
        metrics_frame.grid_columnconfigure(1, weight=1)
        
        # Tarjeta Mi Video
        card_my = ctk.CTkFrame(metrics_frame, fg_color="#0A0A0A", border_width=1, border_color="#1F1F1F", corner_radius=10)
        card_my.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=5)
        ctk.CTkLabel(card_my, text="MI VIDEO (MÉTRICAS)", font=("Arial", 11, "bold"), text_color=COLOR_ACCENT).pack(anchor="w", padx=15, pady=(10, 5))
        self.lbl_my_wpm = ctk.CTkLabel(card_my, text="WPM: --- (Ritmo)", font=("Arial", 11), text_color="#AAA")
        self.lbl_my_wpm.pack(anchor="w", padx=15)
        self.lbl_my_silences = ctk.CTkLabel(card_my, text="Silencios dramáticos: ---", font=("Arial", 11), text_color="#AAA")
        self.lbl_my_silences.pack(anchor="w", padx=15)
        self.lbl_my_duration = ctk.CTkLabel(card_my, text="Duración estimada: ---", font=("Arial", 11), text_color="#AAA")
        self.lbl_my_duration.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Tarjeta Referencia
        card_ref = ctk.CTkFrame(metrics_frame, fg_color="#0A0A0A", border_width=1, border_color="#1F1F1F", corner_radius=10)
        card_ref.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=5)
        ctk.CTkLabel(card_ref, text="COMPETIDOR (MÉTRICAS)", font=("Arial", 11, "bold"), text_color=COLOR_SUCCESS).pack(anchor="w", padx=15, pady=(10, 5))
        self.lbl_ref_wpm = ctk.CTkLabel(card_ref, text="WPM: --- (Ritmo)", font=("Arial", 11), text_color="#AAA")
        self.lbl_ref_wpm.pack(anchor="w", padx=15)
        self.lbl_ref_silences = ctk.CTkLabel(card_ref, text="Silencios dramáticos: ---", font=("Arial", 11), text_color="#AAA")
        self.lbl_ref_silences.pack(anchor="w", padx=15)
        self.lbl_ref_duration = ctk.CTkLabel(card_ref, text="Duración estimada: ---", font=("Arial", 11), text_color="#AAA")
        self.lbl_ref_duration.pack(anchor="w", padx=15, pady=(0, 10))

        # Fila de Guiones Transcritos
        scripts_frame = ctk.CTkFrame(scroll_right, fg_color="transparent")
        scripts_frame.pack(fill="x", pady=(0, 15))
        scripts_frame.grid_columnconfigure(0, weight=1)
        scripts_frame.grid_columnconfigure(1, weight=1)
        
        # Textbox Mi Video
        col_my = ctk.CTkFrame(scripts_frame, fg_color="transparent")
        col_my.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        hdr_my = ctk.CTkFrame(col_my, fg_color="transparent")
        hdr_my.pack(fill="x")
        ctk.CTkLabel(hdr_my, text="GUION DE MI VIDEO (EDITABLE)", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(side="left")
        self.btn_open_my_txt = ctk.CTkButton(hdr_my, text="📂 ABRIR TXT", width=70, height=20, font=("Arial", 9, "bold"), fg_color="#222", hover_color="#333", command=self.open_my_txt)
        self.btn_open_my_txt.pack(side="right")
        
        self.txt_my_script = ctk.CTkTextbox(col_my, height=180, fg_color="#050505", border_width=1, border_color="#151515", text_color="#CCC", wrap="word")
        self.txt_my_script.pack(fill="both", expand=True, pady=(3, 0))
        
        # Textbox Referencia
        col_ref = ctk.CTkFrame(scripts_frame, fg_color="transparent")
        col_ref.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        
        hdr_ref = ctk.CTkFrame(col_ref, fg_color="transparent")
        hdr_ref.pack(fill="x")
        ctk.CTkLabel(hdr_ref, text="GUION DEL COMPETIDOR (EDITABLE)", font=("Arial", 10, "bold"), text_color=COLOR_TEXT_SUB).pack(side="left")
        self.btn_open_ref_txt = ctk.CTkButton(hdr_ref, text="📂 ABRIR TXT", width=70, height=20, font=("Arial", 9, "bold"), fg_color="#222", hover_color="#333", command=self.open_ref_txt)
        self.btn_open_ref_txt.pack(side="right")
        
        self.txt_ref_script = ctk.CTkTextbox(col_ref, height=180, fg_color="#050505", border_width=1, border_color="#151515", text_color="#CCC", wrap="word")
        self.txt_ref_script.pack(fill="both", expand=True, pady=(3, 0))
        
        # Panel del Reporte Comparativo de IA
        ctk.CTkLabel(scroll_right, text="INFORME ESTRATÉGICO DE VIRALIZACIÓN (AUDITORÍA DE IA)", font=FONT_SECTION, text_color=COLOR_TEXT_SUB).pack(anchor="w", pady=(10, 2))
        self.txt_report = ctk.CTkTextbox(scroll_right, height=450, fg_color="#050505", border_width=1, border_color="#121212", text_color="#00E676", font=FONT_MONO, wrap="word")
        self.txt_report.pack(fill="x", pady=(0, 10))
        self.txt_report.insert("0.0", "Los resultados del análisis comparativo y los planes de acción estratégicos aparecerán aquí una vez que inicies la comparación...")

    def update_status(self, text, color=None):
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color if color else "#FFD700"))
        if hasattr(self.main, 'update_status'):
            self.after(0, lambda: self.main.update_status(text, color))

    def browse_local_file(self, target):
        file_path = filedialog.askopenfilename(
            title="Seleccionar Video o Audio",
            filetypes=[
                ("Archivos multimedia", "*.mp4 *.mkv *.avi *.mov *.mp3 *.m4a *.wav *.ogg *.webm"),
                ("Todos los archivos", "*.*")
            ]
        )
        if file_path:
            file_path = os.path.abspath(file_path)
            if target == "my":
                self.entry_my_url.delete(0, "end")
                self.entry_my_url.insert(0, file_path)
            else:
                self.entry_ref_url.delete(0, "end")
                self.entry_ref_url.insert(0, file_path)

    # --- HILO DE ANÁLISIS DE VIDEO INDIVIDUAL ---
    def run_analyze_thread(self, target):
        url = self.entry_my_url.get().strip() if target == "my" else self.entry_ref_url.get().strip()
        if not url:
            self.update_status("⚠️ Introduce una URL o archivo local", "orange")
            return
            
        is_local = os.path.exists(url) and os.path.isfile(url)
        is_youtube = "youtube.com" in url or "youtu.be" in url
        
        if not is_local and not is_youtube:
            self.update_status("⚠️ Introduce una URL de YT o un archivo local válido", "orange")
            return
            
        if target == "my":
            if self.processing_my: return
            self.processing_my = True
            self.btn_my_analyze.configure(state="disabled", text="ESPERA...")
        else:
            if self.processing_ref: return
            self.processing_ref = True
            self.btn_ref_analyze.configure(state="disabled", text="ESPERA...")
            
        self.update_status(f"📥 PROCESANDO ({target.upper()})...", "#FFD700")
        
        groq_key = getattr(self.main, "groq_api_key", None)
        
        threading.Thread(
            target=self.analyze_video_flow,
            args=(url, target, groq_key),
            daemon=True
        ).start()

    def analyze_video_flow(self, url, target, groq_key):
        try:
            is_local = os.path.exists(url) and os.path.isfile(url)
            if is_local:
                audio_path = os.path.abspath(url)
                # Crear un identificador único combinando el nombre del archivo y un hash del path completo
                import hashlib
                path_hash = hashlib.md5(audio_path.encode('utf-8')).hexdigest()[:8]
                base_name = f"local_{path_hash}_{os.path.basename(audio_path)}"
                self.update_status(f"📂 Usando archivo local ({target.upper()})...", "#00FF66")
            else:
                # 1. Descargar audio
                self.update_status(f"🌐 Descargando audio del video ({target.upper()})...", "#FFD700")
                audio_path = download_youtube_audio(url, self.cache_dir, self.update_status)
                base_name = os.path.basename(audio_path)
            
            # Rutas de caché para transcripción
            trans_cache_path = os.path.join(self.cache_dir, f"{base_name}_transcription.json")
            txt_cache_path = os.path.join(self.cache_dir, f"{base_name}_transcription.txt")
            
            transcription = None
            if os.path.exists(trans_cache_path) and os.path.getsize(trans_cache_path) > 0:
                try:
                    self.update_status(f"♻️ Cargando transcripción de caché ({target.upper()})...", "#00FF66")
                    with open(trans_cache_path, "r", encoding="utf-8") as f:
                        transcription = json.load(f)
                except Exception as ex_read:
                    print(f"Error leyendo caché de transcripción: {ex_read}")
            
            if not transcription:
                # 2. Transcribir
                self.update_status(f"🎙️ Transcribiendo audio ({target.upper()})...", "#FFD700")
                transcription = transcribe_audio_benchmark(audio_path, groq_key, self.update_status)
                
                # Guardar caché en disco de inmediato
                try:
                    with open(trans_cache_path, "w", encoding="utf-8") as f:
                        json.dump(transcription, f, indent=4, ensure_ascii=False)
                    script_text_to_save = transcription.get("text", "").strip()
                    with open(txt_cache_path, "w", encoding="utf-8") as f:
                        f.write(script_text_to_save)
                    self.update_status(f"💾 Transcripción guardada en disco ({target.upper()}).", "#00E676")
                except Exception as ex_write:
                    print(f"Error escribiendo caché de transcripción: {ex_write}")
            
            # 3. Calcular métricas
            self.update_status(f"📊 Calculando métricas de ritmo...", "#FFD700")
            metrics = calculate_pacing_metrics(transcription)
            
            # Guion limpio y path de TXT absoluto
            script_text = transcription.get("text", "").strip()
            txt_path_abs = os.path.abspath(txt_cache_path)
            
            # Asegurar que el txt_cache_path exista y esté escrito
            if not os.path.exists(txt_path_abs) or os.path.getsize(txt_path_abs) == 0:
                try:
                    with open(txt_path_abs, "w", encoding="utf-8") as f:
                        f.write(script_text)
                except Exception as ex_write_txt:
                    print(f"Error escribiendo txt de transcripción: {ex_write_txt}")
            
            self.after(0, lambda: self.on_analyze_success(target, script_text, metrics, txt_path_abs))
        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda: self.on_analyze_error(target, str(e)))

    def on_analyze_success(self, target, script_text, metrics, txt_path):
        if target == "my":
            self.processing_my = False
            self.btn_my_analyze.configure(state="normal", text="📥 ANALIZAR")
            self.my_video_data = {"script": script_text, "metrics": metrics}
            self.my_txt_path = txt_path
            self.my_script_full = script_text
            
            # Actualizar interfaz
            self.txt_my_script.delete("0.0", "end")
            if len(script_text) > 15000:
                truncated_text = (
                    f"⚠️ [MOSTRANDO PREVIO DE 15,000 CARACTERES PARA EVITAR CONGELAMIENTO]\n"
                    f"La transcripción completa está guardada en:\n{txt_path}\n"
                    f"Usa el botón '📂 ABRIR TXT' para verla o editarla en el Bloc de Notas.\n\n"
                    f"{script_text[:15000]}\n\n"
                    f"... [Sigue en el archivo TXT] ..."
                )
                self.txt_my_script.insert("0.0", truncated_text)
            else:
                self.txt_my_script.insert("0.0", script_text)
                
            self.lbl_my_wpm.configure(text=f"WPM: {metrics['wpm']} ({metrics['pacing_desc']})", text_color=COLOR_SUCCESS)
            self.lbl_my_silences.configure(text=f"Silencios dramáticos: {metrics['silence_count']} (promedio {metrics['avg_silence_dur']}s)", text_color="white")
            self.lbl_my_duration.configure(text=f"Duración estimada: {metrics['total_duration']}s", text_color="white")
        else:
            self.processing_ref = False
            self.btn_ref_analyze.configure(state="normal", text="📥 ANALIZAR")
            self.ref_video_data = {"script": script_text, "metrics": metrics}
            self.ref_txt_path = txt_path
            self.ref_script_full = script_text
            
            # Actualizar interfaz
            self.txt_ref_script.delete("0.0", "end")
            if len(script_text) > 15000:
                truncated_text = (
                    f"⚠️ [MOSTRANDO PREVIO DE 15,000 CARACTERES PARA EVITAR CONGELAMIENTO]\n"
                    f"La transcripción completa está guardada en:\n{txt_path}\n"
                    f"Usa el botón '📂 ABRIR TXT' para verla o editarla en el Bloc de Notas.\n\n"
                    f"{script_text[:15000]}\n\n"
                    f"... [Sigue en el archivo TXT] ..."
                )
                self.txt_ref_script.insert("0.0", truncated_text)
            else:
                self.txt_ref_script.insert("0.0", script_text)
                
            self.lbl_ref_wpm.configure(text=f"WPM: {metrics['wpm']} ({metrics['pacing_desc']})", text_color=COLOR_SUCCESS)
            self.lbl_ref_silences.configure(text=f"Silencios dramáticos: {metrics['silence_count']} (promedio {metrics['avg_silence_dur']}s)", text_color="white")
            self.lbl_ref_duration.configure(text=f"Duración estimada: {metrics['total_duration']}s", text_color="white")
            
        self.update_status(f"✅ ANÁLISIS COMPLETADO ({target.upper()})", COLOR_SUCCESS)
        
        # Abrir el TXT de inmediato de forma asíncrona para que no interfiera en la UI
        if txt_path and os.path.exists(txt_path):
            try:
                threading.Thread(target=lambda: os.startfile(txt_path), daemon=True).start()
            except Exception as e:
                print(f"Error al abrir automáticamente el archivo TXT: {e}")

    def on_analyze_error(self, target, error_msg):
        if target == "my":
            self.processing_my = False
            self.btn_my_analyze.configure(state="normal", text="📥 ANALIZAR")
        else:
            self.processing_ref = False
            self.btn_ref_analyze.configure(state="normal", text="📥 ANALIZAR")
            
        self.update_status(f"❌ FALLO ({target.upper()}): {error_msg[:30]}", "red")
        
        import tkinter.messagebox as msgbox
        msgbox.showerror("Error de Análisis", f"No se pudo descargar o transcribir el video de YouTube ({target.upper()}).\nDetalle: {error_msg}")

    def open_my_txt(self):
        if self.my_txt_path and os.path.exists(self.my_txt_path):
            try:
                os.startfile(self.my_txt_path)
            except Exception as e:
                import tkinter.messagebox as msgbox
                msgbox.showerror("Error", f"No se pudo abrir el archivo TXT:\n{e}")
        else:
            import tkinter.messagebox as msgbox
            msgbox.showinfo("Información", "No hay ningún archivo TXT guardado para tu video.")

    def open_ref_txt(self):
        if self.ref_txt_path and os.path.exists(self.ref_txt_path):
            try:
                os.startfile(self.ref_txt_path)
            except Exception as e:
                import tkinter.messagebox as msgbox
                msgbox.showerror("Error", f"No se pudo abrir el archivo TXT:\n{e}")
        else:
            import tkinter.messagebox as msgbox
            msgbox.showinfo("Información", "No hay ningún archivo TXT guardado para el competidor.")

    # --- HILO DE COMPARACIÓN ---
    def run_comparison_thread(self):
        # Tomar guiones directos de los textboxes o archivos TXT correspondientes
        my_textbox_content = self.txt_my_script.get("0.0", "end").strip()
        ref_textbox_content = self.txt_ref_script.get("0.0", "end").strip()
        
        if not my_textbox_content or my_textbox_content.startswith("Los resultados"):
            self.update_status("⚠️ Introduce el guion de tu video primero", "orange")
            return
        if not ref_textbox_content:
            self.update_status("⚠️ Introduce el guion del competidor primero", "orange")
            return

        # Para mi video: si fue truncado, usar archivo .txt para leer cambios del Notepad
        if "⚠️ [MOSTRANDO PREVIO" in my_textbox_content and self.my_txt_path and os.path.exists(self.my_txt_path):
            try:
                with open(self.my_txt_path, "r", encoding="utf-8") as f:
                    my_script = f.read().strip()
            except Exception as e:
                print(f"Error leyendo my_txt_path: {e}")
                my_script = self.my_script_full if self.my_script_full else my_textbox_content
        else:
            my_script = my_textbox_content

        # Para el competidor: si fue truncado, usar archivo .txt
        if "⚠️ [MOSTRANDO PREVIO" in ref_textbox_content and self.ref_txt_path and os.path.exists(self.ref_txt_path):
            try:
                with open(self.ref_txt_path, "r", encoding="utf-8") as f:
                    ref_script = f.read().strip()
            except Exception as e:
                print(f"Error leyendo ref_txt_path: {e}")
                ref_script = self.ref_script_full if self.ref_script_full else ref_textbox_content
        else:
            ref_script = ref_textbox_content
            
        api_key = getattr(self.main, "google_api_key", "")
        provider = getattr(self.main, "llm_provider", "gemini")
        if provider == "groq":
            api_key = getattr(self.main, "groq_api_key", "")
            
        if not api_key:
            self.update_status("⚠️ Configura tu API Key global primero (icono ⚙️)", "orange")
            return
            
        self.comparing = True
        self.btn_compare.configure(state="disabled", text="ANALIZANDO ESTRATEGIA CON IA...")
        self.update_status("🧠 EVALUANDO COMPARATIVA CON INTELIGENCIA ARTIFICIAL...", "#FFD700")
        
        # Si las métricas no se calcularon por descarga, calculamos métricas sintéticas simples basadas en texto
        if not self.my_video_data["metrics"]:
            self.my_video_data["metrics"] = {"wpm": "Manual/Indefinido", "silence_count": "N/A", "total_duration": "N/A", "pacing_desc": "Manual"}
        if not self.ref_video_data["metrics"]:
            self.ref_video_data["metrics"] = {"wpm": "Manual/Indefinido", "silence_count": "N/A", "total_duration": "N/A", "pacing_desc": "Manual"}
            
        threading.Thread(
            target=self.compare_flow_bg,
            args=(my_script, self.my_video_data["metrics"], ref_script, self.ref_video_data["metrics"], api_key, provider),
            daemon=True
        ).start()

    def compare_flow_bg(self, my_script, my_metrics, ref_script, ref_metrics, api_key, provider):
        try:
            report = compare_narrative_ai(
                my_script=my_script,
                my_metrics=my_metrics,
                ref_script=ref_script,
                ref_metrics=ref_metrics,
                api_key=api_key,
                provider=provider
            )
            self.after(0, lambda: self.on_compare_success(report))
        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda: self.on_compare_error(str(e)))

    def on_compare_success(self, report):
        self.comparing = False
        self.btn_compare.configure(state="normal", text="⚡ COMPARAR GUIONES Y RITMO ⚡")
        
        self.txt_report.delete("0.0", "end")
        self.txt_report.insert("0.0", report)
        
        self.update_status("✨ COMPARATIVA GENERADA EXITOSAMENTE!", COLOR_SUCCESS)
        
        # Diálogo interactivo
        import tkinter.messagebox as msgbox
        msgbox.showinfo("Comparativa Completa", "La Inteligencia Artificial ha terminado de redactar el informe comparativo y tu estrategia de optimización viral.")

    def on_compare_error(self, error_msg):
        self.comparing = False
        self.btn_compare.configure(state="normal", text="⚡ COMPARAR GUIONES Y RITMO ⚡")
        self.update_status("❌ ERROR DE COMPARACIÓN DE IA", "red")
        
        import tkinter.messagebox as msgbox
        msgbox.showerror("Error de Comparación", f"La IA falló al redactar la comparativa.\nDetalle: {error_msg}")

    # --- STATE COMPATIBILITY ---
    def get_state(self):
        return {
            "my_url": self.entry_my_url.get().strip(),
            "ref_url": self.entry_ref_url.get().strip(),
            "my_script": self.txt_my_script.get("0.0", "end").strip(),
            "ref_script": self.txt_ref_script.get("0.0", "end").strip(),
            "report": self.txt_report.get("0.0", "end").strip(),
            "my_script_full": self.my_script_full,
            "ref_script_full": self.ref_script_full,
            "my_txt_path": self.my_txt_path,
            "ref_txt_path": self.ref_txt_path
        }

    def restore_state(self, state):
        if not state: return
        self.entry_my_url.delete(0, "end")
        self.entry_my_url.insert(0, state.get("my_url", ""))
        self.entry_ref_url.delete(0, "end")
        self.entry_ref_url.insert(0, state.get("ref_url", ""))
        
        self.my_script_full = state.get("my_script_full", "")
        self.ref_script_full = state.get("ref_script_full", "")
        self.my_txt_path = state.get("my_txt_path", "")
        self.ref_txt_path = state.get("ref_txt_path", "")
        
        self.txt_my_script.delete("0.0", "end")
        self.txt_my_script.insert("0.0", state.get("my_script", ""))
        self.txt_ref_script.delete("0.0", "end")
        self.txt_ref_script.insert("0.0", state.get("ref_script", ""))
        
        self.txt_report.delete("0.0", "end")
        self.txt_report.insert("0.0", state.get("report", ""))
