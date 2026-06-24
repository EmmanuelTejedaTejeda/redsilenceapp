import os
import json
import pickle
import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes oficiales para YouTube Data API y YouTube Analytics API
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly"
]

def get_authenticated_services(client_secrets_path, token_path):
    """
    Autentica con Google OAuth2 y retorna los clientes para YouTube Analytics (v2) y YouTube Data (v3).
    """
    credentials = None
    if os.path.exists(token_path):
        try:
            with open(token_path, "rb") as token:
                credentials = pickle.load(token)
        except Exception as e:
            print(f"Error cargando token de caché: {e}")
            credentials = None
            
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as e:
                print(f"Error al refrescar token, requiriendo re-autenticación: {e}")
                credentials = None

        if not credentials:
            if not os.path.exists(client_secrets_path):
                raise FileNotFoundError(f"No se encuentra el archivo de credenciales de cliente: {client_secrets_path}")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            credentials = flow.run_local_server(port=0)
            
        # Guardar credenciales para la próxima sesión
        with open(token_path, "wb") as token:
            pickle.dump(credentials, token)
            
    analytics_service = build("youtubeAnalytics", "v2", credentials=credentials)
    youtube_service = build("youtube", "v3", credentials=credentials)
    
    return analytics_service, youtube_service

def load_metrics_cache():
    cache_path = os.path.join("config", "cache", "metrics_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando caché de métricas: {e}")
    return {}

def save_metrics_cache(cache):
    cache_path = os.path.join("config", "cache", "metrics_cache.json")
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando caché de métricas: {e}")

def fetch_channel_data_and_analytics(client_secrets_path, token_path):
    """
    Obtiene los datos del canal (nombre, suscriptores, foto de perfil) y 
    las métricas de los últimos 30 días de YouTube Analytics, con caché diaria.
    """
    try:
        analytics, youtube = get_authenticated_services(client_secrets_path, token_path)
        
        # 1. Obtener información básica del canal autenticado (id, snippet, statistics)
        channel_response = youtube.channels().list(
            part="snippet,statistics",
            mine=True
        ).execute()
        
        if not channel_response.get("items"):
            raise ValueError("No se encontraron canales asociados con estas credenciales.")
            
        channel_item = channel_response["items"][0]
        channel_id = channel_item["id"]
        
        # Comprobar si existe caché reciente (duración máxima: 2 horas)
        metrics_cache = load_metrics_cache()
        if channel_id in metrics_cache:
            cached_data = metrics_cache[channel_id]
            cache_time = cached_data.get("timestamp")
            is_valid = False
            if cache_time:
                now = datetime.datetime.now().timestamp()
                if now - cache_time < 7200: # 2 horas (7200 segundos)
                    is_valid = True
            else:
                # Fallback retrocompatible
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                if cached_data.get("cached_at") == today_str:
                    is_valid = True
            if is_valid:
                print(f"Cargando métricas del canal {channel_id} desde caché local de disco.")
                return cached_data["summary"]
        
        # Si no hay caché o es antigua, realizar las consultas completas
        channel_name = channel_item["snippet"]["title"]
        subscribers = channel_item["statistics"].get("subscriberCount", "0")
        profile_pic_url = channel_item["snippet"]["thumbnails"]["default"]["url"]
        
        # 2. Consultar YouTube Analytics de los últimos 30 días
        end_date = datetime.date.today() - datetime.timedelta(days=1)
        start_date = end_date - datetime.timedelta(days=30)
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        metrics = "views,likes,comments,shares,subscribersGained,subscribersLost,estimatedMinutesWatched,averageViewDuration"
        
        # Reporte diario (para los gráficos)
        daily_report = analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_str,
            endDate=end_str,
            metrics=metrics,
            dimensions="day"
        ).execute()
        
        # Parsear filas del reporte diario
        headers = [col["name"] for col in daily_report.get("columnHeaders", [])]
        rows = daily_report.get("rows", [])
        
        # Transformar en un listado de diccionarios de días
        daily_data = []
        for row in rows:
            day_entry = dict(zip(headers, row))
            daily_data.append(day_entry)
            
        # Ordenar diariamente por fecha
        daily_data = sorted(daily_data, key=lambda x: x.get("day", ""))
        
        # Calcular agregados
        total_views = sum(int(d.get("views", 0)) for d in daily_data)
        total_likes = sum(int(d.get("likes", 0)) for d in daily_data)
        total_comments = sum(int(d.get("comments", 0)) for d in daily_data)
        total_shares = sum(int(d.get("shares", 0)) for d in daily_data)
        subs_gained = sum(int(d.get("subscribersGained", 0)) for d in daily_data)
        subs_lost = sum(int(d.get("subscribersLost", 0)) for d in daily_data)
        net_subs = subs_gained - subs_lost
        total_minutes = sum(int(d.get("estimatedMinutesWatched", 0)) for d in daily_data)
        
        avg_duration = 0
        if daily_data:
            avg_duration = sum(float(d.get("averageViewDuration", 0)) for d in daily_data) / len(daily_data)
            
        summary = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "subscribers": subscribers,
            "profile_pic": profile_pic_url,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "net_subscribers": net_subs,
            "watch_time_hours": round(total_minutes / 60.0, 1),
            "average_duration_seconds": round(avg_duration, 1),
            "daily_history": daily_data
        }
        
        # Guardar en caché con marca de tiempo actual
        metrics_cache[channel_id] = {
            "summary": summary,
            "timestamp": datetime.datetime.now().timestamp()
        }
        save_metrics_cache(metrics_cache)
        
        return summary
        
    except Exception as e:
        print(f"Error al obtener métricas reales de YouTube Analytics: {e}")
        raise e

def get_mock_channel_analytics(channel_name="Canal de Simulación"):
    """
    Retorna métricas simuladas de alta calidad para pruebas o desarrollo sin conexión.
    """
    import random
    
    end_date = datetime.date.today() - datetime.timedelta(days=1)
    daily_data = []
    
    # Generar 30 días de historia realista
    for i in range(30, 0, -1):
        day = end_date - datetime.timedelta(days=i)
        views = random.randint(1500, 4800)
        likes = int(views * random.uniform(0.08, 0.15))
        comments = int(views * random.uniform(0.01, 0.03))
        shares = int(views * random.uniform(0.02, 0.05))
        gained = random.randint(10, 45)
        lost = random.randint(2, 8)
        min_watched = int(views * random.uniform(1.2, 2.5))
        avg_dur = random.randint(45, 120)
        
        daily_data.append({
            "day": day.strftime("%Y-%m-%d"),
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "subscribersGained": gained,
            "subscribersLost": lost,
            "estimatedMinutesWatched": min_watched,
            "averageViewDuration": avg_dur
        })
        
    total_views = sum(d["views"] for d in daily_data)
    total_likes = sum(d["likes"] for d in daily_data)
    total_comments = sum(d["comments"] for d in daily_data)
    total_shares = sum(d["shares"] for d in daily_data)
    net_subs = sum(d["subscribersGained"] - d["subscribersLost"] for d in daily_data)
    total_minutes = sum(d["estimatedMinutesWatched"] for d in daily_data)
    avg_dur = sum(d["averageViewDuration"] for d in daily_data) / len(daily_data)
    
    summary = {
        "channel_id": "MOCK_CHANNEL_ID",
        "channel_name": channel_name,
        "subscribers": "14,820",
        "profile_pic": f"https://picsum.photos/100/100?random={abs(hash(channel_name)) % 100}",
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "net_subscribers": net_subs,
        "watch_time_hours": round(total_minutes / 60.0, 1),
        "average_duration_seconds": round(avg_dur, 1),
        "daily_history": daily_data
    }
    
    return summary

def parse_iso8601_duration(duration_str):
    """
    Convierte una duración en formato ISO 8601 (ej. PT1M30S o PT45S) a segundos.
    """
    import re
    match = re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 60  # Fallback default
    minutes = int(match.group(1)) if match.group(1) else 0
    seconds = int(match.group(2)) if match.group(2) else 0
    return minutes * 60 + seconds

def calculate_video_score(views, likes, comments, shares, subs_gained, avg_duration, duration_seconds, video_type="shorts"):
    """
    Calcula el puntaje (0-100) y rango (S+, S, A, B, C, D, F) de un video corto (Short), largo (Long) o directo (Live).
    Si los datos de retención están ausentes (porque el video es muy nuevo y Analytics aún no
    lo ha procesado, lo que da avg_duration == 0), calcula el score basándose 100% en interacciones
    para evitar penalizaciones injustas.
    """
    if views <= 0:
        return 0, "D", "#555555"
        
    # 1. Puntos de Interacción (Peso: 45% en fórmula consolidada, o 100% si no hay retención)
    # Fórmula ponderada: (Likes + 5*Comments + 10*Shares) / (Views + 50) [Suavizado Bayesiano para evitar tasas infladas en pocas vistas]
    # Nota: Si se consulta la Data API (fallback de videos nuevos), shares será 0.
    interaction_rate = (likes + (5 * comments) + (10 * shares)) / (views + 50)
    
    if interaction_rate >= 0.12:
        int_score = 100
    elif interaction_rate >= 0.08:
        int_score = 80 + (interaction_rate - 0.08) * (20 / 0.04)
    elif interaction_rate >= 0.04:
        int_score = 50 + (interaction_rate - 0.04) * (30 / 0.04)
    else:
        int_score = (interaction_rate / 0.04) * 50

    # 2. Comprobar si los datos de Analytics (Retención) aún están pendientes
    if avg_duration <= 0:
        # Los datos de Analytics aún no están procesados (común en las primeras 48-72 horas).
        # Para no penalizar el video con un 0 en retención y suscriptores, basamos el 100% del score en la interacción.
        base_score = int_score
        subs_bonus = 0
    else:
        # Fórmula Consolidada Completa (Retención 55% + Interacción 45% + Bonus Suscriptores)
        # A. Puntos de Retención (AVP)
        if video_type == "live":
            # Para directos, evaluamos la retención en base a minutos absolutos (avg_duration en segundos)
            if avg_duration >= 600:  # 10 min
                ret_score = 100
            elif avg_duration >= 300:  # 5 min
                ret_score = 80 + (avg_duration - 300) * (20 / 300)
            elif avg_duration >= 120:  # 2 min
                ret_score = 50 + (avg_duration - 120) * (30 / 180)
            else:
                ret_score = (avg_duration / 120) * 50
        else:
            if duration_seconds <= 0:
                duration_seconds = 60
            avp = (avg_duration / duration_seconds) * 100
            
            if video_type == "long":
                # Para videos largos, la retención esperable es menor
                if avp >= 50:
                    ret_score = 100
                elif avp >= 40:
                    ret_score = 80 + (avp - 40) * (20 / 10)
                elif avp >= 25:
                    ret_score = 50 + (avp - 25) * (30 / 15)
                else:
                    ret_score = (avp / 25) * 50
            else:
                # Shorts
                if avp >= 100:
                    ret_score = 100
                elif avp >= 70:
                    ret_score = 80 + (avp - 70) * (20 / 30)
                elif avp >= 50:
                    ret_score = 50 + (avp - 50) * (30 / 20)
                else:
                    ret_score = (avp / 50) * 50

        # B. Puntaje Base
        base_score = (ret_score * 0.55) + (int_score * 0.45)

        # C. Bonus por Suscriptores ganados (Hasta +10 puntos)
        # Fórmula: Suscriptores ganados por cada 1,000 vistas
        subs_per_1k = (subs_gained / views) * 1000
        subs_bonus = min(10, subs_per_1k * 3.33)  # 3 subs/1k vistas otorga el bono máximo de +10 pts
        
    # 3. Multiplicador de credibilidad por volumen de vistas (evita puntajes inflados en videos con pocas vistas)
    # Logarítmico, llega a 1.0 a partir de ~10,000 vistas (10^4.0) para asegurar peso representativo
    import math
    view_weight = min(1.0, math.log10(views) / 4.0) if views > 1 else 0.1

    # 4. Bonus por Alcance Absoluto (Reach Bonus logarítmico, hasta +20 pts extra)
    reach_bonus = min(20, max(0, math.log10(views) * 4.5))
    
    final_score = round(max(0, min(100, (base_score + subs_bonus) * view_weight + reach_bonus)))
    
    # Asignar Rango
    if final_score >= 95:
        rank = "S+"
        color = "#FF0055"  # Neon Red Hot
    elif final_score >= 90:
        rank = "S"
        color = "#FF0000"  # Neon Red
    elif final_score >= 75:
        rank = "A"
        color = "#00FF66"  # Neon Green
    elif final_score >= 60:
        rank = "B"
        color = "#0099FF"  # Blue
    elif final_score >= 45:
        rank = "C"
        color = "#FFCC00"  # Yellow
    else:
        rank = "D"
        color = "#555555"  # Gray
        
    return final_score, rank, color

def load_metadata_cache():
    cache_path = os.path.join("config", "cache", "videos_metadata.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando caché de metadatos: {e}")
    return {}

def save_metadata_cache(cache):
    cache_path = os.path.join("config", "cache", "videos_metadata.json")
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando caché de metadatos: {e}")

def load_videos_list_cache():
    cache_path = os.path.join("config", "cache", "videos_list_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando caché de lista de videos: {e}")
    return {}

def save_videos_list_cache(cache):
    cache_path = os.path.join("config", "cache", "videos_list_cache.json")
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando caché de lista de videos: {e}")

def is_youtube_short_head_check(video_id):
    """
    Realiza una petición HEAD rápida a la URL de Shorts de YouTube para determinar
    si el video es realmente un Short (retorna True) o si redirige a la vista normal (retorna False).
    """
    import urllib.request
    import ssl
    context = ssl._create_unverified_context()
    url = f"https://www.youtube.com/shorts/{video_id}"
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5, context=context) as res:
            final_url = res.geturl()
            return "shorts" in final_url
    except Exception as e:
        print(f"Error checking Shorts redirect for {video_id}: {e}")
        return False

def fetch_video_transcript(video_id):
    """
    Obtiene la transcripción de subtítulos de un video de YouTube.
    Utiliza una caché local en disco para no realizar peticiones web duplicadas.
    """
    import os
    import json
    import time
    
    transcripts_dir = os.path.join("config", "cache", "transcripts")
    cache_path = os.path.join(transcripts_dir, f"{video_id}.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cached_text = data.get("transcript", "")
                # Si la caché contiene un error temporal previo, lo ignoramos para reintentar
                if not cached_text.startswith("[Error al obtener transcripción:"):
                    return cached_text
                else:
                    print(f"Ignorando caché con error previo para {video_id}, reintentando descarga.")
        except Exception as e:
            print(f"Error leyendo caché de transcripción para {video_id}: {e}")
            
    # Intentar descargar de YouTube usando youtube-transcript-api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # Obtener los subtítulos (por defecto intenta en español 'es', o cualquier idioma disponible)
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id, languages=['es', 'en'])
        
        # Unir los fragmentos en un solo bloque de texto de forma robusta (soporta dict y dataclass)
        full_text = " ".join([
            getattr(entry, 'text', entry.get('text') if isinstance(entry, dict) else str(entry))
            for entry in transcript_list
        ])
    except Exception as e:
        err_msg = str(e).lower()
        if "transcriptsdisabled" in err_msg or "nosubtitlesfound" in err_msg:
            full_text = "[Transcripción no disponible: Subtítulos desactivados o no encontrados en este video]"
        else:
            full_text = f"[Error al obtener transcripción: {str(e)}]"
            
    # Guardar en caché local SOLO si no es un error temporal/transitorio
    if not full_text.startswith("[Error al obtener transcripción:"):
        try:
            os.makedirs(transcripts_dir, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"video_id": video_id, "transcript": full_text, "timestamp": time.time()}, f, indent=2, ensure_ascii=False)
        except Exception as ex:
            print(f"Error guardando caché de transcripción para {video_id}: {ex}")
    else:
        # Si dio error temporal y hay un archivo de caché viejo (con error), lo eliminamos
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except Exception as ex:
                print(f"Error eliminando caché con error para {video_id}: {ex}")
        
    return full_text

def fetch_channel_videos(client_secrets_path, token_path, force_reload=False):
    """
    Obtiene los videos subidos de un canal de YouTube y calcula su score algorítmico,
    utilizando un sistema de caché para metadatos estáticos que no cambian (título, fecha, url, duración, portada).
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    try:
        analytics, youtube = get_authenticated_services(client_secrets_path, token_path)
        
        # 1. Obtener información básica del canal autenticado
        channel_response = youtube.channels().list(
            part="contentDetails,statistics",
            mine=True
        ).execute()
        
        if not channel_response.get("items"):
            raise ValueError("No se encontraron canales asociados con estas credenciales.")
            
        channel_id = channel_response["items"][0]["id"]
        uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # Comprobar caché reciente de lista procesada (duración máxima: 2 horas, si no es recarga forzada)
        if not force_reload:
            videos_list_cache = load_videos_list_cache()
            if channel_id in videos_list_cache:
                cached_entry = videos_list_cache[channel_id]
                cache_time = cached_entry.get("timestamp")
                is_valid = False
                if cache_time:
                    now = datetime.datetime.now().timestamp()
                    if now - cache_time < 7200: # 2 horas (7200 segundos)
                        is_valid = True
                else:
                    # Fallback retrocompatible
                    today_str = datetime.date.today().strftime("%Y-%m-%d")
                    if cached_entry.get("cached_at") == today_str:
                        is_valid = True
                if is_valid:
                    print(f"Cargando lista de videos del canal {channel_id} desde caché local de disco.")
                    return cached_entry["videos"]

        # Cargar caché de metadatos estáticos
        metadata_cache = load_metadata_cache()
        channel_cache = metadata_cache.get(channel_id, {})
        
        # Si force_reload es True, ignoramos la caché de metadatos para forzar la recarga completa
        if force_reload:
            channel_cache = {}
        
        # 2. Consultar los videos de esa lista de reproducción (traemos hasta 500 videos con paginación)
        playlist_items = []
        next_page_token = None
        limit = 500
        while len(playlist_items) < limit:
            playlist_response = youtube.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="snippet",
                maxResults=min(50, limit - len(playlist_items)),
                pageToken=next_page_token
            ).execute()
            
            items = playlist_response.get("items", [])
            playlist_items.extend(items)
            
            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token or not items:
                break
        
        videos = []
        cache_updated = False
        
        for item in playlist_items:
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            
            title = snippet["title"]
            published_at = snippet["publishedAt"]
            try:
                date_obj = datetime.datetime.strptime(published_at[:10], "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d/%m/%Y")
            except:
                formatted_date = published_at[:10]
                
            thumbnail = snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
            if not thumbnail:
                thumbnail = snippet.get("thumbnails", {}).get("default", {}).get("url", "")
                
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Si el video ya está en el caché del canal
            if video_id in channel_cache:
                cached_vid = channel_cache[video_id]
                duration = cached_vid.get("duration", 60)
                v_type = cached_vid.get("type")
                if not v_type:
                    v_type = "shorts" if ("#shorts" in title.lower() or duration <= 60) else "long"
                
                # Si el caché es de hoy (misma fecha de hoy), lo cargamos directamente
                if cached_vid.get("cached_at") == today_str:
                    videos.append({
                        "video_id": video_id,
                        "title": cached_vid["title"],
                        "date": cached_vid["date"],
                        "thumbnail": cached_vid["thumbnail"],
                        "url": cached_vid["url"],
                        "duration": duration,
                        "type": v_type,
                        "description": cached_vid.get("description", ""),
                        "tags": cached_vid.get("tags", [])
                    })
                else:
                    # Si el caché es antiguo (ayer o antes), usamos los datos frescos
                    # del snippet de YouTube y conservamos la duración y el tipo
                    videos.append({
                        "video_id": video_id,
                        "title": title,
                        "date": formatted_date,
                        "thumbnail": thumbnail,
                        "url": video_url,
                        "duration": duration,
                        "type": v_type,
                        "description": cached_vid.get("description", ""),
                        "tags": cached_vid.get("tags", [])
                    })
                    # Actualizamos el registro de caché con los datos frescos de hoy
                    channel_cache[video_id] = {
                        "title": title,
                        "date": formatted_date,
                        "thumbnail": thumbnail,
                        "url": video_url,
                        "duration": duration,
                        "type": v_type,
                        "description": cached_vid.get("description", ""),
                        "tags": cached_vid.get("tags", []),
                        "cached_at": today_str
                    }
                    cache_updated = True
            else:
                # Video nuevo
                videos.append({
                    "video_id": video_id,
                    "title": title,
                    "date": formatted_date,
                    "thumbnail": thumbnail,
                    "url": video_url,
                    "duration": None  # Se resolverá en el siguiente paso
                })
                
        # 3. Obtener duraciones para los videos nuevos que no las tengan en caché
        uncached_video_ids = [v["video_id"] for v in videos if v["duration"] is None]
        duration_map = {}
        type_map = {}
        description_map = {}
        tags_map = {}
        
        if uncached_video_ids:
            title_map = {v["video_id"]: v["title"] for v in videos}
            id_batches = [uncached_video_ids[i:i + 50] for i in range(0, len(uncached_video_ids), 50)]
            for batch in id_batches:
                ids_str = ",".join(batch)
                video_details = youtube.videos().list(
                    part="snippet,contentDetails,liveStreamingDetails",
                    id=ids_str
                ).execute()
                for item in video_details.get("items", []):
                    vid_id = item["id"]
                    snippet = item["snippet"]
                    description_map[vid_id] = snippet.get("description", "")
                    tags_map[vid_id] = snippet.get("tags", [])
                    
                    iso_dur = item["contentDetails"]["duration"]
                    duration_seconds = parse_iso8601_duration(iso_dur)
                    duration_map[vid_id] = duration_seconds
                    
                    # Clasificar video
                    vid_title = title_map.get(vid_id, "").lower()
                    if "liveStreamingDetails" in item:
                        v_type = "live"
                    elif "#shorts" in vid_title or duration_seconds <= 60:
                        v_type = "shorts"
                    elif duration_seconds > 180:
                        v_type = "long"
                    else:
                        # Ambiguo: Duración entre 60 y 180 segundos.
                        # Realizar verificación HEAD rápida para comprobar si es Short.
                        if is_youtube_short_head_check(vid_id):
                            v_type = "shorts"
                        else:
                            v_type = "long"
                    type_map[vid_id] = v_type
            
            # Actualizar la lista en memoria y el caché local
            for v in videos:
                if v["video_id"] in duration_map:
                    v["duration"] = duration_map[v["video_id"]]
                    v["type"] = type_map.get(v["video_id"], "shorts")
                    v["description"] = description_map.get(v["video_id"], "")
                    v["tags"] = tags_map.get(v["video_id"], [])
                    channel_cache[v["video_id"]] = {
                        "title": v["title"],
                        "date": v["date"],
                        "thumbnail": v["thumbnail"],
                        "url": v["url"],
                        "duration": v["duration"],
                        "type": v["type"],
                        "description": v["description"],
                        "tags": v["tags"],
                        "cached_at": today_str
                    }
                    cache_updated = True
            
        if cache_updated:
            metadata_cache[channel_id] = channel_cache
            save_metadata_cache(metadata_cache)
                
        # 4. Obtener analíticas de los videos (últimos 90 días). Las métricas SÍ se descargan de nuevo porque cambian.
        video_ids = [v["video_id"] for v in videos]
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=90)
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        analytics_map = {}
        if video_ids:
            try:
                ids_filter = ",".join(video_ids)
                analytics_response = analytics.reports().query(
                    ids=f"channel=={channel_id}",
                    startDate=start_str,
                    endDate=end_str,
                    metrics="views,likes,comments,shares,subscribersGained,averageViewDuration",
                    dimensions="video",
                    filters=f"video=={ids_filter}"
                ).execute()
                
                rows = analytics_response.get("rows", [])
                headers = [col["name"] for col in analytics_response.get("columnHeaders", [])]
                for row in rows:
                    entry = dict(zip(headers, row))
                    vid_id = entry.get("video")
                    analytics_map[vid_id] = entry
            except Exception as ex:
                print(f"Error consultando YouTube Analytics por video: {ex}")
                
        # 5. Calcular score y combinar
        for v in videos:
            vid_id = v["video_id"]
            duration = v.get("duration", 60)
            if duration is None or duration <= 0:
                duration = 60
            
            stats = analytics_map.get(vid_id, {})
            views = int(stats.get("views", 0))
            likes = int(stats.get("likes", 0))
            comments = int(stats.get("comments", 0))
            shares = int(stats.get("shares", 0))
            subs_gained = int(stats.get("subscribersGained", 0))
            avg_duration = float(stats.get("averageViewDuration", 0))
            
            # Fallback a estadísticas acumuladas si Analytics API aún no tiene el video indexado (videos muy nuevos)
            if views == 0:
                try:
                    data_stats = youtube.videos().list(
                        part="statistics",
                        id=vid_id
                    ).execute()
                    if data_stats.get("items"):
                        item_stats = data_stats["items"][0]["statistics"]
                        views = int(item_stats.get("viewCount", 0))
                        likes = int(item_stats.get("likeCount", 0))
                        comments = int(item_stats.get("commentCount", 0))
                except Exception as ex:
                    print(f"Error consultando estadísticas acumuladas: {ex}")
                    
            # Asegurar tipo de video para la fórmula
            v_type = v.get("type")
            if not v_type:
                vid_title = v.get("title", "").lower()
                if "#shorts" in vid_title or duration <= 60:
                    v_type = "shorts"
                elif duration > 180:
                    v_type = "long"
                else:
                    v_type = "shorts" if is_youtube_short_head_check(vid_id) else "long"
                v["type"] = v_type

            score, rank, color = calculate_video_score(
                views=views,
                likes=likes,
                comments=comments,
                shares=shares,
                subs_gained=subs_gained,
                avg_duration=avg_duration,
                duration_seconds=duration,
                video_type=v_type
            )
            
            v["views"] = views
            v["score"] = score
            v["rank"] = rank
            v["rank_color"] = color
            
        # Guardar en la caché de lista procesada con marca de tiempo actual
        try:
            videos_list_cache = load_videos_list_cache()
            videos_list_cache[channel_id] = {
                "videos": videos,
                "timestamp": datetime.datetime.now().timestamp()
            }
            save_videos_list_cache(videos_list_cache)
        except Exception as ex:
            print(f"Error guardando lista de videos en caché: {ex}")
            
        # Si es recarga forzada, eliminamos los archivos de transcripción en caché correspondientes
        if force_reload:
            try:
                transcripts_dir = os.path.join("config", "cache", "transcripts")
                if os.path.exists(transcripts_dir):
                    for v in videos:
                        v_id = v["video_id"]
                        t_cache_path = os.path.join(transcripts_dir, f"{v_id}.json")
                        if os.path.exists(t_cache_path):
                            try:
                                os.remove(t_cache_path)
                            except Exception as ex:
                                print(f"Error eliminando caché de transcripción para {v_id} en recarga forzada: {ex}")
            except Exception as ex:
                print(f"Error limpiando cachés de transcripción en recarga forzada: {ex}")
                
        return videos
    except Exception as e:
        print(f"Error al obtener videos reales del canal: {e}")
        raise e

def get_mock_channel_videos(channel_name="Canal de Simulación"):
    """
    Retorna una lista simulada de videos para pruebas con puntajes calculados.
    Contiene una mezcla de Shorts, Videos Largos y Directos.
    """
    import random
    temas = [
        "Terror en las profundidades", 
        "La casa abandonada de la colina", 
        "El secreto del sótano", 
        "Pesadilla analógica", 
        "Entidad desconocida captada en cámara", 
        "Exploración urbana paranormal", 
        "La leyenda del bosque rojo", 
        "Archivos perdidos VHS"
    ]
    
    videos = []
    end_date = datetime.date.today()
    for i in range(12):
        video_id = f"MOCK_VID_{i}"
        
        # Determinar tipo
        if i % 3 == 0:
            video_type = "shorts"
            duration = random.randint(35, 59)
            title = f"🔴 {random.choice(temas)} #shorts"
            avg_duration = duration * random.uniform(0.6, 1.1)
        elif i % 3 == 1:
            video_type = "long"
            duration = random.randint(300, 1800)  # 5 a 30 mins
            title = f"{random.choice(temas)} - Episodio {i+1} ({channel_name})"
            avg_duration = duration * random.uniform(0.3, 0.6)
        else:
            video_type = "live"
            duration = random.randint(3600, 7200)  # 1 a 2 horas
            title = f"DIRECTO PARANORMAL: {random.choice(temas)} en vivo"
            avg_duration = random.randint(180, 480)  # 3 a 8 mins promedio por espectador
            
        days_ago = i * 3 + random.randint(0, 2)
        date = end_date - datetime.timedelta(days=days_ago)
        
        # Generar estadísticas realistas para la simulación
        views = random.randint(100, 25000)
        likes = int(views * random.uniform(0.02, 0.16))
        comments = int(views * random.uniform(0.001, 0.04))
        shares = int(views * random.uniform(0.005, 0.06))
        subs_gained = int(views * random.uniform(0.001, 0.008))
        
        score, rank, color = calculate_video_score(
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            subs_gained=subs_gained,
            avg_duration=avg_duration,
            duration_seconds=duration,
            video_type=video_type
        )
        
        videos.append({
            "video_id": video_id,
            "title": title,
            "date": date.strftime("%d/%m/%Y"),
            "thumbnail": f"https://picsum.photos/80/50?random={i}",
            "url": "https://www.youtube.com/",
            "views": views,
            "score": score,
            "rank": rank,
            "rank_color": color,
            "type": video_type,
            "duration": duration,
            "description": f"Esta es una descripción simulada de prueba para '{title}'. Contiene elementos de horror, misterio y leyendas urbanas.",
            "tags": [video_type, "horror", "silenciorojo", "miedo", "paranormal"]
        })
    return videos

def get_channel_id_by_name(channel_name):
    """Resuelve el ID de canal a partir de la caché de métricas usando coincidencia de nombre (insensible a mayúsculas/espacios)."""
    cache_path = os.path.join("config", "cache", "metrics_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
                for cid, cdata in cache.items():
                    cached_name = cdata.get("summary", {}).get("channel_name", "")
                    if cached_name.lower().strip() == channel_name.lower().strip():
                        return cid
        except Exception as e:
            print(f"Error resolviendo ID de canal por nombre: {e}")
    return None

def has_valid_videos_cache(channel_name):
    """Determina si existe una caché en disco válida y no expirada (2h) para la lista de videos del canal."""
    if "simulacion" in channel_name.lower() or "mock" in channel_name.lower():
        return True
    cid = get_channel_id_by_name(channel_name)
    if not cid:
        return False
    cache_path = os.path.join("config", "cache", "videos_list_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if cid in cache:
                    cached_entry = cache[cid]
                    cache_time = cached_entry.get("timestamp")
                    if cache_time:
                        return (datetime.datetime.now().timestamp() - cache_time) < 7200
                    # Fallback retrocompatible
                    today_str = datetime.date.today().strftime("%Y-%m-%d")
                    return cached_entry.get("cached_at") == today_str
        except Exception as e:
            print(f"Error validando caché de videos: {e}")
    return False

def has_valid_metrics_cache(channel_name):
    """Determina si existe una caché en disco válida y no expirada (2h) para el resumen de métricas del canal."""
    if "simulacion" in channel_name.lower() or "mock" in channel_name.lower():
        return True
    cid = get_channel_id_by_name(channel_name)
    if not cid:
        return False
    cache_path = os.path.join("config", "cache", "metrics_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if cid in cache:
                    cached_entry = cache[cid]
                    cache_time = cached_entry.get("timestamp")
                    if cache_time:
                        return (datetime.datetime.now().timestamp() - cache_time) < 7200
                    # Fallback retrocompatible
                    today_str = datetime.date.today().strftime("%Y-%m-%d")
                    return cached_entry.get("cached_at") == today_str
        except Exception as e:
            print(f"Error validando caché de métricas: {e}")
    return False


