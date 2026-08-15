import aiofiles
import os
import uuid
import glob
from typing import Optional
from fastapi import APIRouter, HTTPException
from api.deps import (
    get_settings, save_settings, get_settings_async, save_settings_async,
    ChannelCreateRequest, ChannelThemeRequest, MasterPromptItem,
    FolderSettingsRequest
)

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.get("")
async def api_get_channels():
    settings = await get_settings_async()
    return {
        "active_channel": settings.get("active_channel"),
        "channels": settings.get("channels", [])
    }


@router.get("/folders")
async def api_get_folder_settings():
    settings = await get_settings_async()
    return {
        "audio_folder_path": settings.get("audio_folder_path", ""),
        "music_folder_path": settings.get("music_folder_path", ""),
        "images_folder_path": settings.get("images_folder_path", ""),
        "videos_folder_path": settings.get("videos_folder_path", ""),
        "renders_folder_path": settings.get("renders_folder_path", ""),
        "downloader_folder_path": settings.get("downloader_folder_path", "")
    }


@router.post("/folders")
async def api_save_folder_settings(req: FolderSettingsRequest):
    settings = await get_settings_async()
    data = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    for k, v in data.items():
        if k.endswith("_folder_path") and v is not None:
            settings[k] = v
    await save_settings_async(settings)
    return {"status": "success", "settings": api_get_folder_settings()}


@router.post("")
async def api_create_channel(req: ChannelCreateRequest):
    settings = await get_settings_async()
    channels = settings.get("channels", [])
    
    if any(c["name"].lower() == req.name.lower() for c in channels):
        raise HTTPException(status_code=400, detail="Ya existe un canal con ese nombre.")
        
    secret_path = None
    cred_files = glob.glob(os.path.join("credenciales", "*.json"))
    if cred_files:
        secret_path = cred_files[0]
        
    new_channel = {
        "name": req.name,
        "theme": req.theme,
        "theme_color": req.theme_color or "#e50914",
        "secret_path": secret_path,
        "master_prompts": []
    }
    
    channels.append(new_channel)
    settings["channels"] = channels
    if not settings.get("active_channel"):
        settings["active_channel"] = req.name
    await save_settings_async(settings)
    
    return {"status": "success", "channel": new_channel}


@router.post("/select")
async def api_select_channel(payload: dict):
    channel_name = payload.get("channel_name")
    settings = await get_settings_async()
    if not any(c["name"] == channel_name for c in settings.get("channels", [])):
        raise HTTPException(status_code=404, detail="El canal especificado no existe.")
    
    settings["active_channel"] = channel_name
    await save_settings_async(settings)
    return {"status": "success", "active_channel": channel_name}


@router.put("/{channel_name}/theme")
async def api_update_channel_theme(channel_name: str, req: ChannelThemeRequest):
    settings = await get_settings_async()
    channels = settings.get("channels", [])
    channel = next((c for c in channels if c["name"] == channel_name), None)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
        
    channel["theme"] = req.theme
    if req.theme_color:
        channel["theme_color"] = req.theme_color
        
    await save_settings_async(settings)
    return {"status": "success", "channel": channel}


@router.delete("/{channel_name}")
async def api_delete_channel(channel_name: str):
    settings = await get_settings_async()
    channels = settings.get("channels", [])
    new_channels = [c for c in channels if c["name"] != channel_name]
    
    if len(new_channels) == len(channels):
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
        
    settings["channels"] = new_channels
    if settings.get("active_channel") == channel_name:
        settings["active_channel"] = new_channels[0]["name"] if new_channels else None
        
    await save_settings_async(settings)
    return {"status": "success", "active_channel": settings.get("active_channel")}


# --- PROMPTS MASTER POR CANAL ---
import glob
import uuid

@router.get("/{channel_name}/prompts")
async def api_get_channel_prompts(channel_name: str):
    prompts = []
    prompts_dir = os.path.join("config", "prompts", "story", channel_name)
    if os.path.exists(prompts_dir):
        for f in glob.glob(os.path.join(prompts_dir, "*.txt")):
            try:
                async with aiofiles.open(f, "r", encoding="utf-8") as file:
                    content = await file.read()
                    title = os.path.basename(f)[:-4] # remove .txt
                    prompts.append({
                        "id": title, # Usar el título como ID
                        "title": title,
                        "category": "Shorts",
                        "prompt": content
                    })
            except Exception as e:
                print(f"Error leyendo {f}: {e}")
    return prompts

@router.post("/{channel_name}/prompts")
async def api_save_channel_prompt(channel_name: str, item: MasterPromptItem):
    prompts_dir = os.path.join("config", "prompts", "story", channel_name)
    os.makedirs(prompts_dir, exist_ok=True)
    
    # El título servirá como nombre de archivo
    title = item.title.strip()
    if not title:
        title = "Nuevo_Prompt"
        
    file_path = os.path.join(prompts_dir, f"{title}.txt")
    
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(item.prompt)
        
    # Devolver la lista actualizada
    return api_get_channel_prompts(channel_name)


@router.delete("/{channel_name}/prompts/{prompt_id}")
async def api_delete_channel_prompt(channel_name: str, prompt_id: str):
    # prompt_id is the title in our new setup
    prompts_dir = os.path.join("config", "prompts", "story", channel_name)
    file_path = os.path.join(prompts_dir, f"{prompt_id}.txt")
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    return api_get_channel_prompts(channel_name)

import json
from api.deps import get_groq_api_key
from modules.groq_client import generate_content as generate_groq_content

@router.post("/generate-themes")
async def api_generate_themes():
    settings = await get_settings_async()
    channels = settings.get("channels", [])
    
    groq_key = get_groq_api_key()
    if not groq_key:
        raise HTTPException(status_code=400, detail="API Key de Groq no configurada.")
        
    themes = {}
    for ch in channels:
        channel_name = ch["name"]
        prompts_dir = os.path.join("config", "prompts", "story", channel_name)
        combined_text = ""
        
        if os.path.exists(prompts_dir):
            txt_files = glob.glob(os.path.join(prompts_dir, "*.txt"))
            for f in txt_files:
                try:
                    async with aiofiles.open(f, "r", encoding="utf-8") as file:
                        combined_text += file.read()[:500] + " "
                except:
                    pass
                    
        prompt = f"""You are a professional YouTube strategist. 
Based on these script writing instructions for the channel '{channel_name}', deduce the core visual aesthetic or theme of the channel in exactly 1 or 2 words (e.g. 'horror', 'finance', 'cyberpunk', 'meditation').
If there are no instructions provided, output 'general'.
ONLY output the 1-2 words. No quotes, no intro.

INSTRUCTIONS:
{combined_text[:1500]}"""

        try:
            theme_result = generate_groq_content(prompt, groq_key, model_name="llama-3.3-70b-versatile").strip()
            theme_result = theme_result.replace("\"", "").replace("'", "")
            if not theme_result or len(theme_result) > 30:
                theme_result = channel_name
            themes[channel_name] = theme_result
        except Exception as e:
            print(f"Error deducing theme for {channel_name}: {e}")
            themes[channel_name] = channel_name

    themes_path = os.path.join("config", "themes.json")
    async with aiofiles.open(themes_path, "w", encoding="utf-8") as f:
        json.dump(themes, f, indent=4)
        
    return {"status": "success", "themes": themes}
