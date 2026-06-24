import os
import threading
import webbrowser
import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk
import urllib.request
import io
from PIL import Image

from modules.analytics_client import fetch_channel_videos, get_mock_channel_videos, has_valid_videos_cache

# --- PALETA DE COLORES ---
COLOR_BG = "#020202"
COLOR_PANEL = "#070707"
COLOR_ACCENT = "#FF0000"
COLOR_ACCENT_HOVER = "#CC0000"
COLOR_BORDER = "#1F1F1F"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_DIM = "#888888"
COLOR_SUCCESS = "#00FF66"

FONT_TITLE = ("Impact", 28)
FONT_BOLD = ("Inter", 12, "bold")
FONT_MAIN = ("Inter", 12)
FONT_MONO = ("Consolas", 11)

class VideosTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        
        self.main_window = main_window
        self.videos = []
        self.loading = False
        self.loaded_channel_name = None
        
        # Cabecera de la pestaña
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(10, 15))
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="LISTA DE VIDEOS", font=FONT_TITLE, text_color=COLOR_ACCENT)
        self.title_label.pack(side="left")
        
        # Botón de fórmula informativa
        self.btn_formula = ctk.CTkButton(
            self.header_frame,
            text="ⓘ Fórmula",
            font=FONT_BOLD,
            fg_color="transparent",
            hover_color=COLOR_PANEL,
            text_color=COLOR_SUCCESS,
            width=80,
            height=30,
            command=self.show_formula_info
        )
        self.btn_formula.pack(side="left", padx=10)
        
        # Selector de canal y controles
        self.selector_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.selector_frame.pack(side="right")
        
        ctk.CTkLabel(self.selector_frame, text="Canal:", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(side="left", padx=(5, 2))
        
        self.channel_names = [c["name"] for c in self.main_window.channels]
        initial_channel = self.main_window.active_channel_name
        if initial_channel not in self.channel_names:
            initial_channel = self.channel_names[0] if self.channel_names else ""
        self.selected_channel_name = tk.StringVar(value=initial_channel)
        
        self.dropdown_channel = ctk.CTkOptionMenu(
            self.selector_frame,
            variable=self.selected_channel_name,
            values=self.channel_names if self.channel_names else ["Sin canales"],
            fg_color=COLOR_PANEL,
            button_color=COLOR_BORDER,
            button_hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXT_MAIN,
            font=FONT_MAIN,
            width=140,
            command=self.on_channel_changed
        )
        self.dropdown_channel.pack(side="left", padx=5)

        # Dropdown de Ordenar
        ctk.CTkLabel(self.selector_frame, text="Ordenar:", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(side="left", padx=(10, 2))
        
        self.sort_option = tk.StringVar(value="Fecha (Recientes)")
        self.dropdown_sort = ctk.CTkOptionMenu(
            self.selector_frame,
            variable=self.sort_option,
            values=["Fecha (Recientes)", "Título (A-Z)", "Puntuación (Mayor a Menor)"],
            fg_color=COLOR_PANEL,
            button_color=COLOR_BORDER,
            button_hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXT_MAIN,
            font=FONT_MAIN,
            width=160,
            command=self.on_sort_changed
        )
        self.dropdown_sort.pack(side="left", padx=5)
        
        self.btn_load_api = ctk.CTkButton(
            self.selector_frame,
            text="ACTUALIZAR API",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_BOLD,
            width=110,
            command=lambda: self.authenticate_and_load_videos(force_reload=True)
        )
        self.btn_load_api.pack(side="left", padx=5)

        self.btn_mock = ctk.CTkButton(
            self.selector_frame,
            text="SIMULAR VIDEOS",
            fg_color=COLOR_BORDER,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_DIM,
            font=FONT_BOLD,
            width=110,
            command=self.load_mock_videos
        )
        self.btn_mock.pack(side="left", padx=5)

        # Segmented Button para filtrar por tipo
        self.segment_var = tk.StringVar(value="Shorts")
        self.segmented_button = ctk.CTkSegmentedButton(
            self,
            values=["Shorts", "Videos Largos", "Directos"],
            variable=self.segment_var,
            command=self.on_segment_changed,
            fg_color=COLOR_PANEL,
            selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_BOLD,
            height=32
        )
        self.segmented_button.pack(fill="x", padx=5, pady=(5, 10))

        # Panel principal scrollable para la lista
        self.list_panel = ctk.CTkScrollableFrame(
            self,
            fg_color=COLOR_PANEL,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=8,
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT
        )
        self.list_panel.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Inicializar ejecutor de hilos para cargar portadas en paralelo de forma controlada (máx. 2 hilos concurrentes)
        from concurrent.futures import ThreadPoolExecutor
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=2)
        
        # Cargar mensaje inicial si no hay canales configurados
        if not self.main_window.channels:
            self.show_no_channels_message()

    def on_channel_changed(self, value):
        self.main_window.active_channel_name = value
        self.authenticate_and_load_videos(force_reload=True)

    def on_segment_changed(self, value):
        self.render_videos_list()

    def show_no_channels_message(self):
        # Limpiar panel
        for w in self.list_panel.winfo_children():
            w.destroy()
            
        no_channels_label = ctk.CTkLabel(
            self.list_panel,
            text="No hay canales registrados.\nPor favor, ve a la pantalla de Ajustes de Canales para agregar uno.",
            font=FONT_BOLD,
            text_color=COLOR_TEXT_DIM
        )
        no_channels_label.pack(expand=True, pady=100)

    def load_mock_videos(self):
        """Carga videos simulados en la UI."""
        channel_name = self.selected_channel_name.get()
        if not channel_name or channel_name == "Sin canales":
            channel_name = "Canal de Simulación"
            
        self.videos = get_mock_channel_videos(channel_name)
        self.loaded_channel_name = channel_name + " (MOCK)"
        self.sort_videos_list()
        self.render_videos_list()

    def authenticate_and_load_videos(self, force_reload=False):
        """Autentica por OAuth y descarga el listado de videos reales de YouTube."""
        channel_name = self.selected_channel_name.get()
        
        # Si no es carga forzada, y ya están cargados los videos de este canal, no hacer nada
        if not force_reload and self.loaded_channel_name == channel_name and self.videos:
            print(f"VideosTab: El canal '{channel_name}' ya está cargado en memoria. Saltando recarga API.")
            return

        channel_info = next((c for c in self.main_window.channels if c["name"] == channel_name), None)
        
        if not channel_info:
            messagebox.showwarning("Error de canal", "Selecciona un canal válido para cargar videos.")
            return
            
        client_secrets = channel_info.get("credential_file", "")
        if not client_secrets or not os.path.exists(client_secrets):
            messagebox.showwarning(
                "Credenciales faltantes",
                "El canal seleccionado no tiene un archivo client_secrets.json local configurado.\n"
                "Ve a 'Ajustes de Canales' para configurarlo."
            )
            return
            
        # Generar un nombre único de token para este canal
        safe_name = "".join([c if c.isalnum() else "_" for c in channel_name])
        token_path = os.path.join("config", f"token_{safe_name}.pickle")
        
        is_cache = not force_reload and has_valid_videos_cache(channel_name)
        self.show_loading_screen(is_cache=is_cache)
        
        def run_load():
            try:
                self.videos = fetch_channel_videos(client_secrets, token_path, force_reload=force_reload)
                self.main_window.after(0, self.on_api_load_success)
            except Exception as e:
                err_msg = str(e)
                self.main_window.after(0, lambda msg=err_msg: self.handle_load_error(msg))
                
        threading.Thread(target=run_load, daemon=True).start()

    def on_api_load_success(self):
        self.loaded_channel_name = self.selected_channel_name.get()
        self.sort_videos_list()
        self.render_videos_list()

    def sync_active_channel(self):
        """Sincroniza la pestaña con el canal activo de MainWindow."""
        active = self.main_window.active_channel_name
        if active and active in self.channel_names:
            if self.selected_channel_name.get() != active:
                self.selected_channel_name.set(active)
            self.authenticate_and_load_videos(force_reload=False)
        elif not active:
            self.show_no_channels_message()

    def refresh_channel_list(self):
        """Actualiza dinámicamente la lista de canales del dropdown."""
        self.channel_names = [c["name"] for c in self.main_window.channels]
        current = self.selected_channel_name.get()
        if current not in self.channel_names:
            current = self.channel_names[0] if self.channel_names else "Sin canales"
            self.selected_channel_name.set(current)
            self.loaded_channel_name = None
            self.videos = []
        
        self.dropdown_channel.configure(values=self.channel_names if self.channel_names else ["Sin canales"])
        if not self.main_window.channels:
            self.show_no_channels_message()

    def on_sort_changed(self, value):
        self.sort_videos_list()
        self.render_videos_list()

    def sort_videos_list(self):
        import datetime
        val = self.sort_option.get()
        if not self.videos:
            return
            
        if val == "Fecha (Recientes)":
            def get_date_key(x):
                try:
                    return datetime.datetime.strptime(x["date"], "%d/%m/%Y")
                except:
                    return datetime.datetime.min
            self.videos = sorted(self.videos, key=get_date_key, reverse=True)
        elif val == "Título (A-Z)":
            self.videos = sorted(self.videos, key=lambda x: x["title"].lower())
        elif val == "Puntuación (Mayor a Menor)":
            self.videos = sorted(self.videos, key=lambda x: x.get("score", 0), reverse=True)

    def show_formula_info(self):
        # Crear ventana flotante (Toplevel)
        popup = ctk.CTkToplevel(self)
        popup.title("FÓRMULA DETALLADA DEL SCORE")
        popup.geometry("680x700")
        popup.configure(fg_color=COLOR_BG)
        popup.resizable(False, False)
        popup.transient(self) # Mantener al frente
        popup.grab_set() # Bloquear interacción con ventana padre
        
        # Centrar la ventana emergente
        popup.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 680) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 700) // 2
        popup.geometry(f"+{x}+{y}")
        
        # Título principal
        title_label = ctk.CTkLabel(
            popup, 
            text="FÓRMULA DE PUNTUACIÓN DE VIDEOS", 
            font=("Impact", 24), 
            text_color=COLOR_ACCENT
        )
        title_label.pack(pady=(20, 5))

        subtitle_label = ctk.CTkLabel(
            popup, 
            text="Cómo se calcula el rendimiento de tus Shorts, Videos Largos y Directos (0 a 100 pts)", 
            font=FONT_MAIN, 
            text_color=COLOR_TEXT_DIM
        )
        subtitle_label.pack(pady=(0, 15))
        
        # Contenedor con scroll
        txt_frame = ctk.CTkScrollableFrame(
            popup, 
            fg_color=COLOR_PANEL, 
            border_color=COLOR_BORDER, 
            border_width=1,
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT
        )
        txt_frame.pack(fill="both", expand=True, padx=25, pady=(0, 15))
        
        # Intro
        intro_text = (
            "El sistema evalúa cada video de manera dinámica adaptándose al formato:\n\n"
            "• Si el video es muy nuevo y los datos de retención aún no se han procesado en la API de YouTube Analytics (suele tardar 48-72h), el score se calcula basándose al 100% en la tasa de interacción para no penalizarlo.\n"
            "• Una vez que los datos de retención están listos, se aplica la fórmula consolidada de tres pilares adaptada a cada formato (Shorts, Videos Largos o Directos)."
        )
        intro_lbl = ctk.CTkLabel(
            txt_frame, 
            text=intro_text, 
            font=FONT_MAIN, 
            text_color=COLOR_TEXT_MAIN, 
            justify="left", 
            anchor="w",
            wraplength=580
        )
        intro_lbl.pack(fill="x", padx=10, pady=(10, 15))
        
        # Función auxiliar para crear tarjetas de pilares
        def create_pilar_card(parent, title_text, weight_text, desc_text, items):
            card = ctk.CTkFrame(
                parent, 
                fg_color=COLOR_BG, 
                border_color=COLOR_BORDER, 
                border_width=1, 
                corner_radius=8
            )
            card.pack(fill="x", pady=8, padx=5)
            
            # Cabecera de la tarjeta
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=15, pady=(12, 8))
            
            lbl_title = ctk.CTkLabel(
                header, 
                text=title_text, 
                font=FONT_BOLD, 
                text_color=COLOR_SUCCESS, 
                anchor="w"
            )
            lbl_title.pack(side="left")
            
            # Badge de peso
            badge = ctk.CTkFrame(
                header, 
                fg_color=COLOR_PANEL, 
                border_color=COLOR_SUCCESS, 
                border_width=1, 
                corner_radius=4
            )
            badge.pack(side="right")
            
            lbl_weight = ctk.CTkLabel(
                badge, 
                text=f"PESO: {weight_text}", 
                font=("Inter", 10, "bold"), 
                text_color=COLOR_SUCCESS,
                padx=8,
                pady=2
            )
            lbl_weight.pack()
            
            # Descripción
            lbl_desc = ctk.CTkLabel(
                card, 
                text=desc_text, 
                font=FONT_MAIN, 
                text_color=COLOR_TEXT_MAIN, 
                justify="left", 
                anchor="w",
                wraplength=530
            )
            lbl_desc.pack(fill="x", padx=15, pady=(0, 10))
            
            # Escala / Puntuaciones
            items_frame = ctk.CTkFrame(card, fg_color="transparent")
            items_frame.pack(fill="x", padx=15, pady=(0, 12))
            
            for key, val in items:
                row = ctk.CTkFrame(items_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)
                
                bullet = ctk.CTkLabel(
                    row, 
                    text="•", 
                    font=("Inter", 12, "bold"), 
                    text_color=COLOR_ACCENT, 
                    width=15, 
                    anchor="w"
                )
                bullet.pack(side="left")
                
                lbl_key = ctk.CTkLabel(
                    row, 
                    text=f"{key}:", 
                    font=FONT_BOLD, 
                    text_color=COLOR_TEXT_MAIN, 
                    anchor="w"
                )
                lbl_key.pack(side="left", padx=(0, 5))
                
                lbl_val = ctk.CTkLabel(
                    row, 
                    text=val, 
                    font=FONT_MAIN, 
                    text_color=COLOR_TEXT_DIM, 
                    anchor="w"
                )
                lbl_val.pack(side="left")
        
        # Pilar 1
        p1_items = [
            ("Shorts (AVP % / bucle)", ">=100% (Exc), 70-99% (B), 50-69% (Reg), <50% (Bajo)"),
            ("Videos Largos (AVP %)", ">=50% (Exc), 40-49% (B), 25-39% (Reg), <25% (Bajo)"),
            ("Directos (Permanencia)", ">=10m (Exc), 5-9m (B), 2-4m (Reg), <2m (Bajo)")
        ]
        create_pilar_card(
            txt_frame,
            "1. RETENCIÓN DE AUDIENCIA (AVP / TIEMPO ABSOLUTO)",
            "55%",
            "Mide el nivel de atención promedio. Los Shorts/Videos usan el porcentaje de retención (AVP). Los Directos, dada su larga duración, se evalúan por minutos de permanencia absoluta.",
            p1_items
        )
        
        # Pilar 2
        p2_items = [
            ("Likes / Comentarios / Compartidos", "Ponderación (1x / 5x / 10x)"),
            ("Fórmula de Ratio", "[Likes + 5×Comentarios + 10×Compartidos] ÷ (Vistas + 50)"),
            ("Compensación por Vistas", "La tasa se escala según el volumen de vistas para premiar la viralidad"),
            ("Ratios de Escalado", ">=12% (100 pts), 8-11% (80-100 pts), 4-7% (50-80 pts)")
        ]
        create_pilar_card(
            txt_frame,
            "2. COMPROMISO E INTERACCIÓN PONDERADA",
            "45%",
            "Evalúa la interacción del público. Dar 'Like' es simple, pero comentar o compartir requiere un esfuerzo real, por lo que tienen un peso mayor. La tasa se suaviza para videos pequeños y se escala para videos virales.",
            p2_items
        )
        
        # Pilar 3
        p3_items = [
            (">= 3 Suscriptores por 1k vistas", "Otorga el bonus máximo (+10 pts extra)"),
            ("1 - 2 Suscriptores por 1k vistas", "Otorga entre +3 y +9 pts extra de bonus"),
            ("< 1 Suscriptor por 1k vistas", "Otorga entre 0 y +3 pts extra de bonus")
        ]
        create_pilar_card(
            txt_frame,
            "3. CONVERSIÓN DE SUSCRIPTORES (BONUS)",
            "EXTRA (+10 PTS MAX)",
            "Mide el impacto directo del Short para hacer crecer tu comunidad. Se calcula en función de la cantidad de nuevos suscriptores ganados por cada 1,000 visualizaciones, sumando puntos extra directamente al puntaje base (capado en 100 pts).",
            p3_items
        )
        
        # Pilar 4
        p4_items = [
            (">= 10,000 vistas", "Otorga entre +18.0 y +20.0 pts de reach bonus"),
            ("1,000 - 9,999 vistas", "Otorga entre +13.5 y +18.0 pts de reach bonus"),
            ("100 - 999 vistas", "Otorga entre +9.0 y +13.5 pts de reach bonus"),
            ("< 100 vistas", "Otorga menos de +9.0 pts de reach bonus")
        ]
        create_pilar_card(
            txt_frame,
            "4. ALCANCE ABSOLUTO (REACH BONUS)",
            "EXTRA (+20 PTS MAX)",
            "Mide el impacto absoluto y la viralidad de tu video. Se calcula de forma logarítmica según el volumen total de vistas, dando un impulso justo y representativo a los contenidos que logran un alcance masivo.",
            p4_items
        )
        
        # Tarjeta de Rangos Competitivos
        ranges_card = ctk.CTkFrame(
            txt_frame, 
            fg_color=COLOR_BG, 
            border_color=COLOR_BORDER, 
            border_width=1, 
            corner_radius=8
        )
        ranges_card.pack(fill="x", pady=8, padx=5)
        
        lbl_ranges_title = ctk.CTkLabel(
            ranges_card, 
            text="ESCALA DE RANGOS COMPETITIVOS", 
            font=FONT_BOLD, 
            text_color=COLOR_ACCENT, 
            anchor="w"
        )
        lbl_ranges_title.pack(fill="x", padx=15, pady=(12, 8))
        
        lbl_ranges_desc = ctk.CTkLabel(
            ranges_card, 
            text="El score final consolidado asigna un rango competitivo al video corto para evaluar su desempeño general:", 
            font=FONT_MAIN, 
            text_color=COLOR_TEXT_MAIN, 
            justify="left", 
            anchor="w",
            wraplength=530
        )
        lbl_ranges_desc.pack(fill="x", padx=15, pady=(0, 10))
        
        # Tabla de Rangos
        ranges = [
            ("S+", "95 - 100", "#FF0055", "Éxito legendario y viralidad explosiva."),
            ("S", "90 - 94", "#FF0000", "Rendimiento excepcional, excelente alcance."),
            ("A", "75 - 89", "#00FF66", "Rendimiento muy sobresaliente."),
            ("B", "60 - 74", "#0099FF", "Desempeño estable con buena interacción."),
            ("C", "45 - 59", "#FFCC00", "Rendimiento regular. Se sugiere mejorar el gancho."),
            ("D", "0 - 44", "#555555", "Rendimiento bajo. Requiere optimización de contenido.")
        ]
        
        ranges_table = ctk.CTkFrame(ranges_card, fg_color="transparent")
        ranges_table.pack(fill="x", padx=15, pady=(0, 15))
        
        for rank, pts, color, desc in ranges:
            row = ctk.CTkFrame(ranges_table, fg_color="transparent")
            row.pack(fill="x", pady=4)
            
            # Badge de Rango
            badge_frame = ctk.CTkFrame(
                row, 
                fg_color=COLOR_PANEL, 
                border_color=color, 
                border_width=1, 
                corner_radius=4,
                width=55,
                height=26
            )
            badge_frame.pack(side="left")
            badge_frame.pack_propagate(False)
            
            badge_lbl = ctk.CTkLabel(
                badge_frame, 
                text=rank, 
                font=("Impact", 12), 
                text_color=color
            )
            badge_lbl.pack(expand=True)
            
            # Puntos
            pts_lbl = ctk.CTkLabel(
                row, 
                text=f"[{pts} pts]", 
                font=FONT_BOLD, 
                text_color=COLOR_TEXT_MAIN,
                width=80,
                anchor="w"
            )
            pts_lbl.pack(side="left", padx=10)
            
            # Descripción
            desc_lbl = ctk.CTkLabel(
                row, 
                text=desc, 
                font=FONT_MAIN, 
                text_color=COLOR_TEXT_DIM,
                anchor="w",
                justify="left",
                wraplength=400
            )
            desc_lbl.pack(side="left", fill="x", expand=True)

        # Botón Cerrar
        btn_close = ctk.CTkButton(
            popup,
            text="ENTENDIDO",
            fg_color=COLOR_BORDER,
            hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_BOLD,
            width=180,
            height=38,
            command=popup.destroy
        )
        btn_close.pack(pady=15)

    def show_loading_screen(self, is_cache=False):
        for w in self.list_panel.winfo_children():
            w.destroy()
            
        msg = "Cargando desde caché local..." if is_cache else "Cargando videos de YouTube API (Esperando navegador si es necesario)..."
        
        loading_label = ctk.CTkLabel(
            self.list_panel,
            text=msg,
            font=FONT_BOLD,
            text_color=COLOR_ACCENT
        )
        loading_label.pack(expand=True, pady=100)

    def handle_load_error(self, err_msg):
        if messagebox.askyesno("Error de Carga", f"No se pudieron cargar los videos desde YouTube:\n\n{err_msg}\n\n¿Deseas cargar videos de simulación en su lugar?"):
            self.load_mock_videos()
        else:
            self.render_videos_list()

    def render_videos_list(self):
        """Muestra la lista de videos en la UI filtrada por el tipo seleccionado."""
        for w in self.list_panel.winfo_children():
            w.destroy()
            
        if not self.videos:
            empty_label = ctk.CTkLabel(
                self.list_panel,
                text="No se encontraron videos para este canal.",
                font=FONT_MAIN,
                text_color=COLOR_TEXT_DIM
            )
            empty_label.pack(pady=50)
            return

        # Filtrar videos por el tipo correspondiente al segmento seleccionado
        selected_segment = self.segment_var.get().lower()
        # mapeo: "shorts" -> "shorts", "videos largos" -> "long", "directos" -> "live"
        type_map = {
            "shorts": "shorts",
            "videos largos": "long",
            "directos": "live"
        }
        target_type = type_map.get(selected_segment, "shorts")
        
        filtered_videos = []
        for v in self.videos:
            v_type = v.get("type")
            if not v_type:
                # Fallback retrocompatible
                vid_title = v.get("title", "").lower()
                duration = v.get("duration", 60)
                v_type = "shorts" if ("#shorts" in vid_title or (duration is not None and duration <= 60)) else "long"
            if v_type == target_type:
                filtered_videos.append(v)
                
        if not filtered_videos:
            segment_name = self.segment_var.get()
            empty_label = ctk.CTkLabel(
                self.list_panel,
                text=f"No se encontraron {segment_name.lower()} para este canal.",
                font=FONT_MAIN,
                text_color=COLOR_TEXT_DIM
            )
            empty_label.pack(pady=50)
            return
            
        for idx, video in enumerate(filtered_videos[:50], start=1):
            card = ctk.CTkFrame(self.list_panel, fg_color=COLOR_BG, border_color=COLOR_BORDER, border_width=1, corner_radius=6)
            card.pack(fill="x", padx=10, pady=5)
            
            # Número / Índice de orden a la izquierda
            idx_label = ctk.CTkLabel(
                card, 
                text=f"#{idx}", 
                font=("Impact", 16), 
                text_color=COLOR_TEXT_DIM, 
                width=40,
                anchor="center"
            )
            idx_label.pack(side="left", padx=(10, 2), pady=10)
            
            # Miniatura / Ícono
            thumb_frame = ctk.CTkFrame(card, fg_color=COLOR_PANEL, width=80, height=50, corner_radius=4)
            thumb_frame.pack(side="left", padx=5, pady=10)
            thumb_frame.pack_propagate(False)
            
            # Dibujar un triángulo rojo de play ▶ en el centro del frame de miniatura
            play_label = ctk.CTkLabel(thumb_frame, text="▶", font=("Inter", 18, "bold"), text_color=COLOR_ACCENT)
            play_label.pack(expand=True)
            
            # Carga asíncrona de la portada real
            thumbnail_url = video.get("thumbnail", "")
            if thumbnail_url:
                self.load_thumbnail_async(thumbnail_url, thumb_frame, play_label)
            
            # Texto explicativo (Título, Fecha y Vistas)
            text_frame = ctk.CTkFrame(card, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            
            title_label = ctk.CTkLabel(
                text_frame, 
                text=video["title"], 
                font=FONT_BOLD, 
                text_color=COLOR_TEXT_MAIN,
                anchor="w",
                justify="left",
                wraplength=450
            )
            title_label.pack(anchor="w")
            
            views_count = video.get("views", 0)
            date_label = ctk.CTkLabel(
                text_frame, 
                text=f"Publicado: {video['date']}  •  {views_count:,} vistas", 
                font=FONT_MAIN, 
                text_color=COLOR_TEXT_DIM,
                anchor="w"
            )
            date_label.pack(anchor="w", pady=(2, 0))
            
            # Contenedor de Rango y Acción en la derecha
            right_frame = ctk.CTkFrame(card, fg_color="transparent")
            right_frame.pack(side="right", padx=15, pady=10)
            
            # Badge de Rango (Estilo LoL / Rango Competitivo)
            rank_text = video.get("rank", "D")
            rank_color = video.get("rank_color", "#555555")
            score = video.get("score", 0)
            
            badge_frame = ctk.CTkFrame(
                right_frame, 
                fg_color=COLOR_PANEL, 
                border_color=rank_color, 
                border_width=1.5, 
                corner_radius=4,
                width=65,
                height=32
            )
            badge_frame.pack(side="left", padx=(0, 15))
            badge_frame.pack_propagate(False)
            
            rank_label = ctk.CTkLabel(
                badge_frame, 
                text=rank_text, 
                font=("Impact", 16), 
                text_color=rank_color
            )
            rank_label.pack(side="left", fill="both", expand=True, padx=(4, 0))
            
            score_label = ctk.CTkLabel(
                badge_frame, 
                text=f"{score}", 
                font=FONT_BOLD, 
                text_color=COLOR_TEXT_MAIN
            )
            score_label.pack(side="right", fill="both", expand=True, padx=(0, 4))
            
            # Botón Ver Video
            video_url = video["url"]
            btn_watch = ctk.CTkButton(
                right_frame,
                text="VER VIDEO",
                fg_color=COLOR_BORDER,
                hover_color=COLOR_ACCENT,
                text_color=COLOR_TEXT_MAIN,
                font=FONT_BOLD,
                width=90,
                height=32,
                command=lambda url=video_url: webbrowser.open(url)
            )
            btn_watch.pack(side="right")
            
            # Botón Detalles
            btn_details = ctk.CTkButton(
                right_frame,
                text="DETALLES",
                fg_color=COLOR_BORDER,
                hover_color=COLOR_SUCCESS,
                text_color=COLOR_TEXT_MAIN,
                font=FONT_BOLD,
                width=90,
                height=32,
                command=lambda v=video: self.show_video_details_popup(v)
            )
            btn_details.pack(side="right", padx=(0, 8))

    def load_thumbnail_async(self, url, parent_frame, placeholder_label):
        import hashlib
        
        # Crear directorios de caché si no existen
        cache_dir = os.path.join("config", "cache", "thumbnails")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Generar hash de la URL para archivo de caché único
        h = hashlib.md5(url.encode('utf-8')).hexdigest()
        ext = "jpg"
        if ".png" in url.lower():
            ext = "png"
        elif ".webp" in url.lower():
            ext = "webp"
        cache_path = os.path.join(cache_dir, f"{h}.{ext}")
        
        def worker():
            try:
                # 1. Comprobar si existe la imagen en caché local
                if os.path.exists(cache_path):
                    try:
                        raw_img = Image.open(cache_path)
                        raw_img.load()  # Forzar carga de píxeles antes de cerrar el archivo
                        self.main_window.after(0, lambda: self.set_thumbnail_image(parent_frame, placeholder_label, raw_img))
                        return
                    except Exception as ex:
                        # Si está corrupta la borramos
                        print(f"Caché corrupta eliminada: {ex}")
                        try:
                            os.remove(cache_path)
                        except:
                            pass
                
                # 2. Descargar si no está en caché
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    img_data = response.read()
                
                # 3. Guardar en caché local
                try:
                    with open(cache_path, "wb") as f:
                        f.write(img_data)
                except Exception as ex:
                    print(f"Error escribiendo caché de portada: {ex}")
                
                raw_img = Image.open(io.BytesIO(img_data))
                raw_img.load()
                self.main_window.after(0, lambda: self.set_thumbnail_image(parent_frame, placeholder_label, raw_img))
            except Exception as e:
                # Silencioso
                pass
                
        self.thumbnail_executor.submit(worker)

    def set_thumbnail_image(self, parent_frame, placeholder_label, raw_img):
        try:
            if not parent_frame.winfo_exists():
                return
            if placeholder_label.winfo_exists():
                placeholder_label.destroy()
                
            # Crear y empaquetar la imagen
            ctk_img = ctk.CTkImage(light_image=raw_img, dark_image=raw_img, size=(80, 50))
            img_label = ctk.CTkLabel(parent_frame, image=ctk_img, text="")
            img_label.image = ctk_img  # Mantener referencia
            img_label.pack(fill="both", expand=True)
        except Exception as e:
            print(f"Error al asignar miniatura en UI: {e}")

    def update_channels(self):
        """Actualiza la lista de canales del dropdown."""
        self.channel_names = [c["name"] for c in self.main_window.channels]
        self.dropdown_channel.configure(values=self.channel_names if self.channel_names else ["Sin canales"])
        if self.channel_names:
            if self.selected_channel_name.get() not in self.channel_names:
                new_active = self.main_window.active_channel_name
                if new_active not in self.channel_names:
                    new_active = self.channel_names[0]
                self.selected_channel_name.set(new_active)
                self.load_mock_videos()
        else:
            self.selected_channel_name.set("")
            self.show_no_channels_message()

    def show_video_details_popup(self, video):
        # Crear ventana flotante (Toplevel)
        popup = ctk.CTkToplevel(self)
        popup.title("DETALLES Y TRANSCRIPCIÓN DEL VIDEO")
        popup.geometry("700x700")
        popup.configure(fg_color=COLOR_BG)
        popup.resizable(False, False)
        popup.transient(self) # Mantener al frente
        popup.grab_set() # Bloquear interacción con ventana padre
        
        # Centrar la ventana emergente
        popup.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 700) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 700) // 2
        popup.geometry(f"+{x}+{y}")
        
        # Título del video
        title_label = ctk.CTkLabel(
            popup, 
            text=video.get("title", "Sin título"), 
            font=FONT_BOLD, 
            text_color=COLOR_ACCENT,
            justify="left",
            anchor="w",
            wraplength=650
        )
        title_label.pack(pady=(20, 10), padx=25, fill="x")
        
        # Panel de Metadatos Rápidos
        meta_frame = ctk.CTkFrame(popup, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=6)
        meta_frame.pack(fill="x", padx=25, pady=(0, 15))
        
        # Stats en fila
        views = video.get("views", 0)
        date = video.get("date", "Desconocida")
        v_type = video.get("type", "shorts").upper()
        rank = video.get("rank", "D")
        rank_color = video.get("rank_color", "#555555")
        score = video.get("score", 0)
        
        lbl_info = ctk.CTkLabel(
            meta_frame,
            text=f"Publicado: {date}   |   Vistas: {views:,}   |   Tipo: {v_type}   |   Puntaje: {score} ({rank})",
            font=FONT_MAIN,
            text_color=COLOR_TEXT_MAIN
        )
        lbl_info.pack(side="left", padx=15, pady=8)
        
        # Badge de rango en el meta
        badge = ctk.CTkFrame(meta_frame, fg_color=COLOR_BG, border_color=rank_color, border_width=1, corner_radius=4)
        badge.pack(side="right", padx=15, pady=8)
        ctk.CTkLabel(badge, text=rank, font=("Impact", 14), text_color=rank_color, padx=8).pack()
        
        # Contenedor principal con scroll para el contenido detallado
        content_frame = ctk.CTkScrollableFrame(
            popup, 
            fg_color=COLOR_PANEL, 
            border_color=COLOR_BORDER, 
            border_width=1,
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT
        )
        content_frame.pack(fill="both", expand=True, padx=25, pady=(0, 20))
        
        # 1. Sección de Etiquetas (Tags)
        tags_title = ctk.CTkLabel(content_frame, text="ETIQUETAS (TAGS)", font=FONT_BOLD, text_color=COLOR_SUCCESS, anchor="w")
        tags_title.pack(fill="x", padx=10, pady=(10, 5))
        
        tags = video.get("tags", [])
        if tags:
            tags_container = ctk.CTkFrame(content_frame, fg_color="transparent")
            tags_container.pack(fill="x", padx=10, pady=(0, 15))
            
            tags_str = "   #".join(tags)
            if not tags_str.startswith("#"):
                tags_str = "#" + tags_str
            lbl_tags = ctk.CTkLabel(
                tags_container,
                text=tags_str,
                font=FONT_MAIN,
                text_color=COLOR_TEXT_DIM,
                justify="left",
                anchor="w",
                wraplength=600
            )
            lbl_tags.pack(fill="x")
        else:
            lbl_no_tags = ctk.CTkLabel(content_frame, text="[Sin etiquetas asociadas]", font=FONT_MAIN, text_color=COLOR_TEXT_DIM, anchor="w")
            lbl_no_tags.pack(fill="x", padx=10, pady=(0, 15))
            
        # 2. Sección de Descripción
        desc_title = ctk.CTkLabel(content_frame, text="DESCRIPCIÓN COMPLETA", font=FONT_BOLD, text_color=COLOR_SUCCESS, anchor="w")
        desc_title.pack(fill="x", padx=10, pady=(0, 5))
        
        desc_text = video.get("description", "")
        if not desc_text:
            desc_text = "[Sin descripción disponible]"
            
        desc_box = ctk.CTkTextbox(
            content_frame,
            height=120,
            fg_color=COLOR_BG,
            border_color=COLOR_BORDER,
            border_width=1,
            font=FONT_MAIN,
            text_color=COLOR_TEXT_MAIN,
            corner_radius=6
        )
        desc_box.pack(fill="x", padx=10, pady=(0, 20))
        desc_box.insert("0.0", desc_text)
        desc_box.configure(state="disabled")
        
        # 3. Sección de Transcripción
        trans_title = ctk.CTkLabel(content_frame, text="TRANSCRIPCIÓN DEL AUDIO (NARRACIÓN)", font=FONT_BOLD, text_color=COLOR_SUCCESS, anchor="w")
        trans_title.pack(fill="x", padx=10, pady=(0, 5))
        
        trans_box = ctk.CTkTextbox(
            content_frame,
            height=200,
            fg_color=COLOR_BG,
            border_color=COLOR_BORDER,
            border_width=1,
            font=FONT_MAIN,
            text_color=COLOR_TEXT_MAIN,
            corner_radius=6
        )
        trans_box.pack(fill="x", padx=10, pady=(0, 10))
        trans_box.insert("0.0", "Cargando transcripción de audio desde YouTube... Por favor, espera.")
        trans_box.configure(state="disabled")
        
        # Hilo de fondo para cargar la transcripción sin congelar el popup
        def load_transcript_worker():
            try:
                from modules.analytics_client import fetch_video_transcript
                video_id = video.get("video_id")
                transcript = fetch_video_transcript(video_id)
                
                # Actualizar la UI de manera segura en el hilo principal
                if popup.winfo_exists():
                    self.main_window.after(0, lambda: self.update_transcript_ui(popup, trans_box, transcript))
            except Exception as e:
                err_msg = f"[Error en cargador de transcripción: {e}]"
                if popup.winfo_exists():
                    self.main_window.after(0, lambda: self.update_transcript_ui(popup, trans_box, err_msg))
                    
        import threading
        threading.Thread(target=load_transcript_worker, daemon=True).start()
        
    def update_transcript_ui(self, popup, textbox, text):
        try:
            if not popup.winfo_exists() or not textbox.winfo_exists():
                return
            textbox.configure(state="normal")
            textbox.delete("0.0", "end")
            textbox.insert("0.0", text)
            textbox.configure(state="disabled")
        except Exception as e:
            print(f"Error al actualizar la transcripción en la UI: {e}")
