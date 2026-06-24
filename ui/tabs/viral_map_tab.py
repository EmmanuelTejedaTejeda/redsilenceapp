import os
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# Intentar importar matplotlib
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.patheffects as path_effects
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

import networkx as nx
from modules.analytics_client import fetch_channel_videos, has_valid_videos_cache
from modules.graph_analyzer import generate_viral_graph_data

# --- PALETA DE COLORES ---
COLOR_BG = "#020202"
COLOR_PANEL = "#070707"
COLOR_ACCENT = "#FF0000"
COLOR_ACCENT_HOVER = "#CC0000"
COLOR_BORDER = "#1F1F1F"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_DIM = "#888888"
COLOR_SUCCESS = "#00FF66"

# --- RANGOS Y COLORES NEÓN ---
SCORE_RANGES = [
    (90, "S+", "#FF003C"),
    (80, "S", "#FF3300"),
    (70, "A", "#FFCC00"),
    (50, "B", "#00FFCC"),
    (30, "C", "#00FF66"),
    (0, "D", "#888888")
]

def get_rank_and_color(score):
    for limit, rank, color in SCORE_RANGES:
        if score >= limit:
            return rank, color
    return "D", "#888888"

FONT_TITLE = ("Impact", 28)
FONT_BOLD = ("Inter", 12, "bold")
FONT_MAIN = ("Inter", 12)
FONT_MONO = ("Consolas", 11)

class ViralMapTab(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, fg_color="transparent")
        self.main_window = main_window
        self.videos = []
        self.loaded_channel_name = None
        self.loading = False
        
        # Cabecera de la sección
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(10, 15))
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="MAPA DE VIRALIDAD", font=FONT_TITLE, text_color=COLOR_ACCENT)
        self.title_label.pack(side="left")
        
        # Selector de canal y botón refrescar
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
            width=180,
            command=self.on_channel_changed
        )
        self.dropdown_channel.pack(side="left", padx=5)
        
        self.btn_reload = ctk.CTkButton(
            self.selector_frame,
            text="ACTUALIZAR API",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_BOLD,
            width=110,
            command=lambda: self.authenticate_and_load_videos(force_reload=True)
        )
        self.btn_reload.pack(side="left", padx=5)
        
        # --- PANEL DE CONTROLES E FILTROS ---
        self.filters_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8)
        self.filters_frame.pack(fill="x", pady=(0, 15))
        
        # Filtro de tipo de video
        ctk.CTkLabel(self.filters_frame, text="Segmento:", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(side="left", padx=(15, 5), pady=10)
        self.segment_var = tk.StringVar(value="Shorts")
        self.segmented_button = ctk.CTkSegmentedButton(
            self.filters_frame,
            values=["Todos", "Shorts", "Videos Largos", "Directos"],
            variable=self.segment_var,
            command=self.on_filter_changed,
            fg_color=COLOR_BG,
            selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_BOLD
        )
        self.segmented_button.pack(side="left", padx=5, pady=10)
        
        # Filtro de frecuencia mínima de palabras
        ctk.CTkLabel(self.filters_frame, text="Frecuencia Mínima:", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(side="left", padx=(30, 5), pady=10)
        
        self.label_freq_value = ctk.CTkLabel(self.filters_frame, text="2", font=FONT_BOLD, text_color=COLOR_SUCCESS, width=20)
        self.label_freq_value.pack(side="left", padx=2, pady=10)
        
        self.slider_freq = ctk.CTkSlider(
            self.filters_frame,
            from_=1,
            to=10,
            number_of_steps=9,
            command=self.on_slider_changed,
            button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            progress_color=COLOR_BORDER,
            fg_color=COLOR_BG,
            width=150
        )
        self.slider_freq.set(2)
        self.slider_freq.pack(side="left", padx=5, pady=10)
        
        # --- CONTENEDOR PRINCIPAL DE CONTENIDO ---
        self.main_layout = ctk.CTkFrame(self, fg_color="transparent")
        self.main_layout.pack(fill="both", expand=True)
        
        # Subpanel izquierdo (Grafo)
        self.graph_frame = ctk.CTkFrame(self.main_layout, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8)
        self.graph_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Subpanel derecho (Tabla de palabras más virales)
        self.table_frame = ctk.CTkFrame(self.main_layout, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8, width=320)
        self.table_frame.pack(side="right", fill="both")
        self.table_frame.pack_propagate(False)
        
        # Inicializar lienzo Matplotlib
        self.fig = Figure(figsize=(5, 5), facecolor=COLOR_PANEL)
        self.canvas = None
        
        if HAS_MATPLOTLIB:
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
            self.canvas_widget = self.canvas.get_tk_widget()
            self.canvas_widget.pack(fill="both", expand=True, padx=10, pady=10)
            self.canvas_widget.configure(bg=COLOR_PANEL, highlightbackground=COLOR_PANEL)
        else:
            lbl_no_mpl = ctk.CTkLabel(
                self.graph_frame,
                text="Matplotlib no está instalado.\nInstala la librería para visualizar el grafo.",
                font=FONT_BOLD,
                text_color=COLOR_TEXT_DIM
            )
            lbl_no_mpl.pack(expand=True)
            
        # Título de la tabla derecha
        self.table_title = ctk.CTkLabel(self.table_frame, text="PALABRAS MÁS VIRALES", font=FONT_BOLD, text_color=COLOR_SUCCESS, pady=10)
        self.table_title.pack(fill="x")
        
        # Encabezados de la tabla
        self.headers_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent", height=25)
        self.headers_frame.pack(fill="x", padx=10)
        
        ctk.CTkLabel(self.headers_frame, text="Palabra", font=FONT_BOLD, text_color=COLOR_TEXT_DIM, anchor="w").pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(self.headers_frame, text="Freq", font=FONT_BOLD, text_color=COLOR_TEXT_DIM, width=40, anchor="center").pack(side="left")
        ctk.CTkLabel(self.headers_frame, text="Score", font=FONT_BOLD, text_color=COLOR_TEXT_DIM, width=60, anchor="center").pack(side="left")
        ctk.CTkLabel(self.headers_frame, text="Rango", font=FONT_BOLD, text_color=COLOR_TEXT_DIM, width=40, anchor="center").pack(side="left", padx=(5, 0))
        
        # Separador de encabezados
        self.sep = ctk.CTkFrame(self.table_frame, height=1, fg_color=COLOR_BORDER)
        self.sep.pack(fill="x", padx=10, pady=5)
        
        # Contenedor scrollable para las filas de datos
        self.table_scroll = ctk.CTkScrollableFrame(
            self.table_frame,
            fg_color="transparent",
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT
        )
        self.table_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 10))
        
        # Cargar pantalla inicial
        if not self.main_window.channels:
            self.show_message("No hay canales registrados.\nVe a 'Ajustes de Canales' en la barra lateral para agregar uno.")
            
    def on_channel_changed(self, value):
        self.main_window.active_channel_name = value
        self.authenticate_and_load_videos(force_reload=False)
        
    def on_filter_changed(self, value):
        self.generate_and_render_graph()
        
    def on_slider_changed(self, value):
        val_int = int(float(value))
        self.label_freq_value.configure(text=str(val_int))
        self.generate_and_render_graph()
        
    def show_message(self, text):
        """Muestra un mensaje explicativo en la zona del grafo."""
        self.fig.clear()
        self.fig.patch.set_facecolor(COLOR_PANEL)
        if HAS_MATPLOTLIB:
            ax = self.fig.add_subplot(111)
            ax.set_facecolor(COLOR_PANEL)
            ax.axis("off")
            ax.text(0.5, 0.5, text, color=COLOR_TEXT_DIM, fontname="Inter", fontsize=11,
                    horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
            self.canvas.draw()
            
        # Limpiar tabla derecha
        for widget in self.table_scroll.winfo_children():
            widget.destroy()
            
    def show_loading_screen(self):
        self.show_message("Procesando transcripciones y mapeando grafo...\nPor favor, espera.")
        
    def handle_load_error(self, err_msg):
        self.loading = False
        messagebox.showerror("Error", f"Error al cargar datos del canal:\n{err_msg}")
        self.show_message(f"Error al cargar canal:\n{err_msg}")
        
    def authenticate_and_load_videos(self, force_reload=False):
        """Carga los videos de YouTube por API o caché y sincroniza las pestañas."""
        channel_name = self.selected_channel_name.get()
        if not channel_name or channel_name == "Sin canales":
            self.show_message("Registra un canal para comenzar el análisis.")
            return
            
        # Reutilizar datos si ya están en memoria en la pestaña de videos y no es forzado
        videos_tab = self.main_window.dashboard_views.get("videos")
        if not force_reload and videos_tab and videos_tab.loaded_channel_name == channel_name and videos_tab.videos:
            self.videos = videos_tab.videos
            self.loaded_channel_name = channel_name
            self.generate_and_render_graph()
            return
            
        channel_info = next((c for c in self.main_window.channels if c["name"] == channel_name), None)
        if not channel_info:
            self.show_message("Selecciona un canal válido.")
            return
            
        client_secrets = channel_info.get("credential_file", "")
        if not client_secrets or not os.path.exists(client_secrets):
            self.show_message("El canal seleccionado no tiene un archivo client_secrets.json local configurado.\nVe a 'Ajustes de Canales' para configurarlo.")
            return
            
        # Generar token único para este canal
        safe_name = "".join([c if c.isalnum() else "_" for c in channel_name])
        token_path = os.path.join("config", f"token_{safe_name}.pickle")
        
        self.show_loading_screen()
        self.loading = True
        
        def run_load():
            try:
                self.videos = fetch_channel_videos(client_secrets, token_path, force_reload=force_reload)
                
                # Sincronizar de forma cruzada con VideosTab para evitar recargas duplicadas en la otra pestaña
                if videos_tab and (force_reload or videos_tab.loaded_channel_name != channel_name):
                    videos_tab.videos = self.videos
                    videos_tab.loaded_channel_name = channel_name
                    self.main_window.after(0, videos_tab.render_videos_list)
                    
                self.loaded_channel_name = channel_name
                self.loading = False
                self.main_window.after(0, self.generate_and_render_graph)
            except Exception as e:
                self.main_window.after(0, lambda msg=str(e): self.handle_load_error(msg))
                
        threading.Thread(target=run_load, daemon=True).start()
        
    def generate_and_render_graph(self):
        """Genera el grafo y la tabla en un hilo de fondo y los dibuja en UI."""
        if not self.videos:
            self.show_message("No hay videos cargados para este canal.")
            return
            
        segment = self.segment_var.get()
        type_filter = "all"
        if segment == "Shorts":
            type_filter = "shorts"
        elif segment == "Videos Largos":
            type_filter = "long"
        elif segment == "Directos":
            type_filter = "live"
            
        min_freq = int(self.slider_freq.get())
        
        # Mostrar pantalla de carga local del grafo
        self.show_loading_screen()
        
        def run_analysis():
            try:
                # Cargar el grafo de co-ocurrencias
                G, word_data = generate_viral_graph_data(
                    self.videos,
                    video_type_filter=type_filter,
                    min_frequency=min_freq,
                    max_nodes=30 # Filtramos a las top 30 palabras para mantener la visualización limpia
                )
                self.main_window.after(0, lambda: self.render_graph_ui(G, word_data))
            except Exception as e:
                self.main_window.after(0, lambda: self.handle_load_error(str(e)))
                
        threading.Thread(target=run_analysis, daemon=True).start()
        
    def render_graph_ui(self, G, word_data):
        """Dibuja el grafo en el lienzo de Matplotlib y llena la tabla derecha."""
        # 1. Limpiar tabla anterior
        for widget in self.table_scroll.winfo_children():
            widget.destroy()
            
        # 2. Validar que tengamos nodos
        if not HAS_MATPLOTLIB or G.number_of_nodes() == 0:
            self.show_message("No hay suficientes datos de co-ocurrencia para los filtros seleccionados.\nIntenta reducir la frecuencia mínima o actualizar la API.")
            return
            
        # 3. Dibujar Grafo en Matplotlib
        self.fig.clear()
        self.fig.patch.set_facecolor(COLOR_PANEL)
        
        # Forzar un subplot con fondo negro del color del panel de la app
        ax = self.fig.add_subplot(111)
        ax.set_facecolor(COLOR_PANEL)
        ax.axis("off")
        
        try:
            # Ocultar todos los bordes y recuadros de matplotlib
            for spine in ax.spines.values():
                spine.set_visible(False)
                
            # Layout spring estable con k dinámico (mayor dispersión para evitar colapso en el centro)
            num_nodes = G.number_of_nodes()
            k_val = 1.8 / (num_nodes ** 0.5) if num_nodes > 0 else 0.55
            pos = nx.spring_layout(G, k=k_val, iterations=100, seed=42)
            
            # Tamaños proporcionales a la raíz de la frecuencia para evitar nodos gigantes
            node_sizes = [130 + (G.nodes[n]['frequency'] ** 0.5) * 35 for n in G.nodes]
            
            # Normalizar dinámicamente los scores para pintar un degradado neón rojo premium
            scores = [G.nodes[n]['avg_score'] for n in G.nodes]
            min_s = min(scores) if scores else 0
            max_s = max(scores) if scores else 100
            span = max_s - min_s if max_s > min_s else 1
            
            def get_neon_border_color(score):
                norm = (score - min_s) / span
                # Mapeo de color: rojo oscuro apagado a rojo neón ardiente
                r = int(95 + norm * 160)
                g = int(norm * 30)
                b = int(15 + norm * 45)
                return f"#{r:02x}{g:02x}{b:02x}"
                
            node_edge_colors = [get_neon_border_color(G.nodes[n]['avg_score']) for n in G.nodes]
            
            # Dibujar Aristas (relaciones de co-ocurrencia con peso mínimo y límite de densidad)
            if G.number_of_edges() > 0:
                min_edge_weight = 2 if len(self.videos) >= 5 else 1
                filtered_edges = [e for e in G.edges if G.edges[e]['weight'] >= min_edge_weight]
                
                # Ordenar aristas por peso y quedarse con el top 60 para evitar saturación visual (manchas rojas)
                sorted_edges = sorted(filtered_edges, key=lambda x: G.edges[x].get('weight', 1), reverse=True)
                edges_to_draw = sorted_edges[:60]
                
                if edges_to_draw:
                    edge_widths = [1 + (G.edges[e]['weight'] ** 0.5) * 1.5 for e in edges_to_draw]
                    nx.draw_networkx_edges(
                        G, pos, ax=ax,
                        edgelist=edges_to_draw,
                        width=edge_widths,
                        edge_color="#FF003C",
                        alpha=0.08  # Alfa controlado para hilos tenues legibles
                    )
                
            # Dibujar Nodos (Anillos oscuros con bordes neón brillantes correspondientes a su score)
            nx.draw_networkx_nodes(
                G, pos, ax=ax,
                node_size=node_sizes,
                node_color="#0D0D0D",
                edgecolors=node_edge_colors,
                linewidths=2.5
            )
            
            # Dibujar Etiquetas de texto con silueta negra más gruesa y fuente genérica sans-serif para evitar warnings
            labels = nx.draw_networkx_labels(
                G, pos, ax=ax,
                font_size=8,
                font_color="#FFFFFF",
                font_weight="bold",
                font_family="sans-serif"
            )
            
            for text in labels.values():
                text.set_path_effects([
                    path_effects.Stroke(linewidth=3.5, foreground='#020202'),
                    path_effects.Normal()
                ])
                
        except Exception as draw_ex:
            print(f"Error renderizando grafo en Matplotlib: {draw_ex}")
            
        self.canvas.draw()
        
        # 4. Poblar la tabla scrollable de la derecha
        for index, item in enumerate(word_data):
            word = item["word"]
            freq = item["frequency"]
            score = int(item["avg_score"])
            
            # Determinar rango competitivo y color
            rank_label, rank_color = get_rank_and_color(score)
            
            # Frame contenedor para la fila
            row_frame = ctk.CTkFrame(self.table_scroll, fg_color="transparent", height=30)
            row_frame.pack(fill="x", pady=2, padx=5)
            
            # Columna Palabra
            lbl_word = ctk.CTkLabel(row_frame, text=f"#{index+1} {word}", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN, anchor="w")
            lbl_word.pack(side="left", expand=True, fill="x")
            
            # Columna Frecuencia
            lbl_freq = ctk.CTkLabel(row_frame, text=f"{freq}x", font=FONT_MAIN, text_color=COLOR_TEXT_DIM, width=40, anchor="center")
            lbl_freq.pack(side="left")
            
            # Columna Score Promedio
            lbl_score = ctk.CTkLabel(row_frame, text=f"{score}", font=FONT_MAIN, text_color=COLOR_TEXT_MAIN, width=60, anchor="center")
            lbl_score.pack(side="left")
            
            # Columna Rango (Badge estilizado)
            lbl_rank = ctk.CTkLabel(
                row_frame,
                text=rank_label,
                font=FONT_BOLD,
                text_color=rank_color,
                width=40,
                anchor="center"
            )
            lbl_rank.pack(side="left", padx=(5, 0))
            
            # Añadir una línea sutil de separación bajo la fila
            line = ctk.CTkFrame(self.table_scroll, height=1, fg_color="#121212")
            line.pack(fill="x", padx=5)

    def sync_active_channel(self):
        """Sincroniza el canal activo con el de MainWindow al cambiar de pestaña."""
        active = self.main_window.active_channel_name
        if active and active in self.channel_names:
            if self.selected_channel_name.get() != active:
                self.selected_channel_name.set(active)
            self.authenticate_and_load_videos(force_reload=False)
        elif not active:
            self.show_message("Registra un canal para comenzar el análisis.")

    def refresh_channel_list(self):
        """Actualiza la lista del menú desplegable cuando se editan los canales en ajustes."""
        self.channel_names = [c["name"] for c in self.main_window.channels]
        self.dropdown_channel.configure(values=self.channel_names if self.channel_names else ["Sin canales"])
        if self.channel_names:
            current = self.selected_channel_name.get()
            if current not in self.channel_names:
                self.selected_channel_name.set(self.channel_names[0])
                self.main_window.active_channel_name = self.channel_names[0]
            self.authenticate_and_load_videos(force_reload=False)
        else:
            self.selected_channel_name.set("Sin canales")
            self.show_message("No hay canales registrados.")
