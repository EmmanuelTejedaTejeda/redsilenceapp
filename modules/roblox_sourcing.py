import os
import re
import json
import time
import urllib.request
import urllib.parse
import warnings

# Silenciar advertencias de renombrado de la librería duckduckgo_search
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*ddgs.*")


def clean_filename(name):
    # Sanear el nombre para que sea seguro en disco
    return re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_').lower())

def get_vqd(query):
    """Obtiene el token dinámico de sesión (VQD) de DuckDuckGo para una búsqueda."""
    url = "https://duckduckgo.com/"
    data = urllib.parse.urlencode({'q': query}).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            match = re.search(r'vqd=([\d-]+)', html)
            if match:
                return match.group(1)
            match_js = re.search(r'vqd\s*=\s*["\']([\d-]+)["\']', html)
            if match_js:
                return match_js.group(1)
    except Exception as e:
        print(f">>> [ROBLOX SOURCING] Error obteniendo VQD: {e}")
    return None

def search_images(query, vqd, search_gifs=False):
    """Consulta la API de imágenes de DuckDuckGo (Método Fallback)."""
    params = {
        'l': 'us-en',
        'o': 'json',
        'q': query,
        'vqd': vqd,
        'f': ',,,type:gif' if search_gifs else ',,,',
        'p': '1'
    }
    url = "https://duckduckgo.com/i.js?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    req.add_header("Referer", "https://duckduckgo.com/")
    req.add_header("Accept", "application/json, text/javascript, */*; q=0.01")
    req.add_header("Accept-Language", "es-ES,es;q=0.9,en;q=0.8,en-US;q=0.7")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("results", [])
    except Exception as e:
        print(f">>> [ROBLOX SOURCING] Error buscando imágenes: {e}")
    return []

def download_roblox_media(game_name, limit=10, media_type="images", output_dir=None, status_callback=None):
    """
    Busca y descarga imágenes o GIFs animados de un juego de Roblox usando la librería duckduckgo_search.
    Retorna la lista de rutas absolutas de los archivos descargados.
    """
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), "assets", "images")
    os.makedirs(output_dir, exist_ok=True)
    
    is_gif = (media_type == "gifs" or media_type == "animations")
    if is_gif:
        if any(h in game_name.lower() for h in ["horror", "scary", "terror", "creepy"]):
            query = f"{game_name} gif"
        else:
            query = f"{game_name} horror gif"
    else:
        if any(h in game_name.lower() for h in ["horror", "scary", "terror", "creepy"]):
            query = f"{game_name} gameplay screenshots"
        else:
            query = f"{game_name} horror gameplay screenshots"
        
    if status_callback:
        status_callback(f"🔍 Buscando {media_type} de '{game_name}'...", "#FFD700")
        
    results = []
    
    # 1. Intentar usar la librería duckduckgo_search (que gestiona TLS fingerprints y evita 403 Forbidden)
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        import time
        
        # Retardo preventivo para no activar protecciones
        time.sleep(3.0)
        
        max_retries = 3
        delay = 2.0
        for attempt in range(max_retries):
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.images(
                        keywords=query,
                        type_image="gif" if is_gif else None,
                        max_results=limit
                    ))
                break
            except Exception as e:
                err_str = str(e)
                if "Ratelimit" in err_str or "403" in err_str:
                    if status_callback:
                        status_callback(f"⏳ Rate-limit en búsqueda. Reintentando en {delay}s...", "orange")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise e
                    
        # Reintento con consulta fallback simplificada si no se encontraron imágenes
        if not results:
            time.sleep(1.0)
            query_fallback = f"{game_name} gameplay"
            for attempt in range(max_retries):
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.images(
                            keywords=query_fallback,
                            type_image="gif" if is_gif else None,
                            max_results=limit
                        ))
                    break
                except Exception as e:
                    err_str = str(e)
                    if "Ratelimit" in err_str or "403" in err_str:
                        time.sleep(delay)
                        delay *= 2
                    else:
                        raise e
    except Exception as e:
        print(f">>> [ROBLOX SOURCING] Error usando duckduckgo_search: {e}")
        # 2. Fallback clásico de raspado con urllib
        if status_callback:
            status_callback("⚠️ Falló biblioteca. Usando fallback clásico...", "orange")
        try:
            vqd = get_vqd(query)
            if vqd:
                results = search_images(query, vqd, search_gifs=is_gif)
        except Exception as ex:
            print(f">>> [ROBLOX SOURCING] Fallback clásico también falló: {ex}")
            
    if not results:
        if status_callback:
            status_callback(f"⚠️ No se encontraron resultados de {media_type} para '{game_name}'.", "orange")
        return []
        
    downloaded_paths = []
    count = 0
    
    # 3. Descarga de los recursos
    for item in results:
        if count >= limit:
            break
            
        img_url = item.get("image")
        if not img_url:
            continue
            
        # Determinar extensión
        ext = ".gif" if is_gif else ".jpg"
        if not is_gif:
            if ".png" in img_url.lower():
                ext = ".png"
            elif ".webp" in img_url.lower():
                ext = ".webp"
                
        safe_game = clean_filename(game_name)
        filename = f"roblox_{safe_game}_{media_type}_{count}_{int(time.time())}{ext}"
        filepath = os.path.abspath(os.path.join(output_dir, filename))
        
        if status_callback:
            status_callback(f"📥 Descargando {media_type[:-1]} {count+1}/{limit}...", "#FF9100")
            
        req = urllib.request.Request(img_url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                with open(filepath, "wb") as f:
                    f.write(response.read())
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                # Si es una animación, la convertimos a MP4 para máxima compatibilidad
                if is_gif:
                    try:
                        from PIL import Image
                        import shutil
                        import subprocess
                        
                        img = Image.open(filepath)
                        if getattr(img, "is_animated", False) and img.n_frames > 1:
                            if status_callback:
                                status_callback(f"⚙️ Optimizando animación Roblox {count+1}/{limit}...", "#FFD700")
                            
                            # Extraer frames a carpeta temporal
                            temp_frames_dir = os.path.abspath(os.path.join(output_dir, f"temp_frames_{count}_{int(time.time())}"))
                            os.makedirs(temp_frames_dir, exist_ok=True)
                            
                            for frame_idx in range(img.n_frames):
                                img.seek(frame_idx)
                                frame_rgba = img.convert("RGBA")
                                frame_path = os.path.join(temp_frames_dir, f"frame_{frame_idx:03d}.png")
                                frame_rgba.save(frame_path)
                                
                            duration_ms = img.info.get("duration", 100)
                            if duration_ms <= 0:
                                duration_ms = 100
                            fps = 1000.0 / duration_ms
                            
                            mp4_filepath = filepath.rsplit(".", 1)[0] + ".mp4"
                            cmd_conv = [
                                "ffmpeg", "-y", "-threads", "2",
                                "-f", "image2",
                                "-framerate", f"{fps:.2f}",
                                "-i", os.path.join(temp_frames_dir, "frame_%03d.png"),
                                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                                "-an", mp4_filepath
                            ]
                            
                            sub_kwargs = {}
                            if os.name == 'nt':
                                sub_kwargs['creationflags'] = 0x00000040
                                
                            subprocess.run(cmd_conv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                            shutil.rmtree(temp_frames_dir, ignore_errors=True)
                            
                            if os.path.exists(mp4_filepath) and os.path.getsize(mp4_filepath) > 0:
                                try: os.remove(filepath)
                                except: pass
                                filepath = mp4_filepath
                    except Exception as conv_err:
                        print(f">>> [ROBLOX SOURCING] Error convirtiendo animación a MP4: {conv_err}")
                
                downloaded_paths.append({
                    "path": filepath,
                    "type": "video" if is_gif else "image",
                    "has_audio": False,
                    "is_subliminal": False,
                    "ctime": os.path.getctime(filepath)
                })
                count += 1
        except Exception as e:
            print(f">>> [ROBLOX SOURCING] Falló descarga de {img_url}: {e}")
            
    if status_callback:
        status_callback(f"✅ Descargados {count} archivos de Roblox.", "#00FF66")
        
    return downloaded_paths
