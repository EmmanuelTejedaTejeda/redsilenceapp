import json
import os
import time
from datetime import datetime

class ProjectManager:
    def __init__(self, projects_dir="projects"):
        self.projects_dir = projects_dir
        if not os.path.exists(self.projects_dir):
            os.makedirs(self.projects_dir)
            
        self.current_project_id = None
        self.autosave_interval = 30 # seconds
        
        # Ejecutar migración automática al iniciar
        self.migrate_old_projects()

    def migrate_old_projects(self):
        """
        Migra automáticamente los archivos .json sueltos en projects/ a la nueva
        estructura de carpetas projects/<project_id>/state.json y traslada
        sus correspondientes carpetas de doblajes a projects/<project_id>/dubs/.
        """
        if not os.path.exists(self.projects_dir):
            return
            
        # 1. Primera pasada: Migrar archivos .json sueltos
        for f in os.listdir(self.projects_dir):
            if f.endswith(".json") and os.path.isfile(os.path.join(self.projects_dir, f)):
                project_id = f.replace(".json", "")
                old_json_path = os.path.join(self.projects_dir, f)
                new_project_dir = os.path.join(self.projects_dir, project_id)
                
                os.makedirs(new_project_dir, exist_ok=True)
                new_json_path = os.path.join(new_project_dir, "state.json")
                
                try:
                    os.rename(old_json_path, new_json_path)
                    print(f">>> [MIGRACIÓN] Archivo de estado migrado: {old_json_path} -> {new_json_path}")
                except Exception as e:
                    print(f">>> [MIGRACIÓN ERROR] Fallo al migrar proyecto {f}: {e}")
                    
        # 2. Segunda pasada: Escanear subcarpetas de proyectos para reubicar carpetas de doblajes sueltas
        for item in os.listdir(self.projects_dir):
            item_path = os.path.join(self.projects_dir, item)
            if os.path.isdir(item_path):
                state_file = os.path.join(item_path, "state.json")
                if os.path.exists(state_file):
                    try:
                        with open(state_file, "r", encoding="utf-8") as js_f:
                            js_data = json.load(js_f)
                            
                        # Extraer título por diferentes claves posibles de la sesión
                        media_data = js_data.get("media", {})
                        title = media_data.get("title") or media_data.get("meta_title") or media_data.get("meta_card_title") or ""
                        
                        if title:
                            safe_title = "".join([c for c in title if c.isalnum() or c==' ']).rstrip().replace(" ", "_")
                            if safe_title:
                                old_dubs_dir = os.path.join(self.projects_dir, safe_title)
                                # Verificar si existe la carpeta suelta en projects/
                                if os.path.exists(old_dubs_dir) and os.path.isdir(old_dubs_dir):
                                    new_dubs_dir = os.path.join(item_path, "dubs")
                                    if not os.path.exists(new_dubs_dir):
                                        os.rename(old_dubs_dir, new_dubs_dir)
                                        print(f">>> [MIGRACIÓN] Carpeta de doblajes migrada: {old_dubs_dir} -> {new_dubs_dir}")
                                    else:
                                        # Si ya existe por algún motivo, eliminar la suelta para limpiar
                                        try:
                                            import shutil
                                            shutil.rmtree(old_dubs_dir)
                                            print(f">>> [MIGRACIÓN] Eliminada carpeta duplicada suelta: {old_dubs_dir}")
                                        except: pass
                    except Exception as je:
                        print(f">>> [MIGRACIÓN DETAILS ERROR] No se pudieron mover doblajes antiguos para {item}: {je}")

        # 3. Tercera pasada: Migración de caché de videos_largos de projects/ a cache/
        old_videos_largos = os.path.join(self.projects_dir, "videos_largos")
        if os.path.exists(old_videos_largos) and os.path.isdir(old_videos_largos):
            new_videos_largos = os.path.join("cache", "videos_largos")
            os.makedirs(new_videos_largos, exist_ok=True)
            for item in os.listdir(old_videos_largos):
                old_item_path = os.path.join(old_videos_largos, item)
                new_item_path = os.path.join(new_videos_largos, item)
                if os.path.isdir(old_item_path):
                    # Si ya existe el destino, mover subcarpetas
                    if os.path.exists(new_item_path):
                        old_chunks = os.path.join(old_item_path, "chunks")
                        new_chunks = os.path.join(new_item_path, "chunks")
                        if os.path.exists(old_chunks):
                            os.makedirs(new_chunks, exist_ok=True)
                            for file in os.listdir(old_chunks):
                                old_f = os.path.join(old_chunks, file)
                                new_f = os.path.join(new_chunks, file)
                                try:
                                    if not os.path.exists(new_f):
                                        os.rename(old_f, new_f)
                                except Exception as e:
                                    print(f">>> [MIGRACIÓN CACHE ERROR] Fallo al mover chunk {file}: {e}")
                        try:
                            import shutil
                            shutil.rmtree(old_item_path)
                        except: pass
                    else:
                        try:
                            os.rename(old_item_path, new_item_path)
                            print(f">>> [MIGRACIÓN] Caché de video largo migrada: {old_item_path} -> {new_item_path}")
                        except Exception as e:
                            print(f">>> [MIGRACIÓN CACHE ERROR] Fallo al mover {item}: {e}")
            try:
                os.rmdir(old_videos_largos)
                print(f">>> [MIGRACIÓN] Carpeta vacía projects/videos_largos eliminada.")
            except Exception as e:
                print(f">>> [MIGRACIÓN] No se pudo eliminar projects/videos_largos: {e}")

    def create_project(self, title):
        # Sanitize title for filename
        clean_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not clean_title:
            clean_title = "Untitled_Project"
            
        self.current_project_id = f"{timestamp}_{clean_title.replace(' ', '_')}"
        
        # Crear la carpeta de inmediato para estructuración
        os.makedirs(os.path.join(self.projects_dir, self.current_project_id), exist_ok=True)
        return self.current_project_id

    def save_project(self, data, project_id=None):
        if not project_id:
            if not self.current_project_id:
                self.create_project("AutoSave")
            project_id = self.current_project_id
            
        project_dir = os.path.join(self.projects_dir, project_id)
        os.makedirs(project_dir, exist_ok=True)
        filepath = os.path.join(project_dir, "state.json")
        
        # Metadata
        data["_last_modified"] = datetime.now().isoformat()
        data["_version"] = "1.0"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return filepath
        except Exception as e:
            print(f"Error saving project: {e}")
            return None

    def load_project(self, project_id):
        filepath = os.path.join(self.projects_dir, project_id, "state.json")
        if not os.path.exists(filepath):
            # Fallback de compatibilidad por si acaso
            old_filepath = os.path.join(self.projects_dir, f"{project_id}.json")
            if os.path.exists(old_filepath):
                filepath = old_filepath
            else:
                return None
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading project: {e}")
            return None

    def list_projects(self):
        projects = []
        if not os.path.exists(self.projects_dir):
            return []
            
        # Escanear subcarpetas que tengan un archivo state.json
        for item in os.listdir(self.projects_dir):
            item_path = os.path.join(self.projects_dir, item)
            if os.path.isdir(item_path):
                state_file = os.path.join(item_path, "state.json")
                if os.path.exists(state_file):
                    projects.append(item)
        
        # Ordenar por tiempo de modificación del state.json (más reciente primero)
        def get_mtime(proj_id):
            p = os.path.join(self.projects_dir, proj_id, "state.json")
            return os.path.getmtime(p) if os.path.exists(p) else 0
            
        projects.sort(key=get_mtime, reverse=True)
        return projects

    def get_latest_project(self):
        lst = self.list_projects()
        return lst[0] if lst else None
