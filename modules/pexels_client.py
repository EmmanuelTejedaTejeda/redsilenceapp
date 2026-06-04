import urllib.request
import urllib.parse
import json
import os
import re

def clean_query(query):
    # Limpia el string para que solo contenga caracteres alfanuméricos y espacios sencillos
    query = re.sub(r'[^a-zA-Z0-9\s]', '', query)
    return " ".join(query.split())

def search_pexels_video(query, api_key, orientation="portrait"):
    """
    Busca un video en Pexels en base a un término de búsqueda.
    Retorna la URL directa del video mp4.
    """
    if not api_key:
        print(">>> [PEXELS CLIENT] Error: API Key faltante.")
        return None

    cleaned = clean_query(query)
    if not cleaned:
        return None

    encoded_query = urllib.parse.quote(cleaned)
    url = f"https://api.pexels.com/videos/search?query={encoded_query}&orientation={orientation}&per_page=3"
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", api_key)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            
        videos = res_data.get("videos", [])
        if not videos:
            print(f">>> [PEXELS CLIENT] No se encontraron videos para: {cleaned}")
            return None
            
        # Elegir un video aleatorio de los resultados para mayor variedad
        import random
        random.shuffle(videos)
        
        # Elegir el primer video que tenga archivos válidos
        for video in videos:
            video_files = video.get("video_files", [])
            
            # Buscar preferiblemente calidad HD y tipo MP4
            for file in video_files:
                if file.get("quality") == "hd" and "mp4" in file.get("file_type", ""):
                    return file.get("link")
            
            # Si no hay HD, buscar cualquier MP4
            for file in video_files:
                if "mp4" in file.get("file_type", ""):
                    return file.get("link")
                    
            # Fallback al primer archivo disponible
            if video_files:
                return video_files[0].get("link")
                
        return None
    except Exception as e:
        print(f">>> [PEXELS CLIENT] Error buscando video en Pexels: {e}")
        return None

def download_video_file(video_url, output_path):
    """
    Descarga el video desde la URL y lo escribe en el disco.
    """
    req = urllib.request.Request(video_url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(output_path, "wb") as f:
                # Escribir por bloques para evitar saturar memoria
                chunk_size = 1024 * 512 # 512 KB
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
        return output_path
    except Exception as e:
        print(f">>> [PEXELS CLIENT] Error descargando archivo de video: {e}")
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except: pass
        return None

def extract_keywords_from_prompt(scene_text, api_key, provider="gemini"):
    """
    Utiliza Gemini o Groq para resumir un prompt de escena en 1 o 2 palabras clave en inglés
    adecuadas para buscar clips de stock en Pexels.
    """
    prompt = f"""You are a professional video editor. Convert the following scene description into a 1 or 2 word search query in English suitable for finding a matching stock video on Pexels.
Do NOT include quotes, explanation, or punctuation. Output ONLY the keywords.

Scene: {scene_text}"""

    try:
        if provider == "groq":
            from modules import groq_client
            # Usamos Llama-3 para una respuesta ultra veloz
            keywords = groq_client.generate_content(prompt, api_key)
        else:
            from modules import gemini_client
            # Usamos Gemini 2.5 Flash
            keywords = gemini_client.generate_content(prompt, api_key)
            
        cleaned_keywords = keywords.strip().replace('"', '').replace('.', '').lower()
        # Eliminar saltos de línea y formatear
        cleaned_keywords = " ".join(cleaned_keywords.split())
        return cleaned_keywords
    except Exception as e:
        print(f">>> [PEXELS CLIENT] Error extrayendo palabras clave con la IA: {e}")
        # Fallback simple
        return "dark mood"
