import customtkinter as ctk

# --- THEME CONSTANTS ---
COLOR_BG = "#0D0D0D"
COLOR_SIDEBAR = "#141414"
COLOR_EDITOR = "#1A1A1A"
COLOR_ACCENT = "#D32F2F"
COLOR_ACCENT_HOVER = "#B71C1C"
COLOR_TEXT_MAIN = "#E0E0E0"
COLOR_TEXT_DIM = "#888888"
COLOR_BORDER = "#2A2A2A"

FONT_HEADER = ("Impact", 28)
FONT_MONO = ("Consolas", 13)

class VisualPromptViewer(ctk.CTkToplevel):
    def __init__(self, parent, prompt_text):
        super().__init__(parent)
        
        self.title("VISOR DE PROMPTS VISUALES | SILENCIO ROJO")
        self.geometry("1100x800")
        self.configure(fg_color=COLOR_BG)
        
        try:
            self.state('zoomed') 
        except:
            self.attributes("-fullscreen", True) # Fallback
            
        from core.utils import force_focus
        force_focus(self)
        
        self.prompt_text = prompt_text
        self.prompts = []
        
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Header
        self.grid_rowconfigure(1, weight=1) # Content

        self.setup_ui()
        self.parsed_items = self.parse_prompts()
        self.populate_list()

    def setup_ui(self):
        # --- HEADER ---
        header_frame = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, height=80, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")
        
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=30, pady=20)
        
        ctk.CTkLabel(title_box, text="MOTOR VISUAL", font=("Impact", 32), text_color=COLOR_ACCENT).pack(anchor="w")
        ctk.CTkLabel(title_box, text="LISTA DE PROMPTS GENERADOS (MIDJOURNEY / DALL-E)", font=("Arial", 11, "bold"), text_color="#555").pack(anchor="w")

        # Global Actions
        action_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        action_box.pack(side="right", padx=30)
        
        self.btn_copy_all = ctk.CTkButton(action_box, text="COPIAR TODO 📋", 
                                          font=("Arial", 12, "bold"), 
                                          fg_color="#333", hover_color="#444", 
                                          width=140, height=40,
                                          command=self.copy_all)
        self.btn_copy_all.pack(side="right")

        # --- CONTENT AREA (Scrollable List) ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)

    def parse_prompts(self):
        # Improved parsing logic: Line-by-Line with Regex lookahead
        import re
        
        raw_text = self.prompt_text
        lines = raw_text.split('\n')
        
        parsed_items = []
        current_content = []
        current_type = "INFO" # Default start
        
        def commit_block():
            if current_content:
                full_text = "\n".join(current_content).strip()
                if full_text:
                    parsed_items.append({
                        "type": current_type,
                        "content": full_text
                    })
        
        for line in lines:
            s_line = line.strip()
            if not s_line: 
                continue # Skip empty lines for cleaner blocks, or append? better skip to avoid noise
            
            # Check for new Prompt pattern: "1:", "1.", "Imagen 1:"
            # Regex: Start with digit + dot/colon OR "Imagen" + digit
            is_new_prompt = re.match(r'^(\d+[:\.]|Imagen \d+|Prompt \d+)', s_line, re.IGNORECASE)
            
            # Check for Metadata
            is_metadata = "VARIABLE DE ENTIDAD" in s_line or "CONTEXTO:" in s_line
            
            if is_new_prompt:
                # Commit previous
                commit_block()
                # Start new
                current_type = "PROMPT"
                current_content = [s_line] # Start with this line
                
            elif is_metadata:
                # Commit previous
                commit_block()
                # Start new
                current_type = "INFO"
                current_content = [s_line]
                
            else:
                # Continuation of current block
                current_content.append(s_line)
                
        # Commit last block
        commit_block()
            
        return parsed_items



    def populate_list(self):
        # Clear
        for widget in self.scroll_frame.winfo_children(): 
            widget.destroy()

        if not self.parsed_items:
            self.create_prompt_card(1, self.prompt_text, "RAW TEXT")
            return

        # Start incremental population to keep UI responsive
        self._items_to_add = self.parsed_items.copy()
        self._current_index = 0
        self._add_next_chunk()

    def _add_next_chunk(self):
        """Adds a small batch of cards and schedules the next batch."""
        if not hasattr(self, "_items_to_add") or not self._items_to_add:
            return

        # Add 3 items per frame
        for _ in range(3):
            if not self._items_to_add:
                break
            
            item = self._items_to_add.pop(0)
            self._current_index += 1
            
            label = "VISUAL PROMPT" if item["type"] == "PROMPT" else "CONTEXT / INFO"
            clean_content = item["content"].replace("**", "").replace("##", "")
            self.create_prompt_card(self._current_index, clean_content, label)
            
        # Schedule next chunk if there are items left
        if self._items_to_add:
            self.after(10, self._add_next_chunk)

    def create_prompt_card(self, index, text, label_type):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_EDITOR, corner_radius=8, border_width=1, border_color="#333")
        card.pack(fill="x", pady=(0, 10), padx=5)
        
        # Grid Layout
        card.grid_columnconfigure(0, weight=0, minsize=50) # Index
        card.grid_columnconfigure(1, weight=1)             # Text
        card.grid_columnconfigure(2, weight=0, minsize=100)# Button
        
        # 1. Index / Icon
        icon = "🎨" if label_type == "VISUAL PROMPT" else "ℹ️"
        color = COLOR_ACCENT if label_type == "VISUAL PROMPT" else "#444"
        
        box_idx = ctk.CTkFrame(card, fg_color="transparent", width=50)
        box_idx.grid(row=0, column=0, sticky="ns", padx=5)
        
        ctk.CTkLabel(box_idx, text=f"{index}", font=("Impact", 18), text_color="#555").pack(pady=(10,0))
        ctk.CTkLabel(box_idx, text=icon, font=("Arial", 14)).pack()

        # 2. Content
        box_content = ctk.CTkFrame(card, fg_color="transparent")
        box_content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Badge
        bs = ctk.CTkLabel(box_content, text=label_type, font=("Arial", 8, "bold"), 
                          text_color=color, fg_color="#111", corner_radius=4)
        bs.pack(anchor="w", pady=(0, 5))
        
        # Text
        # Using Entry instead of Textbox for single lines, or Textbox for multi
        h = 60 if len(text) > 100 else 40
        txt = ctk.CTkTextbox(box_content, height=h, fg_color="#111", text_color="#DDD", font=("Consolas", 11), wrap="word")
        txt.insert("0.0", text)
        txt.configure(state="disabled")
        txt.pack(fill="x")

        # 3. Copy Button
        # Pass CARD reference to dim it
        btn = ctk.CTkButton(card, text="COPIAR", width=80, height=30, 
                            fg_color="#222", hover_color="#333", border_color="#444", border_width=1,
                            font=("Arial", 10, "bold"))
        btn.grid(row=0, column=2, padx=10)
        
        # Configure command with ALL references needed for visual update
        btn.configure(command=lambda c=card, b=btn, t=text, tb=txt: self.copy_text(t, b, c, tb))

    def copy_text(self, text, btn, card, textbox):
        from core.utils import copy_to_clipboard_persistent
        copy_to_clipboard_persistent(text)
        # self.update() # REMOVED: Causes lag on Windows
        
        # Visual Feedback: Mark as VISITED/COPIED but keep accessible
        if btn:
            # Change style to indicate success but stay clickable
            btn.configure(text="COPIADO ✔", fg_color="#1B5E20", text_color="white", border_color="#2E7D32", state="normal")
        
        if card:
            # Highlight the card with a subtle green tint and border
            card.configure(fg_color="#091409", border_color="#00C853", border_width=1)
            
        if textbox:
            # Keep text readable, just maybe standard color or slightly brighter to show focus?
            # Actually, let's keep it standard.
            textbox.configure(text_color="#EEE")




    def copy_all(self):
        from core.utils import copy_to_clipboard_persistent
        copy_to_clipboard_persistent(self.prompt_text)
        # self.update() # REMOVED
        
        self.btn_copy_all.configure(text="✅ COPIADO TODO", fg_color=COLOR_SUCCESS)
        # Global copy can revert, but individual ones should probably stay marked if that's the workflow
        self.after(2000, lambda: self.btn_copy_all.configure(text="COPIAR TODO 📋", fg_color="#333"))

COLOR_SUCCESS = "#00C853"
