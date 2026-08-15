import re
import os
import json
from collections import Counter
import networkx as nx

# Intentar importar módulos de comunidades de networkx de forma segura
try:
    from networkx.algorithms.community import louvain_communities
except ImportError:
    try:
        from networkx.algorithms.community.modularity_max import greedy_modularity_communities
        # Envolvemos greedy en una interfaz similar a louvain_communities
        def louvain_communities(G, seed=None):
            return list(greedy_modularity_communities(G))
    except ImportError:
        louvain_communities = None

# Palabras fuertes de gancho asociadas al nicho de misterio/terror/acción para evaluar el Hook Score
# Palabras fuertes de gancho asociadas al nicho de misterio/terror/acción para evaluar el Hook Score
HOOK_WORDS = {
    "misterio", "terror", "secreto", "peligro", "oculto", "prohibido", "maldito", "descubri", "hoy", 
    "perturbador", "historia", "paso", "real", "metraje", "cinta", "vhs", "inexplicable", "paranormal",
    "abandonado", "muerte", "desaparicion", "oscuro", "leyenda", "verdad", "explicacion", "evidencia",
    "curioso", "extraño", "saber", "nadie", "ocultan", "temen", "no debiste", "secreto aterrador", 
    "nunca debiste", "camaras de seguridad", "grabado", "captado", "evidencia real", "escalofriante",
    "aterrador", "prohibida", "sucedio", "ocultado", "descubierto", "caso real", "desaparecido"
}

def extract_bigrams(text):
    """
    Extrae combinaciones significativas de 2 palabras consecutivas del texto,
    excluyendo stop words y números para representar frases clave del nicho.
    """
    if not text:
        return []
    # Remover marcas de corchetes de la transcripción
    text_clean = re.sub(r'\[.*?\]', '', text).strip()
    words = re.findall(r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\d]+', text_clean.lower())
    bigrams = []
    for i in range(len(words) - 1):
        w1 = remove_accents(words[i])
        w2 = remove_accents(words[i+1])
        if w1 not in STOP_WORDS and w2 not in STOP_WORDS:
            if len(w1) > 2 and len(w2) > 2 and not w1.isdigit() and not w2.isdigit():
                bigrams.append(f"{w1} {w2}")
    return bigrams

def calculate_pacing_wpm(transcript, duration_seconds):
    """
    Calcula el ritmo narrativo (palabras por minuto - WPM) en base a la duración y transcripción.
    Un ritmo de Shorts ideal de alta retención suele estar entre 145 y 175 WPM.
    """
    if not transcript or not duration_seconds or duration_seconds <= 0:
        return 0
    clean_text = re.sub(r'\[.*?\]', '', transcript).strip()
    if not clean_text:
        return 0
    words = clean_text.split()
    if len(words) < 5:
        return 0
    wpm = (len(words) / duration_seconds) * 60
    return int(wpm)

def calculate_hook_score(transcript):
    """
    Evalúa la fuerza del gancho en las primeras 20 palabras de la transcripción
    (los primeros 3-5 segundos críticos de un Short).
    """
    if not transcript:
        return 0
    # Limpiar textos de advertencias
    clean_text = re.sub(r'\[.*?\]', '', transcript).strip()
    if not clean_text:
        return 0
    # Analizar las primeras 20 palabras
    words = clean_text.lower().split()[:20]
    intro_text = " ".join(words)
    
    # Evaluar tokens individuales y bigramas iniciales
    tokens = tokenize(intro_text)
    bigrams = extract_bigrams(intro_text)
    all_tokens = tokens + bigrams
    if not all_tokens:
        return 0
        
    # Contar coincidencias con HOOK_WORDS
    hook_matches = [t for t in all_tokens if t in HOOK_WORDS]
    match_count = len(hook_matches)
    
    if match_count == 0:
        return 15
    elif match_count == 1:
        return 50
    elif match_count == 2:
        return 80
    else:
        return 100

def calculate_mismatch_index(title, tags, transcript):
    """
    Mide el porcentaje de desajuste temático entre el título/tags y la transcripción del video.
    Un valor de 100 indica clickbait absoluto (desajuste total); 0 indica coherencia absoluta.
    """
    title_tokens = set(tokenize(title))
    if isinstance(tags, list):
        for tag in tags:
            title_tokens.update(tokenize(tag))
    elif isinstance(tags, str):
        title_tokens.update(tokenize(tags))
        
    if not title_tokens:
        return 0
        
    transcript_tokens = set(tokenize(transcript))
    if not transcript_tokens:
        return 100 # Desajuste total si no hay transcripción pero hay título
        
    intersection = title_tokens.intersection(transcript_tokens)
    overlap = len(intersection) / len(title_tokens)
    
    mismatch = 1.0 - overlap
    return int(mismatch * 100)

def fallback_communities(G):
    """
    Algoritmo de clustering voraz simple de respaldo si Louvain/Greedy Modularity de NetworkX fallan.
    """
    communities = list(nx.connected_components(G))
    if len(communities) == 1 and len(G.nodes) > 6:
        # Si hay un solo componente gigante, intentamos subdividirlo rudimentariamente por grados
        degrees = dict(G.degree())
        avg_degree = sum(degrees.values()) / len(G.nodes)
        c1 = {n for n in G.nodes if degrees[n] >= avg_degree}
        c2 = {n for n in G.nodes if degrees[n] < avg_degree}
        return [c1, c2]
    return communities


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

def get_video_keywords(video, max_transcript_words=12):
    """
    Extrae un conjunto enriquecido de palabras clave y frases de 2 palabras (bigramas) para un video.
    """
    keywords = set()
    
    # 1. Título (siempre se incluye por su relevancia temática)
    title_text = video.get("title", "")
    keywords.update(tokenize(title_text))
    keywords.update(extract_bigrams(title_text))
    
    # 2. Etiquetas del video (tags oficiales)
    tags = video.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            keywords.update(tokenize(tag))
            keywords.update(extract_bigrams(tag))
    elif isinstance(tags, str):
        keywords.update(tokenize(tags))
        keywords.update(extract_bigrams(tags))
            
    # 3. Descripción y Transcripción (obtenemos los N términos más frecuentes del cuerpo)
    desc_text = video.get("description", "")
    transcript_text = video.get("transcript", "")
    video_id = video.get("video_id")
    if not transcript_text and video_id:
        transcripts_dir = os.path.join("config", "cache", "transcripts")
        cache_path = os.path.join(transcripts_dir, f"{video_id}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    transcript_text = data.get("transcript", "")
            except Exception:
                pass
                
    desc_words = tokenize(desc_text)
    trans_words = tokenize(transcript_text)
    all_unigrams = desc_words + trans_words
    
    desc_bigrams = extract_bigrams(desc_text)
    trans_bigrams = extract_bigrams(transcript_text)
    all_bigrams = desc_bigrams + trans_bigrams
    
    if all_unigrams:
        counter_uni = Counter(all_unigrams)
        top_uni = [w for w, count in counter_uni.most_common(max_transcript_words)]
        keywords.update(top_uni)
        
    if all_bigrams:
        counter_bi = Counter(all_bigrams)
        top_bi = [w for w, count in counter_bi.most_common(max_transcript_words // 2)]
        keywords.update(top_bi)
        
    return list(keywords)

def generate_viral_graph_data(videos, video_type_filter="all", min_frequency=2, max_nodes=50):
    """
    Genera un objeto Graph de networkx enriquecido con métricas de red avanzadas
    (PageRank, Centralidad de Intermediación, Comunidades) y un listado ordenado
    de palabras clave, además de calcular métricas de retención en cada video.
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
        
    # Calcular Hook Score y Mismatch Index para cada video filtrado (estrictamente de caché local de disco)
    transcripts_dir = os.path.join("config", "cache", "transcripts")
    for v in filtered_videos:
        video_id = v.get("video_id")
        transcript = v.get("transcript", "")
        if not transcript and video_id:
            cache_path = os.path.join(transcripts_dir, f"{video_id}.json")
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        transcript = data.get("transcript", "")
                except Exception:
                    transcript = ""
            else:
                transcript = ""
            
        v["hook_score"] = calculate_hook_score(transcript)
        v["mismatch_index"] = calculate_mismatch_index(v.get("title", ""), v.get("tags", []), transcript)
        v["pacing_wpm"] = calculate_pacing_wpm(transcript, v.get("duration", 0))
        
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
    
    # Añadir nodos temporales para poder calcular las aristas antes de las métricas complejas de red
    for w in valid_words:
        G.add_node(w)
        
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
        
    # Calcular Métricas Avanzadas sobre el grafo finalizado
    # A. PageRank (Influencia estructural de la palabra)
    try:
        pagerank_scores = nx.pagerank(G, weight='weight')
    except Exception:
        # Fallback basado en grado ponderado normalizado para obtener porcentajes reales (suma = 1.0)
        degrees = {n: G.degree(n, weight='weight') for n in G.nodes}
        total_degree = sum(degrees.values())
        if total_degree > 0:
            pagerank_scores = {n: degrees[n] / total_degree for n in G.nodes}
        else:
            pagerank_scores = {n: 1.0 / len(G.nodes) for n in G.nodes}
        
    # B. Centralidad de Intermediación (Conceptos Puente)
    try:
        betweenness_scores = nx.betweenness_centrality(G, weight='weight')
    except Exception:
        betweenness_scores = {n: 0.0 for n in G.nodes}
        
    # C. Detección de Comunidades Temáticas (Pilares de Contenido)
    community_list = None
    if louvain_communities is not None:
        try:
            community_list = louvain_communities(G, seed=42)
        except Exception:
            pass
            
    if community_list is None:
        community_list = fallback_communities(G)
        
    node_communities = {}
    for comm_id, nodes_set in enumerate(community_list):
        for node in nodes_set:
            node_communities[node] = comm_id
            
    # Añadir atributos a los nodos y recopilar word_data_list
    word_data_list = []
    for w in valid_words:
        freq = word_freq[w]
        scores = word_scores[w]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        pr = pagerank_scores.get(w, 0.0)
        bt = betweenness_scores.get(w, 0.0)
        comm = node_communities.get(w, 0)
        
        # Enriquecer atributos en el grafo
        G.nodes[w]['frequency'] = freq
        G.nodes[w]['avg_score'] = avg_score
        G.nodes[w]['pagerank'] = pr
        G.nodes[w]['betweenness'] = bt
        G.nodes[w]['community'] = comm
        
        word_data_list.append({
            "word": w,
            "frequency": freq,
            "avg_score": avg_score,
            "pagerank": pr,
            "betweenness": bt,
            "community": comm
        })
        
    # Ordenar tabla de palabras por score promedio descendente
    word_data_list.sort(key=lambda x: x["avg_score"], reverse=True)
    
    return G, word_data_list


def get_friendly_rank(score):
    """Devuelve una etiqueta descriptiva y legible para cada rango de puntaje."""
    if score >= 90:
        return "S+ (Viralidad Extrema)"
    elif score >= 80:
        return "S (Excelente)"
    elif score >= 70:
        return "A (Muy Alto)"
    elif score >= 50:
        return "B (Bueno)"
    elif score >= 30:
        return "C (Regular)"
    else:
        return "D (Bajo)"


def generate_creative_insights(videos, word_data_list, G):
    """
    Analiza el grafo y los datos de palabras clave para generar recomendaciones creativas,
    fórmulas de éxito e ideas de títulos en un lenguaje no técnico y accionable.
    """
    if not word_data_list or G.number_of_nodes() == 0:
        return {
            "best_topics": [],
            "winning_combos": [],
            "actionable_tips": [
                "Sube más videos con transcripciones para que el sistema detecte tus temas fuertes y genere recomendaciones.",
                "Actualiza la API si has subido nuevo contenido para refrescar los datos."
            ],
            "title_ideas": [
                "El misterio que la televisión intentó ocultar...",
                "El metraje perdido de la cabaña abandonada",
                "Cintas de VHS encontradas: No veas este video solo"
            ]
        }
    
    # 1. Temas con mayor impacto (Puntaje >= 60 y Frecuencia >= 2)
    high_impact_words = [w for w in word_data_list if w["avg_score"] >= 60 and w["frequency"] >= 2]
    # Si no hay, tomar las top 3 con mayor score en general
    if not high_impact_words:
        high_impact_words = sorted([w for w in word_data_list if w["frequency"] >= 1], key=lambda x: x["avg_score"], reverse=True)[:3]
    else:
        high_impact_words = sorted(high_impact_words, key=lambda x: x["avg_score"], reverse=True)[:5]
        
    # 2. Fórmulas ganadoras (co-ocurrencias de alta puntuación, peso >= 2)
    combos = []
    for u, v, data in G.edges(data=True):
        weight = data.get("weight", 0)
        if weight >= 2:
            score_u = G.nodes[u].get("avg_score", 0)
            score_v = G.nodes[v].get("avg_score", 0)
            combo_score = (score_u + score_v) / 2
            combos.append({
                "word1": u,
                "word2": v,
                "weight": weight,
                "score": combo_score
            })
            
    # Ordenar combos por score
    combos.sort(key=lambda x: x["score"], reverse=True)
    winning_combos = combos[:3]
    
    # 3. Generar consejos accionables
    tips = []
    
    def get_perf_desc(score):
        if score >= 80: return "excelente"
        if score >= 60: return "bueno"
        if score >= 45: return "regular"
        return "bajo/regular"

    # A. Identificar palabra catalizadora por PageRank
    top_pr_word = max(word_data_list, key=lambda x: x["pagerank"])
    tips.append(
        f"👑 **Catalizador de Red ('{top_pr_word['word']}'):** Es tu concepto estructural más influyente según PageRank (Influencia: {top_pr_word['pagerank']:.3f}). "
        f"Úsalo como ancla en tus miniaturas y descripciones para disparar el CTR."
    )
    
    # B. Identificar palabra puente por Betweenness
    bridge_words = [w for w in word_data_list if w["betweenness"] > 0.0]
    if bridge_words:
        top_bridge = max(bridge_words, key=lambda x: x["betweenness"])
        tips.append(
            f"🌉 **Concepto Puente ('{top_bridge['word']}'):** Tiene la mayor centralidad de intermediación ({top_bridge['betweenness']:.2f}). "
            f"Es la palabra ideal para transicionar o mezclar temáticas en el canal sin perder audiencia."
        )
        
    # C. Análisis de Retención (Hook & Mismatch) sobre videos reales del formato
    low_perf_videos = [v for v in videos if v.get("score") is not None and v.get("score") < 45]
    if low_perf_videos:
        mismatched = [v for v in low_perf_videos if v.get("mismatch_index", 0) >= 50]
        bad_hooks = [v for v in low_perf_videos if v.get("hook_score", 0) <= 30]
        
        if mismatched:
            mismatched.sort(key=lambda x: x.get("mismatch_index"), reverse=True)
            v_m = mismatched[0]
            tips.append(
                f"⚠️ **Alerta de Desajuste (Mismatch):** En tu video \"{v_m.get('title')[:35]}...\" hay un desajuste del {v_m.get('mismatch_index')}% entre "
                f"el título/etiquetas y los temas hablados en el audio. Esto genera caídas rápidas de retención. Cuida la coherencia."
            )
            
        if bad_hooks:
            v_h = bad_hooks[0]
            tips.append(
                f"🚨 **Gancho Inicial Débil:** Tu video \"{v_h.get('title')[:35]}...\" tiene un Hook Score muy bajo ({v_h.get('hook_score')}/100) en los primeros 30s. "
                f"Evita intros lentas o explicaciones largas sin intriga inicial."
            )

    if high_impact_words:
        top_topic = high_impact_words[0]["word"]
        top_score = int(high_impact_words[0]["avg_score"])
        tips.append(f"🔥 **Foco de Audiencia:** '{top_topic}' promedia un rendimiento {get_perf_desc(top_score)} de {top_score} pts ({get_friendly_rank(top_score)}). Sigue explotando esta temática.")
    else:
        tips.append("Continúa subiendo videos para acumular más estadísticas estructurales sobre tus palabras clave.")
        
    if winning_combos:
        c = winning_combos[0]
        w1, w2 = c["word1"], c["word2"]
        tips.append(f"✨ **Conexión Algorítmica:** '{w1}' y '{w2}' forman una sinergia ganadora. Úsalas juntas en títulos y en los primeros 30 segundos del video.")

    # 4. Generar ideas de títulos
    title_ideas = []
    # Generar de acuerdo a palabras clave de alto impacto o combinaciones
    if winning_combos:
        c = winning_combos[0]
        w1, w2 = c["word1"], c["word2"]
        title_ideas.append(f"El oscuro misterio de {w1} y {w2} en la vida real")
        title_ideas.append(f"Cintas de {w1} encontradas: Revelando el secreto de {w2}")
        title_ideas.append(f"La inquietante historia de {w1} que {w2} ocultó")
    elif high_impact_words:
        w1 = high_impact_words[0]["word"]
        w2 = high_impact_words[1]["word"] if len(high_impact_words) > 1 else "terror"
        title_ideas.append(f"¿Por qué {w1} es el mayor peligro del que nadie habla?")
        title_ideas.append(f"El misterio oculto detrás de {w1} ({w2} real)")
        title_ideas.append(f"Historias de {w1} que te perturbarán por completo")
    else:
        title_ideas.append("El misterio que la televisión intentó ocultar...")
        title_ideas.append("El metraje perdido de la cabaña abandonada")
        title_ideas.append("Cintas de VHS encontradas: No veas este video solo")
        
    return {
        "best_topics": high_impact_words,
        "winning_combos": winning_combos,
        "actionable_tips": tips,
        "title_ideas": title_ideas
    }


def get_cached_transcript(video_id):
    """Obtiene la transcripción de un video desde la caché local de disco, o la descarga si no existe."""
    import os
    import json
    
    # 1. Intentar usar fetch_video_transcript de analytics_client para descarga automática y caché
    try:
        from modules.analytics_client import fetch_video_transcript
        transcript = fetch_video_transcript(video_id)
        if transcript:
            return transcript
    except Exception as e:
        print(f"Error descargando transcripción en tiempo real para {video_id}: {e}")
        
    # 2. Fallback de lectura directa de caché por si acaso
    transcripts_dir = os.path.join("config", "cache", "transcripts")
    cache_path = os.path.join(transcripts_dir, f"{video_id}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("transcript", "")
        except Exception:
            pass
    return ""



def safe_parse_date(date_str):
    """Parsea de forma segura fechas en formato DD/MM/YYYY y YYYY-MM-DD."""
    import datetime
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.datetime.min



def fetch_groq_creative_insights(api_key, word_data_list, winning_combos, video_type, all_videos=None, prompt_master_title=None, prompt_master_content=None):
    """
    Realiza una solicitud HTTP POST a la API de Groq para generar un informe creativo
    de YouTube hiper-personalizado a partir del grafo y las palabras clave, inyectando
    métricas avanzadas de PageRank, Comunidades, Hook Score y Mismatch Index.
    Además, audita y propone mejoras directamente sobre el Prompt Maestro activo del canal.
    """
    import urllib.request
    import json
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    # Formatear datos de palabras clave inyectando PageRank y Comunidad
    concept_str = "\n".join([
        f"- {item['word']} (Comunidad Temática: Pilar #{item['community']}, Influencia PageRank: {item['pagerank']:.3f}, Puntaje promedio: {int(item['avg_score'])} pts)" 
        for item in word_data_list[:10]
    ])
    
    # Obtener palabras puente de intermediación
    bridge_words = sorted([w for w in word_data_list if w["betweenness"] > 0.0], key=lambda x: x["betweenness"], reverse=True)[:3]
    bridge_str = "\n".join([
        f"- '{item['word']}' (Centralidad de Intermediación / Puente: {item['betweenness']:.2f})"
        for item in bridge_words
    ]) if bridge_words else "- No se detectaron conceptos puente significativos."
    
    combo_str = "\n".join([
        f"- '{c['word1']}' + '{c['word2']}' (Puntaje promedio combinado: {int(c['score'])} pts)" 
        for c in winning_combos
    ])
    
    # Map the selected format to the corresponding video type string in the database
    target_type = None
    format_name = "VIDEOS"
    if video_type == "Shorts":
        target_type = "shorts"
        format_name = "SHORTS"
    elif video_type == "Videos Largos":
        target_type = "long"
        format_name = "VIDEOS LARGOS"
    elif video_type == "Directos":
        target_type = "live"
        format_name = "DIRECTOS"
        
    # Comparar Videos Exitosos vs Bajo Rendimiento del formato actual
    comparison_str = ""
    if all_videos:
        # Filtrar videos del formato seleccionado que tengan puntuación
        candidates = [
            v for v in all_videos 
            if (target_type is None or v.get("type", "").lower() == target_type) 
            and v.get("score") is not None
        ]
        
        # 1. Ordenar cronológicamente descendente (más nuevos primero)
        candidates.sort(key=lambda x: safe_parse_date(x.get("date", "")), reverse=True)
        
        # 2. Tomar únicamente una muestra de los 12 más recientes
        recent_candidates = candidates[:12]
        
        if len(recent_candidates) >= 2:
            # 3. De estos recientes, ordenar por score de mayor a menor para buscar los extremos en el lote reciente
            recent_candidates.sort(key=lambda x: x["score"], reverse=True)
            
            top_candidates = recent_candidates[:2]
            if len(recent_candidates) >= 4:
                bottom_candidates = recent_candidates[-2:]
            else:
                bottom_candidates = [recent_candidates[-1]] if recent_candidates[1:] else []
                
            comparison_str = f"AUDITORÍA DE {format_name} RECIENTES (COMPARATIVA DE LOS ÚLTIMOS PUBLICADOS):\n\n"
            
            comparison_str += f"--- {format_name} RECIENTES MÁS EXITOSOS (MAYOR RETENCIÓN/INTERACCIÓN) ---\n"
            for v in top_candidates:
                title = v.get("title", "Sin título")
                score = v.get("score", 0)
                rank = v.get("rank", "D")
                video_id = v.get("video_id", "")
                date_published = v.get("date", "Fecha desconocida")
                h_score = v.get("hook_score", 0)
                mism = v.get("mismatch_index", 0)
                pacing = v.get("pacing_wpm", 0)
                pacing_str = f"{pacing} WPM (Ritmo de Habla)" if pacing > 0 else "N/A"
                transcript = get_cached_transcript(video_id)[:500].strip()
                if not transcript:
                    transcript = "(Sin transcripción en caché local o no disponible)"
                comparison_str += f"- Título: \"{title}\" (Fecha: {date_published}, Puntaje: {score}/100, Rango: {rank})\n  Gancho (Hook Score): {h_score}/100, Ritmo Narrativo: {pacing_str}, Desajuste Título-Audio (Mismatch): {mism}%\n  Gancho/Transcripción: {transcript}\n\n"
                
            comparison_str += f"--- {format_name} RECIENTES DE BAJO RENDIMIENTO (MENOR RETENCIÓN/INTERACCIÓN) ---\n"
            for v in bottom_candidates:
                title = v.get("title", "Sin título")
                score = v.get("score", 0)
                rank = v.get("rank", "D")
                video_id = v.get("video_id", "")
                date_published = v.get("date", "Fecha desconocida")
                h_score = v.get("hook_score", 0)
                mism = v.get("mismatch_index", 0)
                pacing = v.get("pacing_wpm", 0)
                pacing_str = f"{pacing} WPM (Ritmo de Habla)" if pacing > 0 else "N/A"
                transcript = get_cached_transcript(video_id)[:500].strip()
                if not transcript:
                    transcript = "(Sin transcripción en caché local o no disponible)"
                comparison_str += f"- Título: \"{title}\" (Fecha: {date_published}, Puntaje: {score}/100, Rango: {rank})\n  Gancho (Hook Score): {h_score}/100, Ritmo Narrativo: {pacing_str}, Desajuste Título-Audio (Mismatch): {mism}%\n  Gancho/Transcripción: {transcript}\n\n"
                
    prompt = (
        f"Analiza los siguientes datos de rendimiento y co-ocurrencia de mi canal de YouTube (temática: terror/misterio/creepypastas/terror analógico) para el formato: '{video_type}'.\n\n"
        "CONTEXTO DEL CANAL Y SISTEMA DE PUNTUACIÓN (SCORE):\n"
        "- La META del canal es maximizar la retención de audiencia (que se queden viendo el video sin hacer swipe away) y la tasa de interacción para viralizar el contenido.\n"
        "- El Puntaje (0-100) mide el rendimiento real: pondera un 55% la retención de audiencia (AVP) y un 45% la interacción del público (likes, comentarios, compartidos), sumando bonus por suscriptores ganados y volumen total de vistas.\n"
        "- Rangos de Viralidad:\n"
        "  * S+ (90-100): Viralidad Extrema.\n"
        "  * S (80-89): Excelente retención e interacción.\n"
        "  * A (70-79): Rendimiento Muy Alto.\n"
        "  * B (50-69): Rendimiento Bueno.\n"
        "  * C (30-49): Rendimiento Regular.\n"
        "  * D (0-29): Rendimiento Bajo / Insuficiente (problemas severos de retención inicial, ganchos aburridos o falta de interacción).\n\n"
        f"ESTRUCTURA DE RED Y CONCEPTOS CLAVE (PageRank & Comunidades):\n{concept_str}\n\n"
        f"CONCEPTOS PUENTE DETECTADOS (Alta Intermediación / Betweenness):\n{bridge_str}\n\n"
        f"COMBINACIONES DE TEMAS MÁS EXITOSAS EN EL GRAFO:\n{combo_str}\n\n"
    )
    
    if prompt_master_content:
        prompt += (
            f"PROMPT MAESTRO ACTUAL EN USO ('{prompt_master_title or 'Prompt Maestro Activo'}'):\n"
            f"--- INICIO DEL PROMPT MAESTRO ACTUAL ---\n"
            f"{prompt_master_content.strip()}\n"
            f"--- FIN DEL PROMPT MAESTRO ACTUAL ---\n\n"
        )

    if comparison_str:
        prompt += f"{comparison_str}\n\n"
        
    prompt_master_instructions = ""
    if prompt_master_content:
        prompt_master_instructions = (
            f"5. **Auditoría Crítica y Propuesta de Mejora al Prompt Maestro ('{prompt_master_title or 'Prompt Maestro Activo'}')**:\n"
            f"   - Audita punto por punto el Prompt Maestro actual presentado arriba frente a los datos reales de retención y métricas obtenidas.\n"
            f"   - Señala con precisión qué instrucciones actuales son débiles, ambiguas o contradictorias con respecto a los ganchos o ritmo narrativo de los videos más virales.\n"
            f"   - Presenta tus **Propuestas de Mejora Concretas** (qué agregar, modificar o eliminar de las instrucciones actuales).\n"
            f"   - Redacta la **VERSIÓN FINAL MEJORADA Y RE-OPTIMIZADA DE TU PROMPT MAESTRO** en un bloque de código markdown `code block` independiente para que sea fácil de copiar y reemplazar en el Generador de Shorts."
        )
    else:
        prompt_master_instructions = (
            "5. **Sugerencia de Prompt Maestro (IA)**: Redacta un 'Prompt Maestro' hiper-optimizado listo para copiar y pegar en el Generador de Shorts (Paso 1). Este prompt debe ordenar a la IA generar un guion que aplique la estructura exacta, el ritmo de locución óptimo detectado (WPM), el gancho inicial ganador y las palabras clave de mayor rendimiento semántico obtenidas en este análisis. Escribe el prompt en un bloque de código markdown `code block` independiente para que sea fácil de copiar."
        )

    prompt += (
        "Genera un informe estratégico breve, sumamente directo y accionable en español. Responde en formato markdown simple, estructurándolo de la siguiente forma:\n"
        "1. **Análisis Algorítmico**: Explica brevemente por qué las combinaciones más exitosas del grafo están funcionando y qué pilares temáticos de tu red (comunidades) dominan la viralidad.\n"
        f"2. **Auditoría Creativa de {video_type} Recientes**: Compara críticamente las transcripciones o títulos de los contenidos exitosos recientes con los de bajo rendimiento reciente. Analiza en profundidad sus ganchos de 3-5 segundos (Hook Score), su Ritmo Narrativo (WPM - Words Per Minute) y sus índices de desajuste (Mismatch). Señala errores de velocidad de locución (ej: muy lento < 140 WPM o muy rápido) o ganchos poco intrigantes en los videos malos, y da consejos crudos y directos de qué corregir en su ritmo de locución.\n"
        "3. **Ideas de Títulos Virales**: Sugiere 3 títulos intrigantes y con alto CTR basados en tus hallazgos.\n"
        f"4. **Gancho de Retención (Hooks)**: Describe cómo estructurar la introducción de tu próximo video/contenido de este formato usando la fórmula ganadora.\n"
        f"{prompt_master_instructions}"
    )
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    models = ["llama-3.1-8b-instant", "llama-3.3-70b-specdec", "llama3-8b-8192", "llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3-70b-8192"]
    last_error = None
    import urllib.error
    
    for model in models:
        try:
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un consultor analítico de YouTube experto en canales de terror y misterio. Hablas de forma profesional, breve, inspiradora y extremadamente directa. Tu foco es el éxito de retención y el CTR."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1800
            }
            
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=25) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as he:
            try:
                err_body = he.read().decode("utf-8")
                err_json = json.loads(err_body)
                err_msg = err_json.get("error", {}).get("message", err_body)
                last_error = f"HTTP {he.code}: {err_msg}"
                if he.code in [401, 403]:
                    break
            except Exception:
                last_error = f"HTTP {he.code}: {he.reason}"
                if he.code in [401, 403]:
                    break
            continue
        except Exception as e:
            last_error = str(e)
            continue
            
    raise RuntimeError(f"Fallo en la comunicación con Groq (Todos los modelos fallaron): {last_error}")


