import os
import glob
import math
import asyncio
import time
import random
import re
import urllib.request
import urllib.parse
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from api.deps import log_progress, get_groq_api_key, get_settings
from modules.groq_client import generate_content as generate_groq_content
from modules.pexels_client import search_pexels_video, download_video_file
from modules.gameplay_sourcing import download_youtube_gameplay
from modules.pixabay_client import search_pixabay_photos
import subprocess

def extract_gameplay_chunks(source_video: str, dest_dir: str, num_chunks: int, duration_per_chunk: int = 3):
    """
    Extrae chunks cortos de un video de gameplay o clip de stock.
    Asume que el source_video es lo suficientemente largo.
    Soporta videos cortos y largos dinámicamente.
    """
    os.makedirs(dest_dir, exist_ok=True)
    extracted_paths = []
    
    try:
        cmd_probe = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", source_video
        ]
        result = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        total_duration = float(result.stdout.strip())
    except Exception as e:
        print(f"Error obteniendo duracion del gameplay: {e}")
        total_duration = 300 # Fallback 5 min
        
    start_offset = min(60.0, total_duration * 0.1)
    safe_duration = total_duration - start_offset - (num_chunks * duration_per_chunk)
    
    if safe_duration <= 0:
        start_offset = 0.0
        step = max(0.5, total_duration / max(1, num_chunks + 1))
    else:
        step = min(15.0, safe_duration / max(1, num_chunks))
        
    for i in range(num_chunks):
        out_path = os.path.join(dest_dir, f"gp_chunk_{i:03d}.mp4")
        start_time = start_offset + (i * step)
        # Asegurar que no nos pasamos del total
        if start_time + duration_per_chunk > total_duration:
            start_time = max(0.0, total_duration - duration_per_chunk)
            
        try:
            cmd = [
                "ffmpeg", "-y", "-ss", f"{start_time:.3f}", "-i", source_video,
                "-t", str(duration_per_chunk), "-c:v", "libx264", "-preset", "superfast",
                "-crf", "23", "-an", out_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(out_path):
                extracted_paths.append(out_path)
        except Exception as e:
            print(f"Error extrayendo chunk {i}: {e}")
            
    return extracted_paths

def search_pexels_photos(query, api_key, limit=3, orientation="portrait"):
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

def download_file(url, output_path):
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

def generate_timeline_resources(req, channel_name: str):
    log_progress(channel_name, f"🧠 Calculando {req.audio_duration}s de audio...", "#00d2ff", 5)
    
    # 1. Calcular número de clips
    num_clips = int(math.ceil(req.audio_duration / 3.0))
    if num_clips < 1:
        num_clips = 1
        
    num_gameplay = 0
    num_mixed = num_clips
    
    if req.intercalar_gameplay:
        num_mixed = num_clips // 2
        num_gameplay = num_clips - num_mixed
        
    log_progress(channel_name, f"📊 Requeridos: {num_clips} clips (Gameplay: {num_gameplay}, Mixto: {num_mixed})", "#00d2ff", 10)
    
    settings = get_settings()
    from api.deps import get_channel_paths
    paths = get_channel_paths(channel_name, settings)
    video_dir = paths["videos"]
    image_dir = paths["images"]
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)
        
    # Limpiar timeline anterior en ambos directorios
    if os.path.exists(video_dir):
        for f in os.listdir(video_dir):
            if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif')):
                try: os.remove(os.path.join(video_dir, f))
                except: pass
    if os.path.exists(image_dir):
        for f in os.listdir(image_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                try: os.remove(os.path.join(image_dir, f))
                except: pass
                
    keywords = []
    if num_mixed > 0:
        log_progress(channel_name, "🤖 Generando lista de términos visuales con Groq...", "#ffae00", 15)
        groq_key = get_groq_api_key()
        
        channel_theme = channel_name
        themes_path = os.path.join("config", "themes.json")
        if os.path.exists(themes_path):
            try:
                with open(themes_path, "r", encoding="utf-8") as f:
                    themes_data = json.load(f)
                    if channel_name in themes_data:
                        channel_theme = themes_data[channel_name]
            except:
                pass
                
        if groq_key:
            prompt = f"""Eres un director de fotografía cinematográfico buscando B-Rolls documentales de alta calidad para el nicho '{channel_theme}'.
Basándote en esta historia: "{req.trama}", genera exactamente {num_mixed} búsquedas en inglés (de 2 a 4 palabras descriptivas por búsqueda).
REGLA CRÍTICA DE AUTENTICIDAD:
Cada término debe describir escenas documentales de contexto hiper-específico (ej: 'underwater sonar radar screen', '1970s oceanographic research ship deck', 'cinematic deep sea trench abyss'). EVITA palabras vacías abstractas como 'dark', 'sea', 'crimson'.
Solo devuelve una lista separada por comas, sin comillas, ni introducciones, ni viñetas."""
            
            try:
                result = generate_groq_content(prompt, groq_key, model_name="llama-3.3-70b-versatile")
                raw_keywords = [k.strip() for k in result.split(",") if k.strip()]
                keywords = raw_keywords[:num_mixed]
            except Exception as e:
                print(f"Error AI keywords: {e}")
        
        while len(keywords) < num_mixed:
            keywords.append(f"aesthetic {channel_theme}")
            
    # 2. Descargar Gameplay
    gameplay_chunks = []
    if num_gameplay > 0:
        log_progress(channel_name, "🎮 Obteniendo y extrayendo fragmentos de Gameplay...", "#ff1a1a", 30)
        gameplay_cache = paths["cache_gameplays"]
        os.makedirs(gameplay_cache, exist_ok=True)
        try:
            gp_path = download_youtube_gameplay("roblox parkour horror", gameplay_cache)
            if gp_path:
                gp_temp = os.path.join(paths["cache"], "temp_gp_chunks")
                gameplay_chunks = extract_gameplay_chunks(gp_path, gp_temp, num_gameplay, 3)
        except Exception as e:
            print(f"Error gameplay: {e}")

    # 3. Descargar Recursos Mixtos alternando plataformas (40% YouTube, 30% Pexels Video, 30% Imagen)
    mixed_clips = []
    if keywords:
        log_progress(channel_name, f"📥 Descargando {len(keywords)} recursos mixtos (IA)...", "#00c853", 50)
        pexels_key = settings.get("pexels_api_key", "")
        pixabay_key = settings.get("pixabay_api_key", "")
        
        cache_temp_dir = os.path.join(paths["cache"], "temp_mixed")
        os.makedirs(cache_temp_dir, exist_ok=True)
        
        for idx, kw in enumerate(keywords):
            clip_path = None
            log_progress(channel_name, f"🔍 Buscando recurso {idx+1}/{len(keywords)}: '{kw}'", "#00E5FF", 50 + int((idx/len(keywords))*30))
            
            # Definir la prioridad de búsqueda según el índice para mantener el ratio 40/30/30
            # idx % 10: [0, 3, 6, 9] -> YouTube (40%), [1, 4, 7] -> Pexels Video (30%), [2, 5, 8] -> Imagen (30%)
            rem = idx % 10
            if rem in [0, 3, 6, 9]:
                search_order = ["youtube", "pexels_video", "pexels_image", "pixabay_image"]
            elif rem in [1, 4, 7]:
                search_order = ["pexels_video", "youtube", "pexels_image", "pixabay_image"]
            else: # 2, 5, 8
                # Alternar entre empezar por Pexels o Pixabay para las imágenes
                if idx % 2 == 0:
                    search_order = ["pexels_image", "pixabay_image", "youtube", "pexels_video"]
                else:
                    search_order = ["pixabay_image", "pexels_image", "youtube", "pexels_video"]
            
            # Ejecutar la búsqueda en el orden prioritario definido
            for source in search_order:
                if clip_path:
                    break # Recurso ya obtenido
                
                if source == "youtube":
                    try:
                        yt_query = f"{kw} short vertical"
                        log_progress(channel_name, f"🌐 Buscando en YouTube: '{kw}'", "#FFD700", 50 + int((idx/len(keywords))*30))
                        yt_video_path = download_youtube_gameplay(yt_query, cache_temp_dir)
                        if yt_video_path and os.path.exists(yt_video_path):
                            slice_dest_dir = os.path.join(cache_temp_dir, f"yt_slice_{idx}")
                            slices = extract_gameplay_chunks(yt_video_path, slice_dest_dir, 1, 3)
                            if slices:
                                clip_path = slices[0]
                                print(f">>> [TIMELINE] Recurso {kw} obtenido y segmentado de YouTube.")
                    except Exception as e:
                        print(f"Error YouTube {kw}: {e}")
                        
                elif source == "pexels_video" and pexels_key:
                    try:
                        log_progress(channel_name, f"🌐 Buscando video en Pexels: '{kw}'", "#00E5FF", 50 + int((idx/len(keywords))*30))
                        url = search_pexels_video(kw, pexels_key, orientation="portrait")
                        if url:
                            out_name = os.path.join(cache_temp_dir, f"px_vid_{idx}_{random.randint(100,999)}.mp4")
                            if download_video_file(url, out_name):
                                clip_path = out_name
                                print(f">>> [TIMELINE] Recurso {kw} obtenido de Pexels Video.")
                    except Exception as e:
                        print(f"Error Pexels Video {kw}: {e}")
                        
                elif source == "pexels_image" and pexels_key:
                    try:
                        log_progress(channel_name, f"🖼️ Buscando imagen en Pexels: '{kw}'", "#00E5FF", 50 + int((idx/len(keywords))*30))
                        img_urls = search_pexels_photos(kw, pexels_key, limit=1)
                        if img_urls:
                            out_name = os.path.join(cache_temp_dir, f"px_img_{idx}_{random.randint(100,999)}.jpg")
                            if download_file(img_urls[0], out_name):
                                clip_path = out_name
                                print(f">>> [TIMELINE] Recurso {kw} obtenido de Pexels Image.")
                    except Exception as e:
                        print(f"Error Pexels Image {kw}: {e}")
                        
                elif source == "pixabay_image" and pixabay_key:
                    try:
                        log_progress(channel_name, f"🖼️ Buscando imagen en Pixabay: '{kw}'", "#00E5FF", 50 + int((idx/len(keywords))*30))
                        photos = search_pixabay_photos(kw, pixabay_key, limit=1)
                        if photos:
                            out_name = os.path.join(cache_temp_dir, f"pb_img_{idx}_{random.randint(100,999)}.jpg")
                            if download_file(photos[0]["image"], out_name):
                                clip_path = out_name
                                print(f">>> [TIMELINE] Recurso {kw} obtenido de Pixabay Image.")
                    except Exception as e:
                        print(f"Error Pixabay Image {kw}: {e}")
            
            if clip_path:
                mixed_clips.append(clip_path)
            else:
                print(f">>> [TIMELINE] ⚠️ No se pudo obtener ningún recurso para la palabra clave: {kw}")
                
    # 4. Intercalar y guardar en timeline
    log_progress(channel_name, "🔄 Intercalando recursos en el timeline...", "#9d00ff", 85)
    
    total_len = max(len(gameplay_chunks), len(mixed_clips))
    file_index = 0
    
    for i in range(total_len):
        if i < len(gameplay_chunks):
            src = gameplay_chunks[i]
            dst = os.path.join(video_dir, f"{file_index:03d}_gameplay.mp4")
            try:
                import shutil
                shutil.copy2(src, dst)
                file_index += 1
            except:
                pass
                
        if i < len(mixed_clips):
            src = mixed_clips[i]
            ext = os.path.splitext(src)[1].lower()
            # Guardar en el directorio apropiado basado en si es video o imagen
            is_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif']
            target_dir = video_dir if is_video else image_dir
            dst = os.path.join(target_dir, f"{file_index:03d}_mixed{ext}")
            try:
                import shutil
                shutil.copy2(src, dst)
                file_index += 1
            except:
                pass
                
    log_progress(channel_name, f"✅ Timeline generado exitosamente con {file_index} recursos.", "#00ff88", 100)
