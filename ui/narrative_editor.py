import customtkinter as ctk
import itertools
import config.prompts as prompts_utils

# --- THEME CONSTANTS ---
COLOR_BG = "#080808"            # Background general ultra oscuro
COLOR_SIDEBAR = "#101010"       # Panel lateral
COLOR_EDITOR = "#141414"        # Fondo del editor
COLOR_ACCENT = "#E53935"        # Rojo vibrante
COLOR_ACCENT_HOVER = "#C62828"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_DIM = "#757575"
COLOR_BORDER = "#222222"

FONT_HEADER = ("Impact", 28)
FONT_SUBHEADER = ("Arial", 12, "bold")
FONT_EDITOR = ("Consolas", 13)

CATEGORIES = {
    "GANCHOS": {
        "icon": "🪝", 
        "desc": "Frases iniciales para atrapar al espectador.",
        "var_name": "LISTA_GANCHOS",
        "color": "#FF79C6" # Pink
    },
    "MONSTRUOS": {
        "icon": "👹", 
        "desc": "Entidades, criaturas o amenazas principales.",
        "var_name": "LISTA_MONSTRUOS",
        "color": "#FF5555" # Red
    },
    "ATMOSFERA": {
        "icon": "🌫️", 
        "desc": "Clima, iluminación y sensaciones del entorno.",
        "var_name": "LISTA_ATMOSFERA",
        "color": "#8BE9FD" # Cyan
    },
    "CIERRES": {
        "icon": "🔚", 
        "desc": "Frases finales o giros para terminar la historia.",
        "var_name": "LISTA_CIERRES",
        "color": "#BD93F9" # Purple
    }
}

class NarrativeEditor(ctk.CTkToplevel):
    def __init__(self, parent):

        super().__init__(parent)
        
        self.title("MATRIZ DE CAOS NARRATIVO | SILENCIO ROJO")
        self.geometry("1000x700")
        self.configure(fg_color=COLOR_BG)
        
        from core.utils import force_focus
        force_focus(self)
        
        # Grid Layout: Sidebar | Content
        self.grid_columnconfigure(0, weight=0, minsize=250) # Sidebar fija
        self.grid_columnconfigure(1, weight=1)              # Content expandible
        self.grid_rowconfigure(0, weight=1)

        # State storage for text widgets
        self.editors = {}
        self.current_btn = None
        self.nav_buttons = {}

        self.init_sidebar()
        self.init_content_area()
        
        # Load Data & Select First
        self.load_data_to_editors()
        self.select_category("GANCHOS")

    def init_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Header Sidebar
        ctk.CTkLabel(self.sidebar, text="VARIABLES\nALEATORIAS", font=("Impact", 20), text_color="#DDD", justify="left").pack(anchor="w", padx=20, pady=(30, 20))
        
        # Navigation Buttons
        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.pack(fill="x", padx=10)
        
        for key, data in CATEGORIES.items():
            btn = ctk.CTkButton(self.nav_container, 
                                text=f"{data['icon']}  {key}", 
                                anchor="w",
                                height=50,
                                font=("Arial", 12, "bold"),
                                fg_color="transparent",
                                hover_color="#222",
                                text_color="#AAA",
                                corner_radius=8,
                                border_width=1,
                                border_color=COLOR_SIDEBAR, # Invisible border initially
                                command=lambda k=key: self.select_category(k))
            btn.pack(fill="x", pady=5)
            self.nav_buttons[key] = btn

        # Bottom Actions
        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True) # Push bottom
        
        self.lbl_info_save = ctk.CTkLabel(self.sidebar, text="Cambios no guardados", text_color=COLOR_TEXT_DIM, font=("Arial", 10))
        self.lbl_info_save.pack(pady=(0, 5))

        self.btn_save = ctk.CTkButton(self.sidebar, 
                                      text="💾  GUARDAR MATRIZ", 
                                      height=50,
                                      fg_color=COLOR_ACCENT,
                                      hover_color=COLOR_ACCENT_HOVER,
                                      font=("Impact", 14),
                                      command=self.save_all)
        self.btn_save.pack(fill="x", padx=20, pady=(0, 30))

    def init_content_area(self):
        self.content_frame = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        
        # Dynamic Header
        self.lbl_category_title = ctk.CTkLabel(self.content_frame, text="...", font=("Impact", 32), text_color="#FFF")
        self.lbl_category_title.pack(anchor="w")
        
        self.lbl_category_desc = ctk.CTkLabel(self.content_frame, text="...", font=("Arial", 12), text_color=COLOR_TEXT_DIM)
        self.lbl_category_desc.pack(anchor="w", pady=(0, 20))

        # Editor Container (Holds all textboxes, we show/hide them)
        self.editor_container = ctk.CTkFrame(self.content_frame, fg_color=COLOR_EDITOR, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        self.editor_container.pack(fill="both", expand=True)

    def load_data_to_editors(self):
        # Create a Textbox for each category but hide them initially
        for key, data in CATEGORIES.items():
            # Container for specific editor
            # We use a frame to wrap header + editor
            wrapper = ctk.CTkFrame(self.editor_container, fg_color="transparent")
            
            # --- Faux Editor Header ---
            header = ctk.CTkFrame(wrapper, fg_color="#1E1E1E", height=30, corner_radius=0)
            header.pack(fill="x")
            
            # File Icon + Title
            ctk.CTkLabel(header, text=f" {data['icon']} {key}.txt ", font=("Consolas", 11, "bold"), 
                         text_color="#CCCCCC", fg_color="#2D2D2D", corner_radius=5).pack(side="left", padx=10, pady=2)
            
            ctk.CTkLabel(header, text="UTF-8", font=("Arial", 9), text_color="#555").pack(side="right", padx=10)

            # --- Textbox ---
            txt = ctk.CTkTextbox(wrapper, 
                                 font=("Consolas", 14), 
                                 fg_color="#141414", 
                                 text_color="#D4D4D4", 
                                 wrap="none", 
                                 undo=True,
                                 border_width=0,
                                 corner_radius=0,
                                 activate_scrollbars=True)
            txt.pack(fill="both", expand=True) # expand inside wrapper
            
            # Load Data
            raw_list = getattr(prompts_utils, data["var_name"], [])
            content = "\n".join(raw_list)
            txt.insert("0.0", content)
            
            # Initial Highlight
            self.highlight_list_items(txt, data.get("color", "#FFFFFF"))
            
            # Live Highlight
            txt.bind("<KeyRelease>", lambda e, t=txt, c=data.get("color", "#FFFFFF"): self.highlight_list_items(t, c))
            
            self.editors[key] = {"frame": wrapper, "textbox": txt}

    def highlight_list_items(self, textbox, main_color):
        try:
            text_widget = textbox._textbox
            full_text = text_widget.get("1.0", "end")
            
            # Clean old tags
            for tag in ["tag_prefix", "tag_paren", "tag_bullet"]:
                text_widget.tag_remove(tag, "1.0", "end")
            
            # Config Styles
            text_widget.tag_config("tag_prefix", foreground=main_color, font=("Consolas", 14, "bold"))
            text_widget.tag_config("tag_paren", foreground="#6272A4") # Greyish Blue
            text_widget.tag_config("tag_bullet", foreground="#F1FA8C") # Yellowish

            import re
            
            # Pattern: TIPO X (...) :
            # We look for "TIPO" followed by stuff until ":"
            for match in re.finditer(r"^(TIPO [A-Z0-9]+).+?:", full_text, re.MULTILINE):
                # Color the "TIPO X" part
                start = f"1.0 + {match.start()} chars"
                end = f"1.0 + {match.end()} chars"
                text_widget.tag_add("tag_prefix", start, end)

            # Pattern: parenthesis content (e.g. "La Advertencia")
            for match in re.finditer(r"\(.*?\)", full_text):
                text_widget.tag_add("tag_paren", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

            # Pattern: Simple Bullet "-" or "*" at start
            for match in re.finditer(r"^[\-\*]\s", full_text, re.MULTILINE):
                 text_widget.tag_add("tag_bullet", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

        except Exception as e:
            print(e)

    def select_category(self, category):
        # Update Nav visuals
        for key, btn in self.nav_buttons.items():
            if key == category:
                btn.configure(fg_color="#222", text_color="#FFF", border_color="#333")
            else:
                btn.configure(fg_color="transparent", text_color="#AAA", border_color=COLOR_SIDEBAR)
        
        # Update Header
        info = CATEGORIES[category]
        self.lbl_category_title.configure(text=f"{info['icon']} {category}")
        self.lbl_category_desc.configure(text=info['desc'])
        
        # Show/Hide Editors
        for key, widgets in self.editors.items():
            if key == category:
                widgets["frame"].pack(fill="both", expand=True)
            else:
                widgets["frame"].pack_forget()

    def save_all(self):
        try:
            total_items = 0
            for key, data in CATEGORIES.items():
                widget = self.editors[key]["textbox"]
                raw_text = widget.get("0.0", "end").strip()
                
                # Filter empty lines
                clean_list = [line.strip() for line in raw_text.split("\n") if line.strip()]
                
                # Update memory
                # We need to clear the list inplace and extend to keep references if any
                target_list = getattr(prompts_utils, data["var_name"])
                target_list.clear()
                target_list.extend(clean_list)
                
                total_items += len(clean_list)

            # Persist to disk (assuming prompts_utils has this method from previous files)
            if hasattr(prompts_utils, 'save_narrative_vars'):
                prompts_utils.save_narrative_vars()
                self.lbl_info_save.configure(text=f"✅ Guardado exitoso ({total_items} elementos)", text_color=COLOR_ACCENT)
                self.btn_save.configure(text="✅ MATRIZ ACTUALIZADA")
                self.after(2000, lambda: self.btn_save.configure(text="💾  GUARDAR MATRIZ"))
            else:
                self.lbl_info_save.configure(text="Error: Método de guardado no encontrado", text_color="red")
                
        except Exception as e:
            self.lbl_info_save.configure(text=f"Error: {str(e)}", text_color="red")
            print(e)
