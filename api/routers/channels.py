import aiofiles
import os
import uuid
import glob
from typing import Optional
from fastapi import APIRouter, HTTPException
from api.deps import (
    get_settings, save_settings, get_settings_async, save_settings_async,
    ChannelCreateRequest, ChannelThemeRequest, MasterPromptItem,
    FolderSettingsRequest, get_channel_paths, migrate_legacy_files_if_needed
)

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.get("")
async def api_get_channels():
    settings = await get_settings_async()
    active_channel = settings.get("active_channel")
    if active_channel:
        migrate_legacy_files_if_needed(active_channel)
        get_channel_paths(active_channel, settings)
    return {
        "active_channel": active_channel,
        "channels": settings.get("channels", [])
    }


@router.get("/folders")
async def api_get_folder_settings(channel_name: Optional[str] = None):
    settings = await get_settings_async()
    target_channel = channel_name or settings.get("active_channel") or "Canal_General"
    paths = get_channel_paths(target_channel, settings)
    
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c.get("name", "").lower() == target_channel.lower()), None)
    ch_folders = ch_info.get("folders", {}) if ch_info else {}

    return {
        "channel_name": target_channel,
        "audio_folder_path": ch_folders.get("audio_folder_path") or paths["audio"],
        "music_folder_path": ch_folders.get("music_folder_path") or paths["music"],
        "images_folder_path": ch_folders.get("images_folder_path") or paths["images"],
        "videos_folder_path": ch_folders.get("videos_folder_path") or paths["videos"],
        "renders_folder_path": ch_folders.get("renders_folder_path") or paths["renders"],
        "downloader_folder_path": ch_folders.get("downloader_folder_path") or paths["downloader"]
    }


@router.post("/folders")
async def api_save_folder_settings(req: FolderSettingsRequest):
    settings = await get_settings_async()
    active_ch = settings.get("active_channel") or "Canal_General"
    
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c.get("name", "").lower() == active_ch.lower()), None)
    if ch_info:
        if "folders" not in ch_info:
            ch_info["folders"] = {}
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        for k, v in data.items():
            if k.endswith("_folder_path") and v is not None:
                ch_info["folders"][k] = v
                
    await save_settings_async(settings)
    get_channel_paths(active_ch, settings)
    
    updated_folders = await api_get_folder_settings(active_ch)
    return {"status": "success", "settings": updated_folders}


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
        "language": req.language or "es",
        "theme_color": req.theme_color or "#e50914",
        "secret_path": secret_path,
        "master_prompts": []
    }
    
    channels.append(new_channel)
    settings["channels"] = channels
    if not settings.get("active_channel"):
        settings["active_channel"] = req.name
    await save_settings_async(settings)
    
    # Inicializar automáticamente las carpetas internas del nuevo canal
    get_channel_paths(req.name, settings)
    
    return {"status": "success", "channel": new_channel}


@router.post("/select")
async def api_select_channel(payload: dict):
    channel_name = payload.get("channel_name")
    settings = await get_settings_async()
    if not any(c["name"] == channel_name for c in settings.get("channels", [])):
        raise HTTPException(status_code=404, detail="El canal especificado no existe.")
    
    settings["active_channel"] = channel_name
    await save_settings_async(settings)
    
    # Ejecutar migración e inicialización de carpetas aisladas
    migrate_legacy_files_if_needed(channel_name)
    get_channel_paths(channel_name, settings)
    
    return {"status": "success", "active_channel": channel_name}


@router.put("/{channel_name}/theme")
async def api_update_channel_theme(channel_name: str, req: ChannelThemeRequest):
    settings = await get_settings_async()
    channels = settings.get("channels", [])
    channel = next((c for c in channels if c["name"] == channel_name), None)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
        
    channel["theme"] = req.theme
    if req.language:
        channel["language"] = req.language
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
    return await api_get_channel_prompts(channel_name)


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
            
    return await api_get_channel_prompts(channel_name)


import json
from api.deps import get_groq_api_key
from modules.groq_client import generate_content as generate_groq_content

@router.post("/{channel_name}/generate-story-prompt")
async def api_generate_story_prompt_for_channel(channel_name: str):
    groq_key = get_groq_api_key()
    if not groq_key:
        raise HTTPException(status_code=400, detail="API Key de Groq no configurada en Ajustes Generales.")

    # 1. Cargar Prompt Maestro Universal
    universal_path = os.path.join("config", "prompts", "story", "Prompt Maestro Universal.txt")
    if not os.path.exists(universal_path):
        raise HTTPException(status_code=404, detail="No se encontró el archivo 'Prompt Maestro Universal.txt' en config/prompts/story/")

    async with aiofiles.open(universal_path, "r", encoding="utf-8") as f:
        universal_content = await f.read()

    # 2. Determinar tema/nicho e idioma del canal
    settings = await get_settings_async()
    channels = settings.get("channels", [])
    channel_info = next((c for c in channels if c["name"].lower() == channel_name.lower()), None)
    channel_theme = channel_info.get("theme", "General") if channel_info else "General"
    channel_language = channel_info.get("language", "es") if channel_info else "es"

    meta_prompt = f"""Eres un experto Ingeniero de Prompts y estratega de contenido viral para YouTube Shorts y TikTok.
Tu tarea es transformar el siguiente PROMPT MAESTRO UNIVERSAL para adaptarlo 100% al nicho, estilo y temática del canal de YouTube '{channel_name}', cuyo nicho o estética es '{channel_theme}' y cuyo IDIOMA OBJETIVO ES '{channel_language}' (ej: 'es' = Español, 'en' = Inglés, 'fr' = Francés, 'de' = Alemán, 'pt' = Portugués).

INSTRUCCIONES DE TRANSFORMACIÓN:
1. Reemplaza todos los marcadores generales como {{TU_NICHO}}, {{PRIMERA/SEGUNDA_PERSONA}}, {{TESTIMONIO/CHISME/DOCUMENTAL/ETC}}, {{INSERTA_PALABRAS_CLAVE_DE_TU_NICHO}}, {{INSERTA_TUS_RESTRICCIONES_AQUÍ}}, etc., con datos concretos, atractivos y ultra-optimizados para el nicho '{channel_theme}'.
2. Adapta las REGLAS NARRATIVAS, la ESTRUCTURA DE GUION por tiempos (Gancho, Desarrollo, Controversia, CTA) y las PALABRAS CLAVE específicas para este nicho.
3. IDIOMA DE SALIDA: El resultado final DEBE estar redactado o adaptado explícitamente en el idioma '{channel_language}' para asegurar que todos los guiones creados con este prompt maestro se generen 100% en ese idioma.

FORMATO DE SALIDA (ESTRICTO):
La primera línea DEBE comenzar exactamente con:
TITULO: Prompt_Master_{channel_name.replace(' ', '_')}

A partir de la segunda línea, incluye ÚNICAMENTE el texto completo del Prompt Maestro adaptado. Sin introducciones, notas o bloques Markdown envolventes.

PROMPT MAESTRO UNIVERSAL DE ORIGEN:
{universal_content}"""

    try:
        response_text = generate_groq_content(meta_prompt, groq_key).strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar con Groq: {e}")

    lines = response_text.splitlines()
    title = f"Prompt_Master_{channel_name.replace(' ', '_')}"
    prompt_body = response_text

    if lines and lines[0].startswith("TITULO:"):
        extracted_title = lines[0].replace("TITULO:", "").strip()
        clean_title = "".join(c for c in extracted_title if c.isalnum() or c in ("_", "-")).strip()
        if clean_title:
            title = clean_title
        prompt_body = "\n".join(lines[1:]).strip()

    # Guardar el prompt resultante en la carpeta del canal
    prompts_dir = os.path.join("config", "prompts", "story", channel_name)
    os.makedirs(prompts_dir, exist_ok=True)
    file_path = os.path.join(prompts_dir, f"{title}.txt")

    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(prompt_body)

    updated_prompts = await api_get_channel_prompts(channel_name)
    return {
        "status": "success",
        "title": title,
        "prompt": prompt_body,
        "prompts": updated_prompts
    }


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
            theme_result = generate_groq_content(prompt, groq_key, model_name="openai/gpt-oss-120b").strip()
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

