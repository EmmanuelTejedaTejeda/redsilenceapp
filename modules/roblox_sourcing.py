import os
import re
import json
import time
import urllib.request
import urllib.parse

def clean_filename(name):
    # Sanear el nombre para que sea seguro en disco
    return re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_').lower())

def get_vqd(query):
    """Obtiene el token dinámico de sesión (VQD) de DuckDuckGo para una búsqueda."""
    url = "https://duckduckgo.com/"
    data = urllib.parse.urlencode({'q': query}).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
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
    """Consulta la API de imágenes de DuckDuckGo."""
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
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("results", [])
    except Exception as e:
        print(f">>> [ROBLOX SOURCING] Error buscando imágenes: {e}")
    return []

def download_roblox_media(game_name, limit=10, media_type="images", output_dir=None, status_callback=None):
    """
    Busca y descarga imágenes o GIFs animados de un juego de Roblox.
    Retorna la lista de rutas absolutas de los archivos descargados.
    """
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), "assets", "images")
    os.makedirs(output_dir, exist_ok=True)
    
    # Definir query según el tipo solicitado
    is_gif = (media_type == "gifs" or media_type == "animations")
    if is_gif:
        query = f"Roblox {game_name} horror gif"
    else:
        query = f"Roblox {game_name} horror gameplay screenshots"
        
    if status_callback:
        status_callback(f"🔍 Conectando con DuckDuckGo para buscar {media_type}...", "#FFD700")
        
    vqd = get_vqd(query)
    if not vqd:
        # Fallback query más simple si falla
        query = f"Roblox {game_name}"
        vqd = get_vqd(query)
        if not vqd:
            raise Exception("No se pudo conectar a la búsqueda de DuckDuckGo. Verifica tu conexión.")
            
    results = search_images(query, vqd, search_gifs=is_gif)
    if not results:
        # Reintentar sin 'horror'
        query = f"Roblox {game_name} gameplay"
        vqd = get_vqd(query)
        if vqd:
            results = search_images(query, vqd, search_gifs=is_gif)
            
    if not results:
        raise Exception(f"No se encontraron resultados de {media_type} para '{game_name}'.")
        
    downloaded_paths = []
    count = 0
    
    for item in results:
        if count >= limit:
            break
            
        img_url = item.get("image")
        if not img_url:
            continue
            
        # Detectar extensión
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
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                with open(filepath, "wb") as f:
                    f.write(response.read())
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
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
            # Continuar con el siguiente resultado
            
    if status_callback:
        status_callback(f"✅ Descargados {count} archivos de Roblox.", "#00FF66")
        
    return downloaded_paths
