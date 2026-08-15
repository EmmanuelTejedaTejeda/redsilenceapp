import os
import json
import asyncio
import aiofiles
from typing import Dict, List, Optional
from pydantic import BaseModel

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
    print(f"[{channel_name or 'GLOBAL'}] {message}")
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
    voice_name: Optional[str] = "Fritz-PlayAI"
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


class SynthesizeVoiceRequest(BaseModel):
    script_text: str
    voice_name: str
    channel_name: str


class TitleDescriptionRequest(BaseModel):
    story: str
    ai_engine: Optional[str] = "Groq (Llama 3)"
    channel_name: str

class GenerateTimelineRequest(BaseModel):
    trama: str
    script: str
    channel_name: str
    audio_duration: float
    intercalar_gameplay: bool
