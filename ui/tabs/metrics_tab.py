import os
import threading
import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk

# Intentar importar matplotlib para gráficos avanzados
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from modules.analytics_client import fetch_channel_data_and_analytics, get_mock_channel_analytics, has_valid_metrics_cache

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

class MetricsTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        
        self.main_window = main_window
        self.current_data = None
        self.loading = False
        self.loaded_channel_name = None
        
        # Cabecera de la sección
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(10, 15))
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="MÉTRICAS AVANZADAS", font=FONT_TITLE, text_color=COLOR_ACCENT)
        self.title_label.pack(side="left")
        
        # Selector de canal
        self.selector_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.selector_frame.pack(side="right")
        
        ctk.CTkLabel(self.selector_frame, text="Canal:", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(side="left", padx=5)
        
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
            width=180,
            command=self.on_channel_changed
        )
        self.dropdown_channel.pack(side="left", padx=5)
        
        self.btn_auth = ctk.CTkButton(
            self.selector_frame,
            text="ACTUALIZAR API",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_BOLD,
            width=120,
            command=lambda: self.authenticate_and_load(force_reload=True)
        )
        self.btn_auth.pack(side="left", padx=5)

        self.btn_mock = ctk.CTkButton(
            self.selector_frame,
            text="SIMULACIÓN",
            fg_color=COLOR_BORDER,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_DIM,
            font=FONT_BOLD,
            width=100,
            command=self.load_mock_data
        )
        self.btn_mock.pack(side="left", padx=5)

        # Panel principal de visualización
        self.display_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.display_panel.pack(fill="both", expand=True)
        
        # Cargar mensaje inicial si no hay canales
        if not self.main_window.channels:
            self.show_no_channels_message()

    def on_channel_changed(self, value):
        self.main_window.active_channel_name = value
        self.authenticate_and_load(force_reload=True)

    def show_no_channels_message(self):
        for w in self.display_panel.winfo_children():
            w.destroy()
            
        no_channels_label = ctk.CTkLabel(
            self.display_panel,
            text="No hay canales registrados.\nVe a 'Ajustes de Canales' en la barra lateral para agregar uno.",
            font=FONT_BOLD,
            text_color=COLOR_TEXT_DIM
        )
        no_channels_label.pack(expand=True, pady=100)

    def load_mock_data(self):
        """Carga datos de simulación para pruebas rápidas."""
        channel_name = self.selected_channel_name.get()
        if not channel_name or channel_name == "Sin canales":
            channel_name = "Canal de Simulación"
        
        self.current_data = get_mock_channel_analytics(channel_name)
        self.loaded_channel_name = channel_name + " (MOCK)"
        self.render_dashboard_metrics()

    def authenticate_and_load(self, force_reload=False):
        """Intenta autenticar usando OAuth y descargar datos reales."""
        channel_name = self.selected_channel_name.get()
        
        # Si no es carga forzada, y ya están cargadas las métricas de este canal, no hacer nada
        if not force_reload and self.loaded_channel_name == channel_name and self.current_data:
            print(f"MetricsTab: El canal '{channel_name}' ya está cargado en memoria. Saltando recarga API.")
            return

        # Buscar el canal correspondiente en la configuración
        channel_info = next((c for c in self.main_window.channels if c["name"] == channel_name), None)
        
        if not channel_info:
            messagebox.showwarning("Error de canal", "Selecciona un canal válido para autenticar.")
            return
            
        # Preparar rutas de credenciales
        client_secrets = channel_info.get("credential_file", "")
        if not client_secrets or not os.path.exists(client_secrets):
            messagebox.showwarning(
                "Credenciales faltantes",
                "El canal no tiene configurado un archivo client_secrets.json local.\n"
                "Por favor, agrégalo en 'Ajustes de Canales'."
            )
            return
            
        # Generar un nombre único de token para este canal
        safe_name = "".join([c if c.isalnum() else "_" for c in channel_name])
        token_path = os.path.join("config", f"token_{safe_name}.pickle")
        
        # Iniciar hilo de carga para no congelar la interfaz
        is_cache = not force_reload and has_valid_metrics_cache(channel_name)
        self.show_loading_screen(is_cache=is_cache)
        
        def run_auth():
            try:
                self.current_data = fetch_channel_data_and_analytics(client_secrets, token_path)
                self.main_window.after(0, self.render_dashboard_metrics)
            except Exception as e:
                err_msg = str(e)
                self.main_window.after(0, lambda msg=err_msg: self.handle_load_error(msg))
                
        threading.Thread(target=run_auth, daemon=True).start()

    def show_loading_screen(self, is_cache=False):
        for w in self.display_panel.winfo_children():
            w.destroy()
            
        msg = "Cargando desde caché local..." if is_cache else "Esperando autenticación en el navegador...\nCargando métricas de YouTube Analytics API..."
        
        loading_label = ctk.CTkLabel(
            self.display_panel,
            text=msg,
            font=FONT_BOLD,
            text_color=COLOR_ACCENT
        )
        loading_label.pack(expand=True, pady=100)

    def handle_load_error(self, err_msg):
        # Preguntar si desea cargar simulación
        if messagebox.askyesno("Error de Conexión", f"No se pudo conectar a la API de YouTube:\n\n{err_msg}\n\n¿Deseas ver datos de simulación para desarrollo?"):
            self.load_mock_data()
        else:
            self.render_dashboard_metrics()

    def render_dashboard_metrics(self):
        """Renderiza todo el dashboard de métricas usando los datos cargados."""
        self.loaded_channel_name = self.selected_channel_name.get()
        for w in self.display_panel.winfo_children():
            w.destroy()
            
        if not self.current_data:
            return
            
        # --- 1. FILA DE TARJETAS KPIs ---
        kpi_frame = ctk.CTkFrame(self.display_panel, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(5, 15))
        
        kpi_data = [
            ("VISTAS TOTALES", f"{self.current_data['total_views']:,}", COLOR_ACCENT),
            ("HORAS REPRODUCIDAS", f"{self.current_data['watch_time_hours']:,}h", COLOR_SUCCESS),
            ("NUEVOS SUBS (NETO)", f"+{self.current_data['net_subscribers']:,}" if self.current_data['net_subscribers'] >= 0 else f"{self.current_data['net_subscribers']:,}", COLOR_SUCCESS if self.current_data['net_subscribers'] >= 0 else COLOR_ACCENT),
            ("RETENCIÓN MEDIA", f"{self.current_data['average_duration_seconds']}s", COLOR_TEXT_MAIN)
        ]
        
        for title, val, color in kpi_data:
            card = ctk.CTkFrame(kpi_frame, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=6, height=80)
            card.pack(side="left", fill="both", expand=True, padx=5)
            card.pack_propagate(False)
            
            ctk.CTkLabel(card, text=title, font=FONT_BOLD, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=15, pady=(10, 2))
            ctk.CTkLabel(card, text=val, font=("Impact", 24), text_color=color).pack(anchor="w", padx=15)

        # --- 2. CONTENIDO PRINCIPAL: GRÁFICO + TABLA ---
        main_content = ctk.CTkFrame(self.display_panel, fg_color="transparent")
        main_content.pack(fill="both", expand=True)
        
        # Columna Izquierda: Gráfico
        graph_container = ctk.CTkFrame(main_content, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8)
        graph_container.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(graph_container, text="EVOLUCIÓN DE VISTAS (ÚLTIMOS 30 DÍAS)", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(anchor="w", padx=15, pady=15)
        
        # Espacio para el gráfico
        self.draw_graph(graph_container)

        # Columna Derecha: Detalles / Interacciones
        details_container = ctk.CTkFrame(main_content, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8, width=280)
        details_container.pack(side="right", fill="both", expand=False, padx=(5, 0))
        details_container.pack_propagate(False)
        
        ctk.CTkLabel(details_container, text="DETALLE DE INTERACCIONES", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(anchor="w", padx=15, pady=15)
        
        # Tabla de interacciones
        interaction_data = [
            ("Likes Totales", f"{self.current_data['total_likes']:,}"),
            ("Comentarios", f"{self.current_data['total_comments']:,}"),
            ("Compartidos", f"{self.current_data['total_shares']:,}")
        ]
        
        for name, val in interaction_data:
            row = ctk.CTkFrame(details_container, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=5)
            ctk.CTkLabel(row, text=name, font=FONT_MAIN, text_color=COLOR_TEXT_DIM).pack(side="left")
            ctk.CTkLabel(row, text=val, font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(side="right")
            
        # Separador
        ctk.CTkFrame(details_container, fg_color=COLOR_BORDER, height=1).pack(fill="x", padx=15, pady=15)
        
        # Engagement rate
        views = self.current_data["total_views"]
        likes = self.current_data["total_likes"]
        comments = self.current_data["total_comments"]
        shares = self.current_data["total_shares"]
        
        engagement_rate = 0
        if views > 0:
            engagement_rate = ((likes + comments + shares) / views) * 100
            
        ctk.CTkLabel(details_container, text="Tasa de Interacción", font=FONT_MAIN, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=15)
        ctk.CTkLabel(details_container, text=f"{engagement_rate:.2f}%", font=("Impact", 28), text_color=COLOR_SUCCESS).pack(anchor="w", padx=15, pady=5)
        
        # Explicación
        desc = ("Indica el porcentaje de espectadores que reaccionan o comentan tus contenidos "
                "en relación con las vistas totales.")
        ctk.CTkLabel(
            details_container, 
            text=desc, 
            font=FONT_MAIN, 
            text_color=COLOR_TEXT_DIM, 
            wraplength=250, 
            justify="left"
        ).pack(anchor="w", padx=15, pady=10)

    def draw_graph(self, parent_frame):
        """Dibuja el gráfico utilizando Matplotlib o un fallback en Canvas si no está disponible."""
        history = self.current_data.get("daily_history", [])
        if not history:
            return
            
        views_data = [d.get("views", 0) for d in history]
        days_data = [d.get("day", "")[-2:] for d in history] # Solo el día del mes
        
        if HAS_MATPLOTLIB:
            try:
                # Estilo oscuro para matplotlib a juego con el panel
                fig = Figure(figsize=(6, 3), dpi=100)
                fig.patch.set_facecolor("#070707")
                
                ax = fig.add_subplot(111)
                ax.set_facecolor("#070707")
                
                # Graficar la línea con color Neon Red
                ax.plot(days_data, views_data, color="#FF0000", linewidth=2.5, marker="o", markersize=4, markerfacecolor="#FFFFFF")
                
                # Configurar rejillas y colores de ejes
                ax.grid(True, color="#1F1F1F", linestyle="--")
                ax.spines['bottom'].set_color('#1F1F1F')
                ax.spines['top'].set_color('none')
                ax.spines['left'].set_color('#1F1F1F')
                ax.spines['right'].set_color('none')
                
                ax.tick_params(colors='#888888', labelsize=8)
                ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(8))
                
                canvas = FigureCanvasTkAgg(fig, master=parent_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=(0, 15))
                return
            except Exception as e:
                print(f"Error renderizando gráfico en Matplotlib: {e}")
                # Si falla, continúa al fallback Canvas
        
        # FALLBACK: Gráfico personalizado dibujado a mano sobre Canvas de Tkinter
        canvas = tk.Canvas(parent_frame, bg=COLOR_PANEL, highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Esperar a que el Canvas esté mapeado para obtener sus dimensiones reales
        def draw_canvas_lines(event=None):
            canvas.delete("all")
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            
            if w <= 1 or h <= 1:
                return # Todavía no está listo
                
            padding_x = 40
            padding_y = 30
            
            graph_w = w - padding_x * 2
            graph_h = h - padding_y * 2
            
            max_v = max(views_data) if views_data else 1
            min_v = min(views_data) if views_data else 0
            diff = max_v - min_v if max_v != min_v else 1
            
            points = []
            for idx, val in enumerate(views_data):
                cx = padding_x + (idx / (len(views_data) - 1)) * graph_w
                cy = (padding_y + graph_h) - ((val - min_v) / diff) * graph_h
                points.append((cx, cy))
                
            # Dibujar líneas de rejilla horizontales
            for i in range(4):
                grid_y = padding_y + (i / 3) * graph_h
                grid_val = int(max_v - (i / 3) * diff)
                canvas.create_line(padding_x, grid_y, w - padding_x, grid_y, fill="#1F1F1F", dash=(2, 2))
                canvas.create_text(padding_x - 5, grid_y, text=f"{grid_val:,}", fill="#555555", font=("Inter", 8), anchor="e")
                
            # Dibujar curva
            for idx in range(len(points) - 1):
                p1 = points[idx]
                p2 = points[idx + 1]
                canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=COLOR_ACCENT, width=2)
                
            # Dibujar puntos
            for idx, pt in enumerate(points):
                # Solo dibujar algunos puntos para no saturar
                if idx % 3 == 0 or idx == len(points) - 1:
                    canvas.create_oval(pt[0]-3, pt[1]-3, pt[0]+3, pt[1]+3, fill="#FFFFFF", outline=COLOR_ACCENT, width=1.5)
                    # Mostrar el número de día del mes abajo
                    day_lbl = days_data[idx]
                    canvas.create_text(pt[0], padding_y + graph_h + 12, text=day_lbl, fill="#555555", font=("Inter", 8))
                    
        canvas.bind("<Configure>", draw_canvas_lines)
        parent_frame.after(100, draw_canvas_lines)
        
    def update_channels(self):
        """Actualiza la lista de canales del dropdown."""
        self.channel_names = [c["name"] for c in self.main_window.channels]
        current = self.selected_channel_name.get()
        if current not in self.channel_names:
            current = self.main_window.active_channel_name
            if current not in self.channel_names:
                current = self.channel_names[0] if self.channel_names else ""
            self.selected_channel_name.set(current)
            self.loaded_channel_name = None
            self.current_data = None
        
        self.dropdown_channel.configure(values=self.channel_names if self.channel_names else ["Sin canales"])
        if not self.main_window.channels:
            self.show_no_channels_message()

    def sync_active_channel(self):
        """Sincroniza la pestaña con el canal activo de MainWindow."""
        active = self.main_window.active_channel_name
        if active and active in self.channel_names:
            if self.selected_channel_name.get() != active:
                self.selected_channel_name.set(active)
            self.authenticate_and_load(force_reload=False)
        elif not active:
            self.show_no_channels_message()

    def refresh_channel_list(self):
        """Actualiza dinámicamente la lista de canales del dropdown."""
        self.update_channels()
