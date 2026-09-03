import os
import urllib.request
import urllib.parse
import json
import re
import random
from typing import Optional

def is_vector_or_clipart_url(url: str) -> bool:
    """Detecta si la URL corresponde a ilustraciones vectoriales, clipart, dibujos, marcas de agua, portales de minijuegos o tarjetas de felicitaciones/invitaciones"""
    url_lower = url.lower()
    vector_keywords = [
        "vector", "clipart", "illustration", "drawing", "cartoon", "freepik", "stock-vector", 
        "eps", "svg", "drawings", "graphics/vector", "flat-design", "icon", "pngtree", "vecteezy",
        "bigfarm", "goodgame", "fog.com", "games-online", "coloring", "clip-art", "clip_art",
        "invitation", "greeting", "birthday", "tarjeta", "invitacion", "felicitacion", "calendar",
        "wallpaperaccess", "pinterest", "pngall", "rawpixel"
    ]
    return any(vk in url_lower for vk in vector_keywords)

def search_bing_images(query: str, limit: int = 3) -> list:
    """Búsqueda de imágenes en Bing HTML con filtrado de calidad anti-vectores para fotografías y capturas reales"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    encoded = urllib.parse.quote(query)
    url = f"https://www.bing.com/images/search?q={encoded}&first=1"
    req = urllib.request.Request(url, headers=headers)
    image_urls = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            matches = re.findall(r'&quot;murl&quot;:&quot;(https?://[^&]+)&quot;', html)
            for m in matches:
                clean_url = urllib.parse.unquote(m)
                # Filtrar vectores, clipart e ilustraciones infantiles/diagramas
                if is_vector_or_clipart_url(clean_url):
                    continue
                if any(clean_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    if clean_url not in image_urls:
                        image_urls.append(clean_url)
                if len(image_urls) >= limit:
                    break
    except Exception as e:
        print(f"[ENTITY_SEARCH] Error Bing Images '{query}': {e}")
    return image_urls

def search_wikimedia_images(query: str, limit: int = 3) -> list:
    """Búsqueda en Wikimedia Commons API para entidades históricas, noticias o celebridades"""
    headers = {'User-Agent': 'ShortNexusStudio/1.0 (contact@nexusstudio.local)'}
    encoded = urllib.parse.quote(query)
    url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={encoded}&gsrnamespace=6&gsrlimit={limit*3}&prop=imageinfo&iiprop=url|mime|size&format=json"
    req = urllib.request.Request(url, headers=headers)
    image_urls = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                imageinfo = page_data.get("imageinfo", [])
                if imageinfo:
                    img_url = imageinfo[0].get("url")
                    mime = imageinfo[0].get("mime", "")
                    if img_url and any(t in mime for t in ["image/jpeg", "image/png", "image/webp"]):
                        if not is_vector_or_clipart_url(img_url):
                            image_urls.append(img_url)
                if len(image_urls) >= limit:
                    break
    except Exception as e:
        print(f"[ENTITY_SEARCH] Error Wikimedia '{query}': {e}")
    return image_urls

def get_pollinations_ai_image(query: str, dest_dir: str, filename_prefix: str = "ai_entity") -> str:
    """Generación con Pollinations AI como fallback ultra-confiable foto-realista 9:16"""
    try:
        os.makedirs(dest_dir, exist_ok=True)
        prompt_formatted = f"photorealistic 9:16 vertical news documentary photo of {query}, 8k resolution, highly detailed, cinematic lighting, vertical aspect ratio 9:16"
        encoded = urllib.parse.quote(prompt_formatted)
        seed = random.randint(1000, 99999)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&nologo=true&seed={seed}"
        out_path = os.path.join(dest_dir, f"{filename_prefix}_{seed}.jpg")
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(out_path, "wb") as f:
                f.write(resp.read())
        if os.path.exists(out_path) and os.path.getsize(out_path) > 5000:
            print(f"[ENTITY_SEARCH] Imagen foto-realista generada con Pollinations AI: '{query}'")
            return out_path
    except Exception as e:
        print(f"[ENTITY_SEARCH] Error Pollinations AI '{query}': {e}")
    return ""

def download_image_with_fallback(url: str, output_path: str) -> bool:
    """Descarga una imagen verificando cabeceras y tamaño mínimo (mínimo 5 KB)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            data = response.read()
            if len(data) > 5000:
                with open(output_path, "wb") as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f"[ENTITY_SEARCH] Fallo al descargar de {url}: {e}")
    return False

def search_and_download_entity_image(query: str, dest_dir: str, filename_prefix: str = "entity") -> str:
    """
    Búsqueda e instalación de imagen referencial por frase/entidad:
    1. Bing Images (Fotos web reales filtradas sin vectores)
    2. Wikimedia Commons (Imágenes documentales libres)
    3. Pollinations AI (Generación foto-realista 9:16)
    """
    os.makedirs(dest_dir, exist_ok=True)
    out_path = os.path.join(dest_dir, f"{filename_prefix}_{random.randint(100,999)}.jpg")
    
    # 1. Bing Images
    urls = search_bing_images(query, limit=3)
    for u in urls:
        if download_image_with_fallback(u, out_path):
            print(f"[ENTITY_SEARCH] Imagen descargada de Bing: '{query}'")
            return out_path
            
    # 2. Wikimedia Commons
    wm_urls = search_wikimedia_images(query, limit=3)
    for u in wm_urls:
        if download_image_with_fallback(u, out_path):
            print(f"[ENTITY_SEARCH] Imagen descargada de Wikimedia: '{query}'")
            return out_path
            
    # 3. Pollinations AI Fallback
    ai_path = get_pollinations_ai_image(query, dest_dir, filename_prefix)
    if ai_path:
        return ai_path
        
    return ""
