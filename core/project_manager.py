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

    def create_project(self, title):
        # Sanitize title for filename
        clean_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not clean_title:
            clean_title = "Untitled_Project"
            
        self.current_project_id = f"{timestamp}_{clean_title.replace(' ', '_')}"
        return self.current_project_id

    def save_project(self, data, project_id=None):
        if not project_id:
            if not self.current_project_id:
                self.create_project("AutoSave")
            project_id = self.current_project_id
            
        filepath = os.path.join(self.projects_dir, f"{project_id}.json")
        
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
        filepath = os.path.join(self.projects_dir, f"{project_id}.json")
        if not os.path.exists(filepath):
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
            
        for f in os.listdir(self.projects_dir):
            if f.endswith(".json"):
                projects.append(f.replace(".json", ""))
        
        # Sort by modification time (newest first)
        projects.sort(key=lambda x: os.path.getmtime(os.path.join(self.projects_dir, x + ".json")), reverse=True)
        return projects

    def get_latest_project(self):
        lst = self.list_projects()
        return lst[0] if lst else None
