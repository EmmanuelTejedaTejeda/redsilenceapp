import os
import glob
import re
import aiofiles
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from api.deps import (
    get_settings, DownloaderUrlRequest, DownloaderSearchRequest, log_progress, get_channel_paths
)
from modules.gameplay_sourcing import download_youtube_gameplay

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/music")
def api_get_music_files(channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    music_dir = paths["music"]
    if not os.path.exists(music_dir):
        music_dir = os.path.join("assets", "music")
    if not os.path.exists(music_dir):
        return ["Ninguno"]
    try:
        files = [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a'))]
        return ["Ninguno"] + files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo carpeta de música: {e}")


@router.get("/story-prompts")
def api_get_story_prompts(channel_name: Optional[str] = None):
    if channel_name:
        paths = get_channel_paths(channel_name)
        story_dir = paths["prompts"]
    else:
        story_dir = os.path.join("config", "prompts", "story")
    if not os.path.exists(story_dir):
        return []
    try:
        return [f for f in os.listdir(story_dir) if f.lower().endswith(".txt")]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo carpeta de prompts: {e}")


@router.get("/voice-prompts")
def api_get_voice_prompts():
    voice_dir = os.path.join("config", "prompts", "voice")
    if not os.path.exists(voice_dir):
        return []
    try:
        return [f for f in os.listdir(voice_dir) if f.lower().endswith(".txt")]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo carpeta de prompts de voz: {e}")


@router.get("/narrations")
def api_get_narration_files(channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    audio_dir = paths["audio"]
    clean_ch = paths["clean_channel_name"]
    
    dirs_to_check = []
    if os.path.exists(audio_dir):
        sub = os.path.join(audio_dir, clean_ch)
        if os.path.exists(sub):
            dirs_to_check.append(sub)
        dirs_to_check.append(audio_dir)
        
    settings = get_settings()
    global_audio = settings.get("audio_folder_path")
    if global_audio and os.path.exists(global_audio):
        sub = os.path.join(global_audio, clean_ch)
        if os.path.exists(sub) and sub not in dirs_to_check:
            dirs_to_check.append(sub)
        if global_audio not in dirs_to_check:
            dirs_to_check.append(global_audio)

    seen_files = set()
    result = []
    
    for d in dirs_to_check:
        try:
            for f in os.listdir(d):
                if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                    full_path = os.path.abspath(os.path.join(d, f))
                    if f not in seen_files:
                        seen_files.add(f)
                        try:
                            mtime = os.path.getmtime(full_path)
                        except Exception:
                            mtime = 0
                        result.append({"name": f, "path": full_path, "mtime": mtime})
        except Exception:
            continue
            
    result.sort(key=lambda x: x["mtime"], reverse=True)
    return [{"name": item["name"], "path": item["path"]} for item in result]


@router.get("/file-preview")
def api_get_file_preview(path: str):
    """
    Endpoint genérico para servir archivos locales (audios y videos) mediante rutas absolutas.
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(path)


# --- DOWNLOADER & GAMEPLAY SOURCING ---
def bg_download_gameplay(url_or_query: str, channel_name: str, duration: float = 120.0):
    paths = get_channel_paths(channel_name)
    
    # Directorios aislados del canal
    cache_dir = paths["cache_gameplays"]
    output_dir = paths["videos"]
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '', url_or_query[:30].replace(' ', '_').lower())
        
        local_video_path = None
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                if file.startswith(clean_name) and file.endswith(('.mp4', '.mkv', '.webm')):
                    candidate_path = os.path.join(cache_dir, file)
                    from modules.render_utils import get_video_duration
                    if get_video_duration(candidate_path) > 0.0:
                        local_video_path = candidate_path
                        break
                    else:
                        print(f"[CACHE] Eliminando archivo de gameplay corrupto/incompleto: {candidate_path}")
                        try:
                            os.remove(candidate_path)
                        except Exception as e:
                            print(f"[CACHE] Error al eliminar archivo corrupto: {e}")
                            
        if local_video_path and os.path.exists(local_video_path):
            log_progress(channel_name, "♻️ USANDO VIDEO DE GAMEPLAY EN CACHÉ LOCAL DEL CANAL", "#00FF66", 30)
        else:
            log_progress(channel_name, f"🌐 Descargando gameplay para '{url_or_query}'...", "#FFD700", 20)
            local_video_path = download_youtube_gameplay(
                url_or_query, 
                cache_dir, 
                status_callback=lambda msg, color: log_progress(channel_name, msg, color, 40)
            )
            
        if not local_video_path or not os.path.exists(local_video_path):
            log_progress(channel_name, "⚠️ Descarga fallida. Reintentando con búsqueda alternativa...", "orange", 50)
            fallback_query = "Minecraft parkour gameplay long no commentary"
            fallback_clean_name = "minecraft_parkour_gameplay_long_"
            
            for file in os.listdir(cache_dir):
                if file.startswith(fallback_clean_name) and file.endswith(('.mp4', '.mkv', '.webm')):
                    candidate_path = os.path.join(cache_dir, file)
                    from modules.render_utils import get_video_duration
                    if get_video_duration(candidate_path) > 0.0:
                        local_video_path = candidate_path
                        break
                    else:
                        print(f"[CACHE] Eliminando fallback de gameplay corrupto: {candidate_path}")
                        try:
                            os.remove(candidate_path)
                        except Exception as e:
                            print(f"[CACHE] Error al eliminar fallback corrupto: {e}")
            
            if not local_video_path:
                local_video_path = download_youtube_gameplay(
                    fallback_query, 
                    cache_dir, 
                    status_callback=lambda msg, color: log_progress(channel_name, msg, color, 60)
                )
                
        if local_video_path and os.path.exists(local_video_path):
            log_progress(channel_name, "✂️ Segmentando y re-encuadrando gameplay...", "#FF9100", 70)
            from modules.gameplay_sourcing import slice_video_segments
            
            clips = slice_video_segments(
                local_video_path, 
                duration, 
                output_dir, 
                aspect_ratio="9:16", 
                status_callback=lambda msg, color: log_progress(channel_name, msg, color, 85)
            )
            
            if clips:
                log_progress(channel_name, f"✅ Gameplay segmentado con éxito. {len(clips)} clips integrados.", "#00ff88", 100)
            else:
                log_progress(channel_name, "⚠️ Error segmentando clips. Se usará el video completo.", "orange", 100)
        else:
            raise Exception("No se pudo obtener ningún video de gameplay.")
            
    except Exception as e:
        log_progress(channel_name, f"❌ Error en descarga de fondo: {e}", "#ff4444", 0)


@router.post("/downloader/url")
def api_download_by_url(req: DownloaderUrlRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(bg_download_gameplay, req.url, req.channel_name, req.duration)
    return {"status": "success", "message": "Descarga de URL iniciada en segundo plano."}


def search_pexels_photos(query, api_key, limit=5, orientation="portrait"):
    import urllib.request
    import urllib.parse
    import json
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.pexels.com/v1/search?query={encoded_query}&orientation={orientation}&per_page={limit}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", api_key)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            photos = data.get("photos", [])
            return [p.get("src", {}).get("large") or p.get("src", {}).get("original") for p in photos if p.get("src")]
    except Exception as e:
        print(f"Error buscando fotos en Pexels: {e}")
        return []

def search_giphy_gifs(query, limit=5):
    import urllib.request
    import urllib.parse
    import json
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.giphy.com/v1/gifs/search?api_key=dc6zaTOxFJmzC&q={encoded_query}&limit={limit}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            gifs = data.get("data", [])
            return [g.get("images", {}).get("original", {}).get("url") for g in gifs if g.get("images")]
    except Exception as e:
        print(f"Error buscando GIFs en Giphy: {e}")
        return []

def download_file(url, output_path):
    import urllib.request
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"Error descargando recurso {url}: {e}")
        return False

def bg_download_resources(query: str, channel_name: str, duration: float, get_gameplay: bool, get_images: bool, get_gifs: bool):
    import random
    settings = get_settings()
    paths = get_channel_paths(channel_name, settings)
    video_dir = paths["videos"]
    image_dir = paths["images"]
    
    if get_gameplay:
        log_progress(channel_name, f"🎮 Buscando gameplay para: {query}...", "#FFD700", 10)
        bg_download_gameplay(query, channel_name, duration)
        
    if get_images:
        log_progress(channel_name, f"🖼️ Buscando imágenes sobre: {query}...", "#00E5FF", 40)
        pexels_key = settings.get("pexels_api_key")
        pixabay_key = settings.get("pixabay_api_key")
        
        image_urls = []
        if pexels_key:
            image_urls += search_pexels_photos(query, pexels_key, limit=4)
        if not image_urls and pixabay_key:
            try:
                from modules.pixabay_client import search_pixabay_photos
                photos = search_pixabay_photos(query, pixabay_key, limit=4)
                image_urls += [p["image"] for p in photos]
            except Exception as pe:
                print(f"Error con Pixabay client: {pe}")
                
        if image_urls:
            log_progress(channel_name, f"🖼️ Descargando {len(image_urls)} imágenes...", "#00E5FF", 60)
            downloaded = 0
            for idx, img_url in enumerate(image_urls):
                clean_q = re.sub(r'[^a-zA-Z0-9]', '_', query[:20].lower())
                filename = f"image_{clean_q}_{idx}_{random.randint(1000, 9999)}.jpg"
                filepath = os.path.join(image_dir, filename)
                if download_file(img_url, filepath):
                    downloaded += 1
            log_progress(channel_name, f"✅ Se descargaron {downloaded} imágenes del tema.", "#00FF66", 75)
        else:
            log_progress(channel_name, "⚠️ No se encontraron imágenes para el tema.", "orange", 75)
            
    if get_gifs:
        log_progress(channel_name, f"🎬 Buscando GIFs animados para: {query}...", "#FF9100", 80)
        gif_urls = search_giphy_gifs(query, limit=3)
        if gif_urls:
            log_progress(channel_name, f"🎬 Descargando {len(gif_urls)} GIFs...", "#FF9100", 90)
            downloaded = 0
            for idx, gif_url in enumerate(gif_urls):
                clean_q = re.sub(r'[^a-zA-Z0-9]', '_', query[:20].lower())
                filename = f"gif_{clean_q}_{idx}_{random.randint(1000, 9999)}.gif"
                filepath = os.path.join(video_dir, filename)
                if download_file(gif_url, filepath):
                    downloaded += 1
            log_progress(channel_name, f"✅ Se descargaron {downloaded} GIFs del tema.", "#00FF66", 98)
        else:
            log_progress(channel_name, "⚠️ No se encontraron GIFs para el tema.", "orange", 98)
            
    log_progress(channel_name, "✅ Descarga de recursos completada.", "#00FF88", 100)

@router.post("/downloader/search")
def api_download_by_search(req: DownloaderSearchRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        bg_download_resources, 
        req.query, 
        req.channel_name, 
        req.duration, 
        req.get_gameplay, 
        req.get_images, 
        req.get_gifs
    )
    return {"status": "success", "message": "Búsqueda y descarga iniciada en segundo plano."}


@router.get("/gameplay-folders")
def api_get_gameplay_folders(channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    video_dir = paths["videos"]
    cache_gp = paths["cache_gameplays"]
    
    folders = []
    if os.path.exists(video_dir):
        for d in os.listdir(video_dir):
            if os.path.isdir(os.path.join(video_dir, d)) and not d.startswith("."):
                folders.append(d)
    
    if os.path.exists(cache_gp):
        for d in os.listdir(cache_gp):
            if os.path.isdir(os.path.join(cache_gp, d)) and not d.startswith(".") and d not in folders:
                folders.append(d)
                
    return folders


@router.post("/upload-audio")
def api_upload_audio(file: UploadFile = File(...), channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    audio_dir = paths["audio"]
    os.makedirs(audio_dir, exist_ok=True)
    
    filename = file.filename
    if not filename.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
        raise HTTPException(status_code=400, detail="Formato de audio no permitido. Usa .mp3, .wav, .ogg o .m4a")
        
    output_path = os.path.join(audio_dir, filename)
    try:
        with open(output_path, "wb") as buffer:
            import shutil
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success", "filename": filename, "path": output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando el archivo subido: {e}")


@router.post("/upload-resources")
def api_upload_resources(files: List[UploadFile] = File(...), channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    video_dir = paths["videos"]
    image_dir = paths["images"]
    
    saved_files = []
    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()
        if ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif'):
            target_dir = video_dir
        elif ext in ('.png', '.jpg', '.jpeg', '.webp'):
            target_dir = image_dir
        else:
            continue
            
        output_path = os.path.join(target_dir, filename)
        try:
            with open(output_path, "wb") as buffer:
                import shutil
                shutil.copyfileobj(file.file, buffer)
            saved_files.append({"filename": filename, "path": output_path.replace('\\', '/')})
        except Exception as e:
            print(f"Error guardando archivo {filename}: {e}")
            
    return {"status": "success", "uploaded": saved_files}


@router.get("/audio-duration")
def api_get_audio_duration(filename: str, channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    audio_dir = paths["audio"]
    path = os.path.join(audio_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio no encontrado.")
    try:
        from modules.render_utils import get_video_duration
        dur = get_video_duration(path)
        return {"duration": dur}
    except Exception as e:
        try:
            import wave
            with wave.open(path, 'rb') as f:
                frames = f.getnframes()
                rate = f.getframerate()
                dur = frames / float(rate)
                return {"duration": dur}
        except Exception as we:
            print(f"Error parsing wave duration fallback: {we}")
            return {"duration": 120.0}


@router.get("/timeline")
def api_get_timeline_files(channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    video_dir = paths["videos"]
    image_dir = paths["images"]
    
    files = []
    
    if os.path.exists(video_dir):
        for f in os.listdir(video_dir):
            if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif')):
                path = os.path.join(video_dir, f)
                if os.path.isfile(path):
                    files.append({
                        "name": f,
                        "path": os.path.abspath(path).replace('\\', '/'),
                        "type": "video",
                        "size": os.path.getsize(path),
                        "ctime": os.path.getctime(path)
                    })
                    
    if os.path.exists(image_dir):
        for f in os.listdir(image_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                path = os.path.join(image_dir, f)
                if os.path.isfile(path):
                    files.append({
                        "name": f,
                        "path": os.path.abspath(path).replace('\\', '/'),
                        "type": "image",
                        "size": os.path.getsize(path),
                        "ctime": os.path.getctime(path)
                    })
                    
    files.sort(key=lambda x: x["ctime"])
    return files


@router.delete("/timeline")
def api_delete_timeline_file(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    try:
        import gc
        gc.collect()
        from modules.render_utils import safe_remove
        safe_remove(path)
        if os.path.exists(path):
            raise Exception("El archivo sigue bloqueado por el sistema operativo y no pudo ser eliminado.")
        return {"status": "success", "message": "Archivo eliminado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando archivo: {e}")


@router.post("/timeline/clear")
def api_clear_timeline(channel_name: Optional[str] = None):
    paths = get_channel_paths(channel_name)
    video_dir = paths["videos"]
    image_dir = paths["images"]
    
    import gc
    gc.collect()
    from modules.render_utils import safe_remove
    
    deleted_count = 0
    
    if os.path.exists(video_dir):
        for f in os.listdir(video_dir):
            if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif')):
                path = os.path.join(video_dir, f)
                try:
                    safe_remove(path)
                    if not os.path.exists(path):
                        deleted_count += 1
                except:
                    pass
                    
    if os.path.exists(image_dir):
        for f in os.listdir(image_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                path = os.path.join(image_dir, f)
                try:
                    safe_remove(path)
                    if not os.path.exists(path):
                        deleted_count += 1
                except:
                    pass
                    
    return {"status": "success", "message": f"Se eliminaron {deleted_count} archivos del timeline de {paths['channel_name']}."}


@router.post("/cache/clear")
def api_clear_render_cache(channel_name: Optional[str] = None):
    import shutil
    paths = get_channel_paths(channel_name)
    cache_dirs = [
        paths["cache_audio"],
        paths["cache_ass"],
        paths["cache_chunks"],
        paths["cache_json"],
        paths["cache_gameplays"]
    ]
    deleted_files = 0
    deleted_folders = 0
    for d in cache_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                file_path = os.path.join(d, f)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                        deleted_files += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        deleted_folders += 1
                except Exception as e:
                    print(f"Error removiendo {file_path}: {e}")
                    
    return {
        "status": "success", 
        "message": f"Se eliminaron {deleted_files} archivos y {deleted_folders} carpetas de la caché de {paths['channel_name']}."
    }

from api.deps import GenerateTimelineRequest
from modules.timeline_generator import generate_timeline_resources

def bg_generate_timeline(req: GenerateTimelineRequest):
    try:
        generate_timeline_resources(req, req.channel_name)
    except Exception as e:
        log_progress(req.channel_name, f"❌ Error fatal en generación de timeline: {e}", "#ff1a1a", 0)

@router.post("/generate-timeline")
def api_generate_timeline(req: GenerateTimelineRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(bg_generate_timeline, req)
    return {"status": "success", "message": "Generando timeline en segundo plano"}


# --- CRUD DE ESTILOS DE SUBTÍTULOS CUSTOM ---
from pydantic import BaseModel
import json

SUBTITLE_STYLES_PATH = os.path.join("config", "subtitle_styles.json")

class SubtitleStyleModel(BaseModel):
    name: str
    font_name: str = "Arial Black"
    font_size_9_16: int = 90
    font_size_16_9: int = 68
    primary_color: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    back_color: str = "&H80000000"
    bold: int = -1
    italic: int = 0
    outline: int = 4
    shadow: int = 0
    alignment: int = 2
    margin_v_9_16: int = 450
    margin_v_16_9: int = 120
    animation_type: str = "TikTok"
    text_case: str = "uppercase"
    highlight_color: str = "&H00FFFF00&"
    emojis_enabled: bool = True
    hook_type: str = "none"

def get_default_styles():
    return {
        "Reddit History": {
            "name": "Reddit History",
            "font_name": "Arial Black",
            "font_size_9_16": 100,
            "font_size_16_9": 65,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H00000000",
            "bold": -1,
            "italic": 0,
            "outline": 10,
            "shadow": 6,
            "alignment": 2,
            "margin_v_9_16": 700,
            "margin_v_16_9": 120,
            "animation_type": "Reddit",
            "text_case": "uppercase",
            "highlight_color": "&H0000FFFF&",
            "emojis_enabled": False,
            "hook_type": "reddit_card"
        },
        "Roblox Gaming": {
            "name": "Roblox Gaming",
            "font_name": "Arial Black",
            "font_size_9_16": 95,
            "font_size_16_9": 75,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H99000000",
            "bold": -1,
            "italic": 0,
            "outline": 8,
            "shadow": 4,
            "alignment": 2,
            "margin_v_9_16": 450,
            "margin_v_16_9": 120,
            "animation_type": "Roblox",
            "text_case": "uppercase",
            "highlight_color": "&H00FFFF00&",
            "emojis_enabled": False,
            "hook_type": "roblox_double_line"
        }
    }

@router.get("/subtitle-styles")
async def api_get_subtitle_styles():
    styles = get_default_styles()
    
    if os.path.exists(SUBTITLE_STYLES_PATH):
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "r", encoding="utf-8") as f:
                content = await f.read()
                custom_styles = json.loads(content)
                for name, style in custom_styles.items():
                    styles[name] = style
        except Exception as e:
            print(f"Error cargando estilos personalizados de subtítulos: {e}")
            
    return styles

@router.post("/subtitle-styles")
async def api_save_subtitle_style(req: SubtitleStyleModel):
    custom_styles = {}
    if os.path.exists(SUBTITLE_STYLES_PATH):
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "r", encoding="utf-8") as f:
                content = await f.read()
                custom_styles = json.loads(content)
        except Exception:
            pass
            
    custom_styles[req.name] = req.dict()
    
    try:
        os.makedirs(os.path.dirname(SUBTITLE_STYLES_PATH), exist_ok=True)
        async with aiofiles.open(SUBTITLE_STYLES_PATH, "w", encoding="utf-8") as f:
            await f.write(json.dumps(custom_styles, indent=4, ensure_ascii=False))
        return {"status": "success", "message": f"Estilo de subtítulo '{req.name}' guardado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando el estilo de subtítulo: {e}")

@router.delete("/subtitle-styles/{name}")
async def api_delete_subtitle_style(name: str):
    if name in ["Reddit History", "Roblox Gaming"]:
        raise HTTPException(status_code=400, detail="No se pueden eliminar los estilos predeterminados.")
        
    custom_styles = {}
    if os.path.exists(SUBTITLE_STYLES_PATH):
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "r", encoding="utf-8") as f:
                content = await f.read()
                custom_styles = json.loads(content)
        except Exception:
            pass
            
    if name in custom_styles:
        del custom_styles[name]
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "w", encoding="utf-8") as f:
                await f.write(json.dumps(custom_styles, indent=4, ensure_ascii=False))
            return {"status": "success", "message": f"Estilo de subtítulo '{name}' eliminado correctamente."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al eliminar estilo de subtítulo: {e}")
    else:
        raise HTTPException(status_code=404, detail="Estilo de subtítulo personalizado no encontrado.")


from api.deps import GenerateTimelineRequest
from modules.timeline_generator import generate_timeline_resources

def bg_generate_timeline(req: GenerateTimelineRequest):
    try:
        generate_timeline_resources(req, req.channel_name)
    except Exception as e:
        log_progress(req.channel_name, f"❌ Error fatal en generación de timeline: {e}", "#ff1a1a", 0)

@router.post("/generate-timeline")
def api_generate_timeline(req: GenerateTimelineRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(bg_generate_timeline, req)
    return {"status": "success", "message": "Generando timeline en segundo plano"}


# --- CRUD DE ESTILOS DE SUBTÍTULOS CUSTOM ---
from pydantic import BaseModel
import json

SUBTITLE_STYLES_PATH = os.path.join("config", "subtitle_styles.json")

class SubtitleStyleModel(BaseModel):
    name: str
    font_name: str = "Arial Black"
    font_size_9_16: int = 90
    font_size_16_9: int = 68
    primary_color: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    back_color: str = "&H80000000"
    bold: int = -1
    italic: int = 0
    outline: int = 4
    shadow: int = 0
    alignment: int = 2
    margin_v_9_16: int = 450
    margin_v_16_9: int = 120
    animation_type: str = "TikTok"
    text_case: str = "uppercase"
    highlight_color: str = "&H00FFFF00&"
    emojis_enabled: bool = True
    hook_type: str = "none"

def get_default_styles():
    return {
        "Reddit History": {
            "name": "Reddit History",
            "font_name": "Arial Black",
            "font_size_9_16": 100,
            "font_size_16_9": 65,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H00000000",
            "bold": -1,
            "italic": 0,
            "outline": 10,
            "shadow": 6,
            "alignment": 2,
            "margin_v_9_16": 700,
            "margin_v_16_9": 120,
            "animation_type": "Reddit",
            "text_case": "uppercase",
            "highlight_color": "&H0000FFFF&",
            "emojis_enabled": False,
            "hook_type": "reddit_card"
        },
        "Roblox Gaming": {
            "name": "Roblox Gaming",
            "font_name": "Arial Black",
            "font_size_9_16": 95,
            "font_size_16_9": 75,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H99000000",
            "bold": -1,
            "italic": 0,
            "outline": 8,
            "shadow": 4,
            "alignment": 2,
            "margin_v_9_16": 450,
            "margin_v_16_9": 120,
            "animation_type": "Roblox",
            "text_case": "uppercase",
            "highlight_color": "&H00FFFF00&",
            "emojis_enabled": False,
            "hook_type": "roblox_double_line"
        }
    }

@router.get("/subtitle-styles")
async def api_get_subtitle_styles():
    styles = get_default_styles()
    
    if os.path.exists(SUBTITLE_STYLES_PATH):
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "r", encoding="utf-8") as f:
                content = await f.read()
                custom_styles = json.loads(content)
                for name, style in custom_styles.items():
                    styles[name] = style
        except Exception as e:
            print(f"Error cargando estilos personalizados de subtítulos: {e}")
            
    return styles

@router.post("/subtitle-styles")
async def api_save_subtitle_style(req: SubtitleStyleModel):
    custom_styles = {}
    if os.path.exists(SUBTITLE_STYLES_PATH):
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "r", encoding="utf-8") as f:
                content = await f.read()
                custom_styles = json.loads(content)
        except Exception:
            pass
            
    custom_styles[req.name] = req.dict()
    
    try:
        os.makedirs(os.path.dirname(SUBTITLE_STYLES_PATH), exist_ok=True)
        async with aiofiles.open(SUBTITLE_STYLES_PATH, "w", encoding="utf-8") as f:
            await f.write(json.dumps(custom_styles, indent=4, ensure_ascii=False))
        return {"status": "success", "message": f"Estilo de subtítulo '{req.name}' guardado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando el estilo de subtítulo: {e}")

@router.delete("/subtitle-styles/{name}")
async def api_delete_subtitle_style(name: str):
    if name in ["Reddit History", "Roblox Gaming"]:
        raise HTTPException(status_code=400, detail="No se pueden eliminar los estilos predeterminados.")
        
    custom_styles = {}
    if os.path.exists(SUBTITLE_STYLES_PATH):
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "r", encoding="utf-8") as f:
                content = await f.read()
                custom_styles = json.loads(content)
        except Exception:
            pass
            
    if name in custom_styles:
        del custom_styles[name]
        try:
            async with aiofiles.open(SUBTITLE_STYLES_PATH, "w", encoding="utf-8") as f:
                await f.write(json.dumps(custom_styles, indent=4, ensure_ascii=False))
            return {"status": "success", "message": f"Estilo de subtítulo '{name}' eliminado correctamente."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al eliminar estilo de subtítulo: {e}")
    else:
        raise HTTPException(status_code=404, detail="Estilo de subtítulo personalizado no encontrado.")

@router.post("/cache/clear")
def api_clear_render_cache():
    import shutil
    cache_dir = "cache"
    if not os.path.exists(cache_dir):
        return {"status": "success", "message": "El directorio de caché no existe."}
    
    deleted_files = 0
    deleted_folders = 0
    # Limpiar solo subcarpetas temporales de renderizado, conservando detected_encoder.json
    for sub in ["ass", "audio", "chunks", "json", "thumbnails", "gameplays"]:
        path = os.path.join(cache_dir, sub)
        if os.path.exists(path):
            for f in os.listdir(path):
                file_path = os.path.join(path, f)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                        deleted_files += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        deleted_folders += 1
                except Exception as e:
                    print(f"Error removiendo {file_path}: {e}")
                    
    return {
        "status": "success", 
        "message": f"Se eliminaron {deleted_files} archivos y {deleted_folders} carpetas de la caché."
    }
