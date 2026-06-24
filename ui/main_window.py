import os
import json
import hashlib
import urllib.request
import io
import threading
from PIL import Image, ImageDraw
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.utils import force_focus
from ui.tabs.metrics_tab import MetricsTab
from ui.tabs.videos_tab import VideosTab
from ui.tabs.viral_map_tab import ViralMapTab

# --- ESTÉTICA PREMIUM (NEON HORROR / DEEP DARK) ---
ctk.set_appearance_mode("Dark")

COLOR_BG = "#020202"           # Absolute Black
COLOR_PANEL = "#070707"        # Ultra Deep Grey
COLOR_ACCENT = "#FF0000"       # Pure Neon Red
COLOR_ACCENT_HOVER = "#CC0000" # Darker Red
COLOR_BORDER = "#1F1F1F"       # Subtle Charcoal Border
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_DIM = "#888888"
COLOR_SUCCESS = "#00FF66"

FONT_TITLE = ("Impact", 36)
FONT_SUBTITLE = ("Inter", 14)
FONT_MAIN = ("Inter", 12)
FONT_BOLD = ("Inter", 12, "bold")
FONT_MONO = ("Consolas", 11)

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("RED SILENCE | STUDIO CORE")
        self.geometry("1000x700")
        self.configure(fg_color=COLOR_BG)
        self.resizable(True, True)

        self.settings_path = os.path.join("config", "settings.json")
        self.channels = []
        self.load_settings()
        
        # Canal activo preseleccionado para la navegación entre pestañas
        self.active_channel_name = self.channels[0]["name"] if self.channels else ""

        # Inicializar estado del Dashboard persistente
        self.dashboard_layout = None
        self.main_content = None
        self.dashboard_views = {}
        self.sidebar_buttons = {}
        self.active_tab = None

        # Contenedor principal de vistas
        self.container = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        # Cargar vista correspondiente
        if not self.channels:
            self.show_channel_setup_view()
        else:
            self.show_dashboard_view()

        # Forzar foco al iniciar
        self.after(200, lambda: force_focus(self))

    def load_settings(self):
        """Carga las configuraciones de config/settings.json de forma segura."""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.channels = data.get("channels", [])
            except Exception as e:
                print(f"Error al cargar configuración: {e}")
                self.channels = []
        else:
            # Crear directorio config si no existe
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            self.save_settings()

    def save_settings(self):
        """Guarda la configuración actual en el disco."""
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump({"channels": self.channels}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

    def clear_container(self):
        """Elimina todos los widgets dentro del contenedor principal."""
        for widget in self.container.winfo_children():
            widget.destroy()

    # ==========================================
    # VISTA 1: CONFIGURACIÓN / AGREGAR CANALES
    # ==========================================
    def show_channel_setup_view(self):
        # Destruir referencias del dashboard si existían
        self.dashboard_layout = None
        self.main_content = None
        self.dashboard_views = {}
        self.sidebar_buttons = {}
        self.active_tab = None

        self.clear_container()

        # Cabecera de Configuración
        header_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 20))

        title = ctk.CTkLabel(header_frame, text="RED SILENCE SYSTEM", font=FONT_TITLE, text_color=COLOR_ACCENT)
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header_frame, 
            text="Configuración Inicial: Registra un canal para habilitar las subidas automáticas.", 
            font=FONT_SUBTITLE, 
            text_color=COLOR_TEXT_DIM
        )
        subtitle.pack(anchor="w", pady=(5, 0))

        # Panel de dos columnas
        content_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        content_frame.pack(fill="both", expand=True)

        # Columna Izquierda: Formulario
        form_frame = ctk.CTkFrame(content_frame, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8)
        form_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        form_title = ctk.CTkLabel(form_frame, text="AGREGAR NUEVO CANAL", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN)
        form_title.pack(anchor="w", padx=20, pady=(20, 15))

        # Input: Nombre
        ctk.CTkLabel(form_frame, text="Nombre del Canal:", font=FONT_MAIN, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=20)
        self.entry_channel_name = ctk.CTkEntry(
            form_frame, 
            fg_color=COLOR_BG, 
            border_color=COLOR_BORDER, 
            text_color=COLOR_TEXT_MAIN,
            font=FONT_MAIN,
            height=35
        )
        self.entry_channel_name.pack(fill="x", padx=20, pady=(5, 15))

        # Input: Plataforma
        ctk.CTkLabel(form_frame, text="Plataforma:", font=FONT_MAIN, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=20)
        self.option_platform = ctk.CTkOptionMenu(
            form_frame,
            values=["YouTube", "TikTok"],
            fg_color=COLOR_BG,
            button_color=COLOR_BORDER,
            button_hover_color=COLOR_ACCENT,
            dropdown_fg_color=COLOR_PANEL,
            dropdown_text_color=COLOR_TEXT_MAIN,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_MAIN,
            height=35
        )
        self.option_platform.pack(fill="x", padx=20, pady=(5, 15))

        # Input: API Key / Credenciales
        ctk.CTkLabel(form_frame, text="Clave API / Token de Acceso:", font=FONT_MAIN, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=20)
        self.entry_api_key = ctk.CTkEntry(
            form_frame, 
            fg_color=COLOR_BG, 
            border_color=COLOR_BORDER, 
            text_color=COLOR_TEXT_MAIN,
            font=FONT_MAIN,
            placeholder_text="Ingresa la API Key o selecciona un archivo...",
            height=35
        )
        self.entry_api_key.pack(fill="x", padx=20, pady=(5, 5))

        # Botón para subir archivo JSON
        self.selected_file_path = ""
        btn_upload = ctk.CTkButton(
            form_frame,
            text="Seleccionar archivo de credenciales (.json / .pickle)",
            fg_color=COLOR_BG,
            hover_color=COLOR_BORDER,
            border_color=COLOR_BORDER,
            border_width=1,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_MAIN,
            height=30,
            command=self.select_credential_file
        )
        btn_upload.pack(anchor="w", padx=20, pady=(5, 20))

        # Botón Añadir Canal
        btn_add = ctk.CTkButton(
            form_frame,
            text="REGISTRAR CANAL",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT_MAIN,
            font=FONT_BOLD,
            height=40,
            command=self.add_channel
        )
        btn_add.pack(fill="x", padx=20, pady=(10, 20))

        # Columna Derecha: Lista de Canales Configurados
        list_frame = ctk.CTkFrame(content_frame, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8)
        list_frame.pack(side="right", fill="both", expand=True, padx=(10, 0), pady=10)

        list_title = ctk.CTkLabel(list_frame, text="CANALES REGISTRADOS", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN)
        list_title.pack(anchor="w", padx=20, pady=(20, 15))

        # Contenedor con scroll para la lista
        self.scrollable_list = ctk.CTkScrollableFrame(
            list_frame, 
            fg_color="transparent", 
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT
        )
        self.scrollable_list.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.update_channels_list_ui()

        # Panel inferior para continuar
        footer_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        footer_frame.pack(fill="x", pady=(20, 10))

        self.btn_continue = ctk.CTkButton(
            footer_frame,
            text="CONTINUAR AL PANEL PRINCIPAL →",
            fg_color=COLOR_SUCCESS if self.channels else COLOR_BORDER,
            hover_color="#00CC52" if self.channels else COLOR_BORDER,
            text_color=COLOR_BG if self.channels else COLOR_TEXT_DIM,
            font=FONT_BOLD,
            state="normal" if self.channels else "disabled",
            height=45,
            command=self.show_dashboard_view
        )
        self.btn_continue.pack(side="right")

    def select_credential_file(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo de credenciales",
            filetypes=[("Archivos de credenciales", "*.json *.pickle"), ("Todos los archivos", "*.*")]
        )
        if file_path:
            self.selected_file_path = file_path
            self.entry_api_key.delete(0, "end")
            self.entry_api_key.insert(0, file_path)

    def add_channel(self):
        name = self.entry_channel_name.get().strip()
        platform = self.option_platform.get()
        api_key = self.entry_api_key.get().strip()

        if not name:
            messagebox.showwarning("Campo requerido", "Por favor, ingresa el nombre del canal.")
            return

        if not api_key:
            messagebox.showwarning("Campo requerido", "Por favor, ingresa una clave API o selecciona un archivo de credenciales.")
            return

        # Crear diccionario del canal
        new_channel = {
            "name": name,
            "platform": platform,
            "api_key": api_key if not os.path.exists(api_key) else "",
            "credential_file": api_key if os.path.exists(api_key) else ""
        }

        self.channels.append(new_channel)
        if not self.active_channel_name:
            self.active_channel_name = name
        self.save_settings()

        # Limpiar entradas
        self.entry_channel_name.delete(0, "end")
        self.entry_api_key.delete(0, "end")
        self.selected_file_path = ""

        # Actualizar UI
        self.update_channels_list_ui()

        # Notificar a las pestañas si existen en memoria
        if hasattr(self, "dashboard_views"):
            if "videos" in self.dashboard_views:
                self.dashboard_views["videos"].refresh_channel_list()
            if "metrics" in self.dashboard_views:
                self.dashboard_views["metrics"].refresh_channel_list()
            if "viral_map" in self.dashboard_views:
                self.dashboard_views["viral_map"].refresh_channel_list()

        # Habilitar botón continuar
        self.btn_continue.configure(
            state="normal", 
            fg_color=COLOR_SUCCESS, 
            hover_color="#00CC52", 
            text_color=COLOR_BG
        )

    def remove_channel(self, index):
        if 0 <= index < len(self.channels):
            self.channels.pop(index)
            
            # Actualizar canal activo si el actual fue eliminado
            if not self.channels:
                self.active_channel_name = ""
            elif self.active_channel_name not in [c["name"] for c in self.channels]:
                self.active_channel_name = self.channels[0]["name"]
                
            self.save_settings()
            self.update_channels_list_ui()

            # Notificar a las pestañas si existen en memoria
            if hasattr(self, "dashboard_views"):
                if "videos" in self.dashboard_views:
                    self.dashboard_views["videos"].refresh_channel_list()
                if "metrics" in self.dashboard_views:
                    self.dashboard_views["metrics"].refresh_channel_list()
                if "viral_map" in self.dashboard_views:
                    self.dashboard_views["viral_map"].refresh_channel_list()

            # Deshabilitar botón continuar si no quedan canales
            if not self.channels:
                self.btn_continue.configure(
                    state="disabled", 
                    fg_color=COLOR_BORDER, 
                    hover_color=COLOR_BORDER, 
                    text_color=COLOR_TEXT_DIM
                )

    def update_channels_list_ui(self):
        # Limpiar lista actual en UI
        for widget in self.scrollable_list.winfo_children():
            widget.destroy()

        if not self.channels:
            empty_label = ctk.CTkLabel(
                self.scrollable_list, 
                text="No hay canales registrados aún.", 
                font=FONT_MAIN, 
                text_color=COLOR_TEXT_DIM
            )
            empty_label.pack(pady=40)
            return

        for idx, channel in enumerate(self.channels):
            item_frame = ctk.CTkFrame(self.scrollable_list, fg_color=COLOR_BG, border_color=COLOR_BORDER, border_width=1, corner_radius=6)
            item_frame.pack(fill="x", pady=5)

            # Información del canal
            info_text = f"{channel['name']} ({channel['platform']})"
            info_label = ctk.CTkLabel(item_frame, text=info_text, font=FONT_BOLD, text_color=COLOR_TEXT_MAIN)
            info_label.pack(side="left", padx=15, pady=10)

            # Botón eliminar
            btn_delete = ctk.CTkButton(
                item_frame,
                text="ELIMINAR",
                fg_color="transparent",
                hover_color=COLOR_BORDER,
                text_color=COLOR_ACCENT,
                font=FONT_BOLD,
                width=70,
                height=25,
                command=lambda i=idx: self.remove_channel(i)
            )
            btn_delete.pack(side="right", padx=15, pady=10)


    def quick_jump(self, channel_name, tab):
        """Redirige directamente a una pestaña preseleccionando un canal específico."""
        self.active_channel_name = channel_name
        self.show_dashboard_view(tab)

    # ==========================================
    # VISTA 2: PANEL DE CONTROL (DASHBOARD)
    # ==========================================
    def show_dashboard_view(self, tab="home"):
        # Si el layout del dashboard no existe o fue destruido, lo creamos completo
        if not self.dashboard_layout or not self.dashboard_layout.winfo_exists():
            self.clear_container()

            # Layout del Dashboard: Sidebar + Main Content
            self.dashboard_layout = ctk.CTkFrame(self.container, fg_color="transparent")
            self.dashboard_layout.pack(fill="both", expand=True)

            # Sidebar Izquierdo
            sidebar = ctk.CTkFrame(self.dashboard_layout, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8, width=200)
            sidebar.pack(side="left", fill="y", padx=(0, 10), pady=10)
            sidebar.pack_propagate(False)

            logo_label = ctk.CTkLabel(sidebar, text="RED SILENCE", font=FONT_TITLE, text_color=COLOR_ACCENT)
            logo_label.pack(pady=(20, 30))

            # Botones de navegación sidebar
            self.sidebar_buttons = {}

            self.sidebar_buttons["home"] = ctk.CTkButton(
                sidebar, 
                text="Panel Principal", 
                fg_color="transparent", 
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_DIM, 
                font=FONT_MAIN,
                height=35,
                command=lambda: self.switch_tab("home")
            )
            self.sidebar_buttons["home"].pack(fill="x", padx=15, pady=5)

            self.sidebar_buttons["videos"] = ctk.CTkButton(
                sidebar, 
                text="Lista de Videos", 
                fg_color="transparent", 
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_DIM, 
                font=FONT_MAIN,
                height=35,
                command=lambda: self.switch_tab("videos")
            )
            self.sidebar_buttons["videos"].pack(fill="x", padx=15, pady=5)

            self.sidebar_buttons["metrics"] = ctk.CTkButton(
                sidebar, 
                text="Métricas Avanzadas", 
                fg_color="transparent", 
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_DIM, 
                font=FONT_MAIN,
                height=35,
                command=lambda: self.switch_tab("metrics")
            )
            self.sidebar_buttons["metrics"].pack(fill="x", padx=15, pady=5)

            self.sidebar_buttons["viral_map"] = ctk.CTkButton(
                sidebar, 
                text="Mapa de Viralidad", 
                fg_color="transparent", 
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_DIM, 
                font=FONT_MAIN,
                height=35,
                command=lambda: self.switch_tab("viral_map")
            )
            self.sidebar_buttons["viral_map"].pack(fill="x", padx=15, pady=5)

            btn_settings = ctk.CTkButton(
                sidebar, 
                text="Ajustes de Canales", 
                fg_color="transparent", 
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_DIM, 
                font=FONT_MAIN,
                height=35,
                command=self.show_channel_setup_view
            )
            btn_settings.pack(fill="x", padx=15, pady=5)

            # Main Content (Contenedor de pestañas)
            self.main_content = ctk.CTkFrame(self.dashboard_layout, fg_color=COLOR_PANEL, border_color=COLOR_BORDER, border_width=1, corner_radius=8)
            self.main_content.pack(side="right", fill="both", expand=True, padx=(10, 0), pady=10)

            # Inicializar las vistas en memoria
            self.dashboard_views = {}
            self.active_tab = None

            # 1. Vista Home
            self.dashboard_views["home"] = ctk.CTkFrame(self.main_content, fg_color="transparent")
            self.render_home_tab_content(self.dashboard_views["home"])

            # 2. Vista VideosTab
            self.dashboard_views["videos"] = VideosTab(self.main_content, self)

            # 3. Vista MetricsTab
            self.dashboard_views["metrics"] = MetricsTab(self.main_content, self)

            # 4. Vista ViralMapTab (Mapa de Viralidad)
            self.dashboard_views["viral_map"] = ViralMapTab(self.main_content, self)

        # Alternar a la pestaña solicitada
        self.switch_tab(tab)

    def switch_tab(self, tab):
        """Oculta la pestaña actual y muestra la pestaña seleccionada sin destruir widgets."""
        if self.active_tab == tab:
            # Si ya está en la pestaña solicitada, solo forzar sincronización de canal activo
            if tab == "videos":
                self.dashboard_views["videos"].sync_active_channel()
            elif tab == "metrics":
                self.dashboard_views["metrics"].sync_active_channel()
            elif tab == "viral_map":
                self.dashboard_views["viral_map"].sync_active_channel()
            return

        # Ocultar la pestaña anterior
        if self.active_tab and self.active_tab in self.dashboard_views:
            self.dashboard_views[self.active_tab].pack_forget()
            btn = self.sidebar_buttons.get(self.active_tab)
            if btn:
                btn.configure(
                    fg_color="transparent",
                    border_width=0,
                    text_color=COLOR_TEXT_DIM,
                    font=FONT_MAIN
                )

        # Mostrar la nueva pestaña
        if tab in self.dashboard_views:
            view = self.dashboard_views[tab]
            
            if tab == "home":
                self.render_home_tab_content(view)
                
            view.pack(fill="both", expand=True, padx=25, pady=25)
            
            # Estilizar el botón del sidebar seleccionado
            btn = self.sidebar_buttons.get(tab)
            if btn:
                btn.configure(
                    fg_color=COLOR_BG,
                    border_color=COLOR_BORDER,
                    border_width=1,
                    text_color=COLOR_TEXT_MAIN,
                    font=FONT_BOLD
                )
            
            self.active_tab = tab

            # Sincronizar el canal activo en la pestaña seleccionada
            if tab == "videos":
                self.dashboard_views["videos"].sync_active_channel()
            elif tab == "metrics":
                self.dashboard_views["metrics"].sync_active_channel()
            elif tab == "viral_map":
                self.dashboard_views["viral_map"].sync_active_channel()

    def render_home_tab_content(self, parent_frame):
        """Limpia y dibuja la lista de canales activos en la pestaña principal."""
        for widget in parent_frame.winfo_children():
            widget.destroy()

        # Cabecera interna del main content
        inner_header = ctk.CTkFrame(parent_frame, fg_color="transparent")
        inner_header.pack(fill="x", pady=(0, 10))

        welcome_title = ctk.CTkLabel(inner_header, text="BIENVENIDO AL PANEL DE CONTROL", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN)
        welcome_title.pack(anchor="w")

        welcome_desc = ctk.CTkLabel(inner_header, text="El sistema está listo para procesar y publicar tus contenidos.", font=FONT_MAIN, text_color=COLOR_TEXT_DIM)
        welcome_desc.pack(anchor="w", pady=5)

        # Contenedor de lista de canales activos
        ctk.CTkLabel(parent_frame, text="CANALES CONFIGURADOS Y ACTIVOS:", font=FONT_BOLD, text_color=COLOR_TEXT_MAIN).pack(anchor="w", pady=(15, 5))

        dashboard_list = ctk.CTkScrollableFrame(
            parent_frame,
            fg_color=COLOR_PANEL,
            border_width=0,
            corner_radius=0,
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT
        )
        dashboard_list.pack(fill="both", expand=True, pady=(0, 15))

        # Contenedor Grid dentro del ScrollableFrame para organizar por cards
        grid_frame = ctk.CTkFrame(dashboard_list, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True)

        for idx, channel in enumerate(self.channels):
            # Tarjeta de Canal
            card = ctk.CTkFrame(
                grid_frame, 
                fg_color=COLOR_BG, 
                border_color=COLOR_BORDER, 
                border_width=1, 
                corner_radius=8,
                width=210,
                height=180
            )
            card.grid(row=idx // 3, column=idx % 3, padx=10, pady=10)
            card.grid_propagate(False)
            
            # Cabecera de la tarjeta: Plataforma y Estado
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=12, pady=(12, 5))
            
            platform_name = channel['platform'].upper()
            platform_color = "#FF0000" if channel['platform'].lower() == "youtube" else "#00FF66"
            
            platform_badge = ctk.CTkFrame(
                header, 
                fg_color=COLOR_PANEL, 
                border_color=platform_color, 
                border_width=1, 
                corner_radius=4
            )
            platform_badge.pack(side="left")
            
            platform_lbl = ctk.CTkLabel(
                platform_badge, 
                text=platform_name, 
                font=("Inter", 9, "bold"), 
                text_color=platform_color,
                padx=6,
                pady=1
            )
            platform_lbl.pack()
            
            status_dot = ctk.CTkLabel(
                header, 
                text="● Conectado", 
                font=("Inter", 10, "bold"), 
                text_color=COLOR_SUCCESS
            )
            status_dot.pack(side="right")
            
            # Contenedor para el Logo circular
            logo_frame = ctk.CTkFrame(
                card, 
                width=70, 
                height=70, 
                corner_radius=35, 
                fg_color=COLOR_PANEL, 
                border_color=platform_color, 
                border_width=1.5
            )
            logo_frame.pack(pady=(12, 4))
            logo_frame.pack_propagate(False) # Forzar dimensiones circulares
            
            logo_lbl = ctk.CTkLabel(
                logo_frame, 
                text="▶" if channel['platform'].lower() == "youtube" else "🎵", 
                font=("Inter", 20, "bold"), 
                text_color=platform_color
            )
            logo_lbl.pack(expand=True)
            
            # Lanzar carga del logo real asíncronamente
            self.load_profile_pic_async(channel['name'], channel['platform'], logo_lbl, logo_frame)
            
            # Nombre del Canal
            name_lbl = ctk.CTkLabel(
                card, 
                text=channel['name'], 
                font=FONT_BOLD, 
                text_color=COLOR_TEXT_MAIN,
                wraplength=180
            )
            name_lbl.pack(pady=2)
            
            # Acciones rápidas (Videos / Métricas)
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", side="bottom", padx=12, pady=12)
            
            btn_videos = ctk.CTkButton(
                actions,
                text="Videos",
                font=("Inter", 9, "bold"),
                fg_color=COLOR_PANEL,
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_MAIN,
                height=24,
                width=56,
                command=lambda name=channel['name']: self.quick_jump(name, "videos")
            )
            btn_videos.pack(side="left", padx=2)
            
            btn_metrics = ctk.CTkButton(
                actions,
                text="Métricas",
                font=("Inter", 9, "bold"),
                fg_color=COLOR_PANEL,
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_MAIN,
                height=24,
                width=56,
                command=lambda name=channel['name']: self.quick_jump(name, "metrics")
            )
            btn_metrics.pack(side="left", padx=2)

            btn_viral = ctk.CTkButton(
                actions,
                text="Viralidad",
                font=("Inter", 9, "bold"),
                fg_color=COLOR_PANEL,
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_MAIN,
                height=24,
                width=56,
                command=lambda name=channel['name']: self.quick_jump(name, "viral_map")
            )
            btn_viral.pack(side="left", padx=2)

        # Contenedor para futuras herramientas
        tools_placeholder = ctk.CTkFrame(parent_frame, fg_color="transparent")
        tools_placeholder.pack(fill="x", side="bottom", pady=15)

        placeholder_label = ctk.CTkLabel(
            tools_placeholder, 
            text="[ Las herramientas de edición, generación y subida de videos se implementarán aquí ]",
            font=FONT_MONO,
            text_color=COLOR_TEXT_DIM
        )
        placeholder_label.pack(expand=True)

    def create_letter_avatar(self, channel_name, size=(68, 68)):
        """Genera un avatar circular con la inicial del canal y un color neón vibrante de fondo."""
        try:
            img = Image.new('RGBA', size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Paleta de colores neón vibrantes a juego con la interfaz
            colors = [
                (255, 0, 85, 255),   # Rojo neón hot
                (0, 255, 102, 255),  # Verde neón
                (0, 153, 255, 255),  # Azul neón
                (255, 204, 0, 255),  # Amarillo neón
                (255, 102, 0, 255),  # Naranja
                (153, 0, 255, 255),  # Púrpura neón
            ]
            bg_color = colors[abs(hash(channel_name)) % len(colors)]
            
            # Dibujar fondo circular
            draw.ellipse((0, 0, size[0], size[1]), fill=bg_color)
            
            # Obtener inicial
            initial = channel_name[0].upper() if channel_name else "?"
            
            # Cargar fuente limpia
            from PIL import ImageFont
            font = None
            for font_name in ["arial.ttf", "calibri.ttf", "Helvetica.ttf", "DejaVuSans.ttf"]:
                try:
                    font = ImageFont.truetype(font_name, 36)
                    break
                except Exception:
                    continue
            if font is None:
                font = ImageFont.load_default()
                
            # Dibujar inicial centrada
            try:
                draw.text((size[0]/2, size[1]/2), initial, fill=(255, 255, 255, 255), font=font, anchor="mm")
            except Exception:
                # Fallback para versiones antiguas de Pillow
                w, h = 15, 25
                draw.text(((size[0]-w)/2, (size[1]-h)/2), initial, fill=(255, 255, 255, 255), font=font)
                
            return img
        except Exception as e:
            print(f"Error generando avatar de letra: {e}")
            # Retornar círculo rojo si todo falla
            img = Image.new('RGBA', size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((0, 0, size[0], size[1]), fill=(255, 0, 0, 255))
            return img

    def load_profile_pic_async(self, channel_name, platform, label_widget, frame_widget):
        """Busca en caché o descarga y recorta circularmente el logo de perfil en segundo plano."""
        cache_dir = os.path.join("config", "cache", "profile_pics")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Intentar obtener la URL desde la caché de métricas
        metrics_cache_path = os.path.join("config", "cache", "metrics_cache.json")
        profile_pic_url = None
        
        # Buscamos en el caché de métricas con coincidencia flexible
        if os.path.exists(metrics_cache_path):
            try:
                with open(metrics_cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    for cid, cdata in cache_data.items():
                        summary = cdata.get("summary", {})
                        cached_name = summary.get("channel_name", "")
                        if cached_name.lower().strip() == channel_name.lower().strip():
                            profile_pic_url = summary.get("profile_pic")
                            break
            except Exception as e:
                print(f"Error leyendo caché de métricas para logo: {e}")
                
        # Nombre de archivo basado en el hash del nombre del canal para consistencia
        h = hashlib.md5(channel_name.encode('utf-8')).hexdigest()
        cache_path = os.path.join(cache_dir, f"{h}.png")
        
        size = (68, 68)
        
        def update_ui(circular_img):
            try:
                if label_widget.winfo_exists() and frame_widget.winfo_exists():
                    ctk_img = ctk.CTkImage(light_image=circular_img, dark_image=circular_img, size=size)
                    label_widget.configure(text="", image=ctk_img)
                    label_widget.image = ctk_img  # Mantener referencia fuerte para evitar Garbage Collection
            except Exception as ex:
                print(f"Error actualizando logo en UI: {ex}")

        # Si ya existe en caché local de disco, cargarlo de inmediato en el hilo principal
        if os.path.exists(cache_path):
            try:
                raw_img = Image.open(cache_path)
                raw_img.load()
                update_ui(raw_img)
                return
            except Exception as ex:
                print(f"Error leyendo logo cacheado: {ex}")
                try:
                    os.remove(cache_path)
                except:
                    pass

        # Si es un canal de simulación o mock (no hay URL real), generamos avatar de letras inmediatamente
        is_mock = "simulacion" in channel_name.lower() or "mock" in channel_name.lower()
        if is_mock or not profile_pic_url:
            circular_img = self.create_letter_avatar(channel_name, size)
            try:
                circular_img.save(cache_path, "PNG")
            except Exception as ex:
                print(f"Error guardando avatar de letra en disco: {ex}")
            update_ui(circular_img)
            return

        # Para canales reales con URL, descargar asíncronamente en un hilo secundario
        def worker():
            nonlocal profile_pic_url
            try:
                import ssl
                # Crear un contexto SSL que no verifique certificados (para evitar fallos de certificados SSL locales)
                try:
                    ssl_context = ssl._create_unverified_context()
                except AttributeError:
                    ssl_context = None
                
                req = urllib.request.Request(profile_pic_url, headers={'User-Agent': 'Mozilla/5.0'})
                if ssl_context:
                    with urllib.request.urlopen(req, timeout=12, context=ssl_context) as response:
                        img_data = response.read()
                else:
                    with urllib.request.urlopen(req, timeout=12) as response:
                        img_data = response.read()
                
                # Cargar y recortar la imagen descargada
                raw_img = Image.open(io.BytesIO(img_data))
                raw_img.load()
                raw_img = raw_img.resize(size, Image.Resampling.LANCZOS)
                
                # Crear máscara circular
                mask = Image.new('L', size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0], size[1]), fill=255)
                
                # Aplicar máscara
                circular_img = Image.new('RGBA', size, (0, 0, 0, 0))
                circular_img.paste(raw_img, (0, 0), mask=mask)
                
                # Guardar en disco para futuros inicios
                circular_img.save(cache_path, "PNG")
                
                self.after(0, lambda: update_ui(circular_img))
                
            except Exception as e:
                print(f"Error descargando logo real para '{channel_name}': {e}. Generando avatar local.")
                # Si falla la descarga, generamos un avatar local de letras de respaldo
                circular_img = self.create_letter_avatar(channel_name, size)
                try:
                    circular_img.save(cache_path, "PNG")
                except:
                    pass
                self.after(0, lambda: update_ui(circular_img))
                
        threading.Thread(target=worker, daemon=True).start()
