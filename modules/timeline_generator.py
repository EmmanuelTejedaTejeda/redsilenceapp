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
from modules.entity_search import search_and_download_entity_image
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

def segment_script_into_sentences(script_text: str, target_num_clips: int) -> list:
    """Divide el guion en exactamente target_num_clips frases/bloques homogéneos."""
    clean_text = script_text.replace('\n', ' ').strip()
    raw_sentences = [s.strip() for s in re.split(r'[.!?]+', clean_text) if s.strip()]
    if not raw_sentences:
        raw_sentences = [clean_text]
        
    result_blocks = []
    if len(raw_sentences) == target_num_clips:
        result_blocks = raw_sentences
    elif len(raw_sentences) > target_num_clips:
        ratio = len(raw_sentences) / float(target_num_clips)
        for i in range(target_num_clips):
            start_idx = int(i * ratio)
            end_idx = int((i + 1) * ratio) if i < target_num_clips - 1 else len(raw_sentences)
            block = " ".join(raw_sentences[start_idx:end_idx])
            result_blocks.append(block)
    else:
        words = clean_text.split()
        chunk_size = max(1, len(words) // target_num_clips)
        for i in range(target_num_clips):
            start_idx = i * chunk_size
            end_idx = (i + 1) * chunk_size if i < target_num_clips - 1 else len(words)
            block = " ".join(words[start_idx:end_idx])
            result_blocks.append(block)
            
    return result_blocks

def extract_per_sentence_visual_queries(sentences: list, channel_theme: str = "General") -> list:
    """Extrae 1 término visual hiper-específico de 2-5 palabras por frase del guion."""
    groq_key = get_groq_api_key()
    if not groq_key:
        return [s[:40] for s in sentences]
        
    num_clips = len(sentences)
    sentences_formatted = "\n".join([f"Frase {i+1}: {s}" for i, s in enumerate(sentences)])
    
    prompt = f"""
Eres el director visual maestro de ShortNexus Studio.
Tenemos un guion dividido en exactamente {num_clips} frases para un vídeo corto vertical (Shorts/TikTok).

TU TAREA:
Para CADA una de las {num_clips} frases, debes extraer el término de búsqueda visual MÁS RELEVANTE (de 2 a 5 palabras descriptivas).

REGLAS ABSOLUTAS:
1. SI LA FRASE MENCIONA UN NOMBRE REAL, PERSONAJE, VIDEOJUEGO, MARCA, PELÍCULA O NOTICIA (ej: GTA 6, CyberLeek, MrBeast, Elon Musk, Bitcoin, Rockstar Games), CONSERVA EL NOMBRE EXACTO DE LA ENTIDAD.
2. Si la frase es sobre una acción o concepto, genera un término cinematográfico claro (ej: 'hacker malware screen warning', 'crypto coin dollar scam', 'police cyber crime investigation').
3. PROHIBIDO GENERAR PALABRAS VAGAS O RARAS como 'footprint', 'farm', 'abstract blur', 'dark room'.

FRASES DEL GUION:
{sentences_formatted}

Responde ÚNICAMENTE con un JSON válido con esta estructura (sin etiquetas markdown ni texto adicional):
[
  {{"phrase_index": 1, "query": "búsqueda para frase 1"}},
  ...
]
"""
    try:
        raw = generate_groq_content(prompt, groq_key)
        raw_clean = raw.strip()
        if raw_clean.startswith("```json"): raw_clean = raw_clean[7:]
        if raw_clean.startswith("```"): raw_clean = raw_clean[3:]
        if raw_clean.endswith("```"): raw_clean = raw_clean[:-3]
        data = json.loads(raw_clean.strip())
        queries = [item.get("query", "").strip() for item in data]
        if len(queries) == num_clips:
            return queries
    except Exception as e:
        print("Error en extract_per_sentence_visual_queries:", e)
        
    return [s[:40] for s in sentences]

def generate_timeline_resources(req, channel_name: str):
    log_progress(channel_name, f"🧠 Calculando {req.audio_duration}s de audio...", "#00d2ff", 5)
    
    # 1. Calcular número de clips
    num_clips = int(math.ceil(req.audio_duration / 3.0))
    if num_clips < 1:
        num_clips = 1
        
    num_mixed = num_clips
    log_progress(channel_name, f"📊 Requeridos: {num_clips} clips mixtos", "#00d2ff", 10)
    
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
    custom_kw = getattr(req, "custom_keywords", None)
    if custom_kw and isinstance(custom_kw, list) and len(custom_kw) > 0:
        keywords = [str(k).strip() for k in custom_kw if str(k).strip()]
        log_progress(channel_name, f"📋 Usando {len(keywords)} términos visuales definidos/editados por el usuario...", "#00d2ff", 15)

    if num_mixed > 0 and len(keywords) == 0:
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

        script_text = getattr(req, "script", "") or ""
        if script_text.strip():
            log_progress(channel_name, f"🤖 Analizando guion frase por frase ({num_mixed} frases)...", "#ffae00", 15)
            sentences = segment_script_into_sentences(script_text, num_mixed)
            keywords = extract_per_sentence_visual_queries(sentences, channel_theme)
        else:
            log_progress(channel_name, "🤖 Generando términos visuales con Groq...", "#ffae00", 15)
            groq_key = get_groq_api_key()
            if groq_key:
                prompt = f"Genera exactamente {num_mixed} búsquedas visuales descriptivas separadas por comas para: {req.trama}"
                try:
                    result = generate_groq_content(prompt, groq_key, model_name="openai/gpt-oss-120b")
                    raw_keywords = [k.strip() for k in result.split(",") if k.strip()]
                    keywords = raw_keywords[:num_mixed]
                except Exception as e:
                    print(f"Error AI keywords: {e}")

        while len(keywords) < num_mixed:
            keywords.append(f"aesthetic {channel_theme}")
            
    # 2. Descargar Recursos Mixtos (40% YouTube, 30% Pexels Video, 30% Imagen)
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
            
            # Detectar si la búsqueda trata sobre una entidad/sujeto específico
            words = [w for w in kw.strip().split() if w]
            has_proper_nouns = any(len(w) > 1 and w[0].isupper() for w in words[1:]) if len(words) > 1 else (len(words) == 1 and words[0][0].isupper())
            is_entity = has_proper_nouns or any(k in kw.lower() for k in ["gta", "mrbeast", "elon", "musk", "ronaldo", "messi", "iphone", "batman", "spiderman", "anime", "naruto", "roblox", "minecraft", "fortnite", "tesla", "apple", "bitcoin"])

            # Reequilibrar la mezcla de fuentes: 
            # - Para entidades explícitas/nombres de juegos/personas: Buscar Imagen Referencial -> YouTube -> Pexels Video
            # - Para conceptos/acciones: Alternar entre Pexels Video -> YouTube -> Imagen Referencial (asegurando videos MP4)
            rem = idx % 5
            if is_entity or "gameplay" in kw.lower() or "video" in kw.lower():
                search_order = ["entity_image", "youtube", "pexels_video", "pexels_image"]
            elif rem in [0, 2]:
                search_order = ["pexels_video", "youtube", "entity_image", "pexels_image"]
            elif rem in [1, 3]:
                search_order = ["youtube", "pexels_video", "entity_image", "pexels_image"]
            else:
                search_order = ["entity_image", "pexels_video", "youtube", "pexels_image"]
            
            # Ejecutar la búsqueda en el orden prioritario definido
            for source in search_order:
                if clip_path:
                    break # Recurso ya obtenido
                
                if source == "entity_image":
                    try:
                        log_progress(channel_name, f"📌 Buscando imagen referencial (Entidad/IA): '{kw}'", "#FF007F", 50 + int((idx/len(keywords))*30))
                        img_entity_path = search_and_download_entity_image(kw, cache_temp_dir, f"entity_{idx}")
                        if img_entity_path and os.path.exists(img_entity_path):
                            clip_path = img_entity_path
                            print(f">>> [TIMELINE] Recurso referencial para entidad '{kw}' obtenido exitosamente.")
                    except Exception as e:
                        print(f"Error Entity Image {kw}: {e}")

                elif source == "youtube":
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
                
    # 3. Guardar recursos en el timeline
    log_progress(channel_name, "🔄 Integrando recursos al timeline...", "#9d00ff", 85)
    file_index = 0
    import shutil
    for src in mixed_clips:
        ext = os.path.splitext(src)[1].lower()
        is_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif']
        target_dir = video_dir if is_video else image_dir
        dst = os.path.join(target_dir, f"{file_index:03d}_mixed{ext}")
        try:
            shutil.copy2(src, dst)
            file_index += 1
        except:
            pass
                
    log_progress(channel_name, f"✅ Timeline generado exitosamente con {file_index} recursos.", "#00ff88", 100)
                
    log_progress(channel_name, f"✅ Timeline generado exitosamente con {file_index} recursos.", "#00ff88", 100)
