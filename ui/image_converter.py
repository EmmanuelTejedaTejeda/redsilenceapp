import os
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

# --- THEME CONSTANTS ---
COLOR_BG = "#080808"
COLOR_SIDEBAR = "#101010"
COLOR_ACCENT = "#D32F2F"
COLOR_ACCENT_HOVER = "#FF1744"
COLOR_TEXT_MAIN = "#FFFFFF"

class ImageConverter(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("CONVERSOR DE IMÁGENES (PNG -> JPEG) | SILENCIO ROJO")
        self.geometry("700x500")
        self.configure(fg_color=COLOR_BG)
        
        from core.utils import force_focus
        force_focus(self)
        
        self.selected_files = []
        
        self.init_ui()
        
    def init_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(header, text="CONVERSOR DE IMÁGENES", font=("Impact", 28), text_color=COLOR_TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(header, text="Selecciona múltiples imágenes PNG y conviértelas a JPEG de alta calidad con un clic.", font=("Arial", 12), text_color="#888").pack(anchor="w")
        
        # Tools
        tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        tools_frame.pack(fill="x", padx=20, pady=10)
        
        btn_select = ctk.CTkButton(tools_frame, text="SELECCIONAR ARCHIVOS 📂", 
                                   fg_color="#222", hover_color="#333", command=self.select_files)
        btn_select.pack(side="left", padx=(0, 10))
        
        self.btn_convert = ctk.CTkButton(tools_frame, text="CONVERTIR A JPEG ⚙️", 
                                    fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.convert_files)
        self.btn_convert.pack(side="left")
        self.btn_convert.configure(state="disabled")
        
        # List context
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="#101010", border_width=1, border_color="#222")
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.status_lbl = ctk.CTkLabel(self, text="Esperando archivos...", font=("Consolas", 12), text_color="#888")
        self.status_lbl.pack(pady=10)
        
        # Start with empty list message
        self.update_list()
        
    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Seleccionar imágenes PNG",
            filetypes=[("PNG Images", "*.png"), ("All Files", "*.*")]
        )
        if files:
            # self.attributes("-topmost", False)  # Not needed if we don't anchor it
            
            raw_pngs = [f for f in files if f.lower().endswith('.png')]
            
            # Natural sort to keep sequence order like "img1", "img2", ..., "img10"
            def natural_sort_key(s):
                return [int(text) if text.isdigit() else text.lower()
                        for text in re.split('([0-9]+)', s)]
                        
            self.selected_files = sorted(raw_pngs, key=natural_sort_key)
            
            self.update_list()
            self.status_lbl.configure(text=f"{len(self.selected_files)} archivos PNG seleccionados.")
            if self.selected_files:
                self.btn_convert.configure(state="normal")
            # self.attributes("-topmost", True) # REMOVED: Don't lock it
            
    def update_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
            
        if not self.selected_files:
            ctk.CTkLabel(self.list_frame, text="No hay archivos seleccionados.", text_color="#444").pack(pady=20)
            return
            
        for f in self.selected_files:
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            fname = os.path.basename(f)
            ctk.CTkLabel(row, text="🖼️", width=30).pack(side="left")
            ctk.CTkLabel(row, text=fname, font=("Consolas", 12), text_color="#AAA").pack(side="left", padx=10)
            
    def convert_files(self):
        if not self.selected_files:
            return
            
        success_count = 0
        error_count = 0
        
        self.btn_convert.configure(state="disabled", text="CONVIRTIENDO...")
        self.update()
        
        for file_path in self.selected_files:
            try:
                img = Image.open(file_path)
                
                # Convert to RGB (JPEG doesn't support transparency)
                if img.mode in ('RGBA', 'P', 'LA'):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    try:
                        bg.paste(img, mask=img.split()[-1]) # Alpha channel is usually last
                    except Exception:
                        bg.paste(img)
                    img = bg
                else:
                    img = img.convert('RGB')
                    
                output_path = os.path.splitext(file_path)[0] + ".jpg"
                img.save(output_path, "JPEG", quality=95)
                success_count += 1
            except Exception as e:
                print(f"Error procesando {file_path}: {e}")
                error_count += 1
                
        self.status_lbl.configure(text=f"Conversión completa. {success_count} convertidos, {error_count} errores.")
        self.btn_convert.configure(state="normal", text="CONVERTIR A JPEG ⚙️")
        
        # self.attributes("-topmost", False) # REMOVED
        messagebox.showinfo("Proceso Terminado", f"Conversión Finalizada.\nÉxitos: {success_count}\nErrores: {error_count}\nLas imágenes se han guardado en la misma ruta original.")
        
        self.selected_files = []
        self.update_list()
        self.btn_convert.configure(state="disabled")
        # self.attributes("-topmost", True) # REMOVED
