import os
import sys
import json
import re
import shutil
import asyncio
import aiofiles
from typing import Dict, List, Optional
from pydantic import BaseModel

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

SETTINGS_PATH = os.path.join("config", "settings.json")
GROQ_SETTINGS_PATH = os.path.join("config", "groq_settings.json")

# Diccionario de colas SSE para eventos de progreso en tiempo real por canal
PROGRESS_QUEUES: Dict[str, List[asyncio.Queue]] = {}


def get_settings():
    if not os.path.exists(SETTINGS_PATH):
        return {"active_channel": None, "channels": []}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active_channel": None, "channels": []}

async def get_settings_async():
    if not os.path.exists(SETTINGS_PATH):
        return {"active_channel": None, "channels": []}
    try:
        async with aiofiles.open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    except Exception:
        return {"active_channel": None, "channels": []}

def save_settings(data):
    os.makedirs("config", exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def save_settings_async(data):
    os.makedirs("config", exist_ok=True)
    async with aiofiles.open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, indent=4, ensure_ascii=False))


def sanitize_channel_name(channel_name: Optional[str]) -> str:
    if not channel_name or not str(channel_name).strip():
        return "Canal_General"
    clean_name = re.sub(r'[/\\:*?"<>|]', '_', str(channel_name).strip())
    clean_name = clean_name.strip('. ')
    return clean_name or "Canal_General"


def get_channel_paths(channel_name: Optional[str] = None, settings: dict = None) -> dict:
    """
    Devuelve un diccionario con las rutas absolutas aisladas para un canal específico.
    Si el canal tiene carpetas personalizadas en su objeto, las respeta; de lo contrario,
    usa las rutas aisladas 'projects/channels/{clean_ch}/...'.
    """
    if settings is None:
        settings = get_settings()
        
    active_ch = channel_name or settings.get("active_channel") or "Canal_General"
    clean_ch = sanitize_channel_name(active_ch)
    
    base_channel_dir = os.path.abspath(os.path.join("projects", "channels", clean_ch))
    
    # Buscar el objeto del canal específico
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c.get("name", "").lower() == active_ch.lower()), None)
    ch_folders = ch_info.get("folders", {}) if ch_info else {}
    
    cust_audio = ch_folders.get("audio_folder_path")
    cust_music = ch_folders.get("music_folder_path")
    cust_images = ch_folders.get("images_folder_path")
    cust_videos = ch_folders.get("videos_folder_path")
    cust_renders = ch_folders.get("renders_folder_path")
    cust_downloader = ch_folders.get("downloader_folder_path")
    
    audio_dir = os.path.abspath(cust_audio) if cust_audio else os.path.join(base_channel_dir, "audio")
    music_dir = os.path.abspath(cust_music) if cust_music else os.path.join("assets", "audio", "music")
    images_dir = os.path.abspath(cust_images) if cust_images else os.path.join("assets", "images")
    videos_dir = os.path.abspath(cust_videos) if cust_videos else os.path.join("assets", "videos")
    renders_dir = os.path.abspath(cust_renders) if cust_renders else os.path.join(base_channel_dir, "renders")
    downloader_dir = os.path.abspath(cust_downloader) if cust_downloader else os.path.join(base_channel_dir, "downloader")
    cache_dir = os.path.join(base_channel_dir, "cache")
    config_dir = os.path.join(base_channel_dir, "config")
    prompts_dir = os.path.abspath(os.path.join("config", "prompts", "story", clean_ch))
    
    paths = {
        "channel_name": active_ch,
        "clean_channel_name": clean_ch,
        "channel_dir": base_channel_dir,
        "audio": audio_dir,
        "music": music_dir,
        "images": images_dir,
        "videos": videos_dir,
        "renders": renders_dir,
        "downloader": downloader_dir,
        "cache": cache_dir,
        "cache_audio": os.path.join(cache_dir, "audio"),
        "cache_gameplays": os.path.join(cache_dir, "gameplays"),
        "cache_ass": os.path.join(cache_dir, "ass"),
        "cache_chunks": os.path.join(cache_dir, "chunks"),
        "cache_json": os.path.join(cache_dir, "json"),
        "config": config_dir,
        "metadata_file": os.path.join(config_dir, "generation_metadata.json"),
        "prompts": prompts_dir
    }
    
    for key, path_val in paths.items():
        if key in ("channel_name", "clean_channel_name", "metadata_file"):
            continue
        os.makedirs(path_val, exist_ok=True)
        
    os.makedirs(os.path.dirname(paths["metadata_file"]), exist_ok=True)
    return paths


def migrate_legacy_files_if_needed(channel_name: str):
    """
    Migra archivos antiguos planos a la nueva estructura aislada del canal dado para no perder datos.
    """
    try:
        paths = get_channel_paths(channel_name)
        
        # 1. Migrar audios de cache/audio a la carpeta audio del canal
        legacy_audio = os.path.abspath(os.path.join("cache", "audio"))
        if os.path.exists(legacy_audio) and legacy_audio != os.path.abspath(paths["audio"]):
            for f in os.listdir(legacy_audio):
                src = os.path.join(legacy_audio, f)
                dst = os.path.join(paths["audio"], f)
                if os.path.isfile(src) and not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
                        
        # 2. Migrar renders de projects/renders a la carpeta renders del canal
        legacy_renders = os.path.abspath(os.path.join("projects", "renders"))
        if os.path.exists(legacy_renders) and legacy_renders != os.path.abspath(paths["renders"]):
            for f in os.listdir(legacy_renders):
                src = os.path.join(legacy_renders, f)
                dst = os.path.join(paths["renders"], f)
                if os.path.isfile(src) and not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
                        
        # 3. Migrar metadatos antiguos de config/cache/generation_metadata.json
        legacy_meta = os.path.abspath(os.path.join("config", "cache", "generation_metadata.json"))
        if os.path.exists(legacy_meta) and not os.path.exists(paths["metadata_file"]):
            try:
                shutil.copy2(legacy_meta, paths["metadata_file"])
            except Exception:
                pass
    except Exception as e:
        print(f"[MIGRATION WARNING] Error migrando archivos legacy: {e}")


def get_groq_api_key():
    if os.path.exists(GROQ_SETTINGS_PATH):
        try:
            with open(GROQ_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("groq_api_key") or data.get("api_key", "")
        except Exception:
            pass
    return os.environ.get("GROQ_API_KEY", "")


def get_gemini_api_key():
    try:
        settings = get_settings()
        return settings.get("google_api_key", "")
    except Exception:
        return ""


def log_progress(channel_name: str, message: str, color: str = "#ffffff", percentage: int = None, output_path: str = None):
    """
    Envía mensajes de estado y porcentaje a los clientes SSE conectados para un canal dado.
    """
    import time
    try:
        print(f"[{channel_name or 'GLOBAL'}] {message}")
    except Exception:
        try:
            clean_msg = message.encode('ascii', errors='replace').decode('ascii')
            print(f"[{channel_name or 'GLOBAL'}] {clean_msg}")
        except Exception:
            pass
    if not channel_name:
        channel_name = "GLOBAL"
        
    if channel_name in PROGRESS_QUEUES:
        payload = {
            "message": message,
            "status": message,
            "color": color,
            "timestamp": time.time()
        }
        if percentage is not None:
            payload["percentage"] = percentage
        if output_path:
            payload["output_path"] = output_path
            
        data_str = json.dumps(payload)
        for q in PROGRESS_QUEUES[channel_name]:
            try:
                q.put_nowait(data_str)
            except Exception:
                pass


# --- MODELOS PYDANTIC COMPARTIDOS ---
class ChannelCreateRequest(BaseModel):
    name: str
    theme: str
    language: Optional[str] = "es"
    theme_color: Optional[str] = "#e50914"

class FolderSettingsRequest(BaseModel):
    audio_folder_path: Optional[str] = ""
    music_folder_path: Optional[str] = ""
    images_folder_path: Optional[str] = ""
    videos_folder_path: Optional[str] = ""
    renders_folder_path: Optional[str] = ""
    downloader_folder_path: Optional[str] = ""


class ChannelThemeRequest(BaseModel):
    theme: str
    language: Optional[str] = "es"
    theme_color: Optional[str] = "#e50914"


class MasterPromptItem(BaseModel):
    id: Optional[str] = None
    title: str
    category: str
    prompt: str


class GenerateRequest(BaseModel):
    channel_name: str
    prompt_title: Optional[str] = None
    custom_prompt: Optional[str] = None
    music_name: Optional[str] = "Ninguno"
    sub_style: Optional[str] = "Reddit History"
    render_quality: Optional[str] = "720p (Balanceado)"
    bg_source: Optional[str] = "Minecraft Parkour"
    ai_engine: Optional[str] = "Groq (Llama 3)"
    narration_file: Optional[str] = None
    video_title: Optional[str] = None
    enable_subtitles: Optional[bool] = False


class ScriptGenerationRequest(BaseModel):
    channel_name: str
    prompt_title: str
    custom_instructions: Optional[str] = None
    ai_engine: Optional[str] = "Groq (Llama 3)"


class DownloaderUrlRequest(BaseModel):
    url: str
    channel_name: str
    clip_type: Optional[str] = "gameplay"
    duration: Optional[float] = 120.0


class DownloaderSearchRequest(BaseModel):
    query: str
    channel_name: str
    duration: Optional[float] = 120.0
    get_gameplay: Optional[bool] = True
    get_images: Optional[bool] = True
    get_gifs: Optional[bool] = True


class TitleDescriptionRequest(BaseModel):
    story: str
    ai_engine: Optional[str] = "Groq (Llama 3)"
    channel_name: str

class GenerateTimelineRequest(BaseModel):
    trama: str
    script: str
    channel_name: str
    audio_duration: float
    custom_keywords: Optional[List[str]] = None

