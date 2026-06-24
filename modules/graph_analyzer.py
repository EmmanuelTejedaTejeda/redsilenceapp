import re
import os
import json
from collections import Counter
import networkx as nx

# Lista de stop words comunes en español e inglés para filtrar ruido
STOP_WORDS = {
    # Español
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", "con", "no", 
    "una", "su", "al", "lo", "como", "más", "pero", "sus", "este", "o", "este", "ese", "eso", "aquello",
    "este", "esta", "estos", "estas", "este", "muy", "sin", "sobre", "también", "me", "nos", "te", "le",
    "les", "os", "mi", "mis", "tu", "tus", "su", "sus", "esta", "está", "están", "era", "eran", "fue", "fueron",
    "ser", "estar", "hacer", "tener", "cómo", "qué", "quién", "quienes", "cuando", "donde", "por qué", 
    "yo", "él", "ella", "nosotros", "ellos", "ellas", "usted", "ustedes", "mismo", "misma", "otro", "otra",
    "otros", "otras", "todo", "toda", "todos", "todas", "cada", "alguno", "alguna", "algunos", "algunas",
    "es", "son", "un", "unos", "unas", "bien", "si", "sí", "ya", "ahora", "después", "entonces", "cuando",
    # Inglés
    "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was", "for", "on", "are", "as",
    "with", "his", "they", "i", "at", "be", "this", "have", "from", "or", "one", "had", "by", "word", "but",
    "not", "what", "all", "were", "we", "when", "your", "can", "said", "there", "use", "an", "each", "which",
    "she", "do", "how", "their", "if", "will", "up", "other", "about", "out", "many", "then", "them", "these",
    "so", "some", "her", "would", "make", "like", "him", "into", "time", "has", "look", "two", "more", "write",
    "go", "see", "number", "no", "way", "could", "people", "my", "than", "first", "water", "been", "call",
    "who", "oil", "its", "now", "find",
    # Conectores o términos genéricos de transcripción
    "youtube", "shorts", "short", "video", "canal", "hola", "todos", "hoy", "aquí", "les", "traigo", "nuevo",
    "error", "transcripción", "disponible", "audio", "narración"
}

def remove_accents(text):
    """Elimina acentos y diacríticos comunes del español para normalización."""
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ü': 'u', 'ñ': 'n',
        'Á': 'a', 'É': 'e', 'Í': 'i', 'Ó': 'o', 'Ú': 'u',
        'Ü': 'u', 'Ñ': 'n'
    }
    for acc, raw in replacements.items():
        text = text.replace(acc, raw)
    return text

# Normalizar la lista de stop words a texto sin acentos
STOP_WORDS = {remove_accents(w) for w in STOP_WORDS}

def tokenize(text):
    """
    Limpia y divide el texto en una lista de palabras en minúscula sin acentos,
    filtrando stop words, números y palabras de longitud menor o igual a 2.
    """
    if not text:
        return []
    
    # Extraer palabras del texto (secuencias alfanuméricas incluyendo tildes y eñes)
    words = re.findall(r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\d]+', text.lower())
    
    cleaned = []
    for w in words:
        w_norm = remove_accents(w)
        if w_norm not in STOP_WORDS and len(w_norm) > 2 and not w_norm.isdigit():
            cleaned.append(w_norm)
    return cleaned

def get_video_keywords(video, max_transcript_words=10):
    """
    Extrae un conjunto óptimo de palabras clave para un video.
    Incluye palabras del título, tags oficiales y los términos más frecuentes del cuerpo (descripción/transcripción).
    """
    keywords = set()
    
    # 1. Título (siempre se incluye por su relevancia temática)
    title_words = tokenize(video.get("title", ""))
    keywords.update(title_words)
    
    # 2. Etiquetas del video (tags oficiales)
    tags = video.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            keywords.update(tokenize(tag))
            
    # 3. Descripción y Transcripción (obtenemos los N términos más frecuentes del cuerpo)
    desc_words = tokenize(video.get("description", ""))
    
    # Intentar leer transcripción desde caché local si no está en el objeto
    video_id = video.get("video_id")
    transcript_text = video.get("transcript", "")
    if not transcript_text and video_id:
        transcripts_dir = os.path.join("config", "cache", "transcripts")
        cache_path = os.path.join(transcripts_dir, f"{video_id}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    transcript_text = data.get("transcript", "")
            except Exception as e:
                print(f"Error leyendo caché de transcripción para grafo de {video_id}: {e}")
                
    trans_words = tokenize(transcript_text)
    
    all_body_words = desc_words + trans_words
    if all_body_words:
        counter = Counter(all_body_words)
        top_words = [word for word, count in counter.most_common(max_transcript_words)]
        keywords.update(top_words)
        
    return list(keywords)

def generate_viral_graph_data(videos, video_type_filter="all", min_frequency=2, max_nodes=50):
    """
    Genera un objeto Graph de networkx y un listado ordenado de palabras clave con su score y frecuencia.
    """
    # 1. Filtrar videos por tipo
    filtered_videos = []
    for v in videos:
        v_type = v.get("type", "long")
        # Asegurar coincidencia de tipos en minúscula
        if video_type_filter == "all" or v_type.lower() == video_type_filter.lower():
            filtered_videos.append(v)
            
    if not filtered_videos:
        return nx.Graph(), []
        
    # 2. Extraer keywords por video y acumular frecuencias y puntuaciones
    video_keywords_list = []
    word_freq = Counter()
    word_scores = {}
    
    for v in filtered_videos:
        score = v.get("score", 0)
        keywords = get_video_keywords(v)
        video_keywords_list.append((keywords, score))
        
        for w in keywords:
            word_freq[w] += 1
            if w not in word_scores:
                word_scores[w] = []
            word_scores[w].append(score)
            
    # 3. Filtrar palabras por frecuencia mínima y máxima (evitar términos universales/genéricos)
    max_video_ratio = 0.60
    max_docs = len(filtered_videos) * max_video_ratio
    
    valid_words = set()
    for w, freq in word_freq.items():
        if freq < min_frequency:
            continue
        # Solo aplicar filtro de frecuencia máxima si hay suficientes videos para discriminar
        if len(filtered_videos) >= 4 and freq > max_docs:
            continue
        valid_words.add(w)
    
    # 4. Limitar nodos para evitar saturación de la visualización
    if len(valid_words) > max_nodes:
        top_words = [w for w, _ in word_freq.most_common() if w in valid_words][:max_nodes]
        valid_words = set(top_words)
        
    if not valid_words:
        return nx.Graph(), []
        
    # 5. Construir el Grafo
    G = nx.Graph()
    
    # Añadir nodos con sus atributos
    word_data_list = []
    for w in valid_words:
        freq = word_freq[w]
        scores = word_scores[w]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        G.add_node(w, frequency=freq, avg_score=avg_score)
        word_data_list.append({
            "word": w,
            "frequency": freq,
            "avg_score": avg_score
        })
        
    # Añadir aristas (co-ocurrencias)
    edge_weights = Counter()
    for keywords, score in video_keywords_list:
        kw_nodes = [w for w in keywords if w in valid_words]
        for i in range(len(kw_nodes)):
            for j in range(i + 1, len(kw_nodes)):
                w1, w2 = kw_nodes[i], kw_nodes[j]
                if w1 > w2:
                    w1, w2 = w2, w1
                edge_weights[(w1, w2)] += 1
                
    for (w1, w2), weight in edge_weights.items():
        G.add_edge(w1, w2, weight=weight)
        
    # Ordenar tabla de palabras por score promedio descendente
    word_data_list.sort(key=lambda x: x["avg_score"], reverse=True)
    
    return G, word_data_list
