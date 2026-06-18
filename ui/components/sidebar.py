import customtkinter as ctk
import webbrowser

# --- PREMIUM PALETTE (REFINED) ---
COLOR_BG_SIDEBAR = "#020202"    # Absolute Black
COLOR_BTN_HOVER = "#0A0A0A"
COLOR_ACCENT_RED = "#FF0000"     # Pure Neon Red
COLOR_INDICATOR = "#FF0000"

class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, main_window):
        super().__init__(parent, width=60, corner_radius=0, fg_color=COLOR_BG_SIDEBAR)
        self.main = main_window
        
        self.grid_propagate(False)
        self.pack_propagate(False) # Bloqueo crítico para forzar los 60px
        
        self.buttons = {}
        self.active_indicator = None
        self.current_view = None
        
        self.setup_ui()
        self.configure(width=60) # Reafirmar ancho atómico
        self.after(2000, self.check_real_width)

    def check_real_width(self):
        try:
            w = self.winfo_width()
            print(f">>> [SIDEBAR DIAGNOSTIC] Actual Width: {w}px | Target: 60px")
        except Exception as e:
            print(f">>> [SIDEBAR ERROR] Could not measure: {e}")

    def setup_ui(self):
        # 1. LOGO AREA
        logo_area = ctk.CTkFrame(self, fg_color="transparent", height=60, width=60)
        logo_area.pack(side="top", pady=(10, 15), fill="x")
        logo_area.pack_propagate(False) # Forzar 60px aquí
        
        logo = ctk.CTkLabel(logo_area, text="SR", font=("Impact", 18), text_color="white",
                            fg_color=COLOR_ACCENT_RED, width=34, height=34, corner_radius=6)
        logo.pack(expand=True)

        # 2. MAIN NAVIGATION
        self.nav_container = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_container.pack(side="top", fill="x", padx=5)        
        # Indicator Bar (The "Sliding" element)
        self.indicator_bar = ctk.CTkFrame(self, width=3, height=24, fg_color=COLOR_INDICATOR, corner_radius=2)
        # We will use .place() for the indicator so we can animate it
        
        items = [
            ("🏠", "dashboard", "HOME"),
            ("🔍", "concept", "SEMILLA DEL TERROR"),
            ("🎨", "visuals", "CONTEXTO NARRATIVO"),
            ("📸", "cover", "DISEÑO DE PORTADA"),
            ("🎙️", "voice_gen", "GENERACIÓN DE VOZ (TTS)"),
            ("🎬", "media", "NARRATIVA Y AUDIO ENGINE"),
            ("📽️", "long_form", "VIDEOS LARGOS 16:9"),
            ("📊", "comparator", "BENCHMARK ESTRATÉGICO")
        ]
        
        for icon, view, tip in items:
            btn = self.create_nav_btn(self.nav_container, icon, view, tip)
            self.buttons[view] = btn

        # 3. UTILS (Bottom)
        utils_frame = ctk.CTkFrame(self, fg_color="transparent", width=60, height=120)
        utils_frame.pack(side="bottom", fill="x", padx=5, pady=15)
        utils_frame.pack_propagate(False)
        
        self.create_util_btn(utils_frame, "🎲", self.main.open_narrative_editor)
        self.create_util_btn(utils_frame, "⚙️", self.main.open_config_editor)
        
        ctk.CTkFrame(utils_frame, height=1, fg_color="#1A1A1A").pack(fill="x", pady=6)
        
        self.btn_reset = ctk.CTkButton(utils_frame, text="🗑", font=("Arial", 16), width=38, height=38, 
                                     corner_radius=8, hover_color="#330000", fg_color="transparent", 
                                     text_color="#450000", command=self.main.reset_ui)
        self.btn_reset.pack(pady=3)

    def create_nav_btn(self, parent, icon, view, tip):
        btn = ctk.CTkButton(parent, 
                            text=icon, 
                            font=("Segoe UI Emoji", 18), 
                            width=38, 
                            height=38,
                            corner_radius=10,
                            hover_color=COLOR_BTN_HOVER,
                            fg_color="transparent",
                            text_color="#444444",
                            command=lambda: self.on_nav_click(view))
        btn.pack(pady=4)
        return btn

    def create_util_btn(self, parent, icon, command):
        btn = ctk.CTkButton(parent, text=icon, font=("Arial", 16), width=38, height=38,
                            corner_radius=8, hover_color="#111", fg_color="transparent",
                            text_color="#444", command=command)
        btn.pack(pady=3)
        return btn

    def on_nav_click(self, view_name):
        if self.current_view == view_name: return
        
        self.current_view = view_name
        self.main.show_view(view_name)
        
        # Animate Indicator and Update Colors
        target_btn = self.buttons[view_name]
        
        # Place indicator perfectly next to button
        # Get Y coordinate relative to the sidebar (centered: (38-24)/2 = 7)
        y_pos = target_btn.winfo_y() + self.nav_container.winfo_y() + 7
        self.indicator_bar.place(x=2, y=y_pos)
        
        for v, btn in self.buttons.items():
            if v == view_name:
                btn.configure(text_color=COLOR_ACCENT_RED, fg_color="#0A0000")
            else:
                btn.configure(text_color="#444", fg_color="transparent")
