import urllib.request
import urllib.parse
import json
import os
import re

def clean_query(query):
    query = re.sub(r'[^a-zA-Z0-9\s]', '', query)
    return " ".join(query.split())

def search_pixabay_photos(query, api_key, limit=5, orientation="vertical"):
    """
    Busca fotos en Pixabay usando su API.
    Retorna una lista de diccionarios con la URL de la imagen y su metadata.
    """
    if not api_key:
        print(">>> [PIXABAY CLIENT] Error: API Key faltante.")
        return []

    cleaned = clean_query(query)
    if not cleaned:
        return []

    encoded_query = urllib.parse.quote(cleaned)
    url = f"https://pixabay.com/api/?key={api_key}&q={encoded_query}&image_type=photo&orientation={orientation}&per_page={limit}"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            
        hits = res_data.get("hits", [])
        results = []
        for hit in hits:
            # Pixabay ofrece webformatURL (max 640px ancho) o largeImageURL (full HD)
            img_link = hit.get("largeImageURL") or hit.get("webformatURL")
            if img_link:
                results.append({
                    "image": img_link,
                    "title": f"Pixabay Image by {hit.get('user', 'Anonymous')}"
                })
        return results
    except Exception as e:
        print(f">>> [PIXABAY CLIENT] Error buscando fotos en Pixabay: {e}")
        return []
