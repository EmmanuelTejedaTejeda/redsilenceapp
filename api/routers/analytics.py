import os
from fastapi import APIRouter, HTTPException
from api.deps import get_settings, get_groq_api_key

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _get_channel_credentials(channel_info):
    secrets = channel_info.get("credential_file") or channel_info.get("secret_path")
    channel_name = channel_info.get("name", "channel")
    token_path = os.path.join("config", f"token_{channel_name}.pickle")
    return secrets, token_path


def _format_visjs_graph(G, word_data_list):
    nodes = []
    edges = []
    if G is not None:
        for node, attrs in G.nodes(data=True):
            freq = attrs.get("frequency", 1)
            score = attrs.get("avg_score", 0.0)
            comm = attrs.get("community", 0)
            nodes.append({
                "id": str(node),
                "label": str(node),
                "value": int(freq),
                "group": int(comm),
                "title": f"Palabra: {node}\nFrecuencia: {freq}\nScore Promedio: {score:.1f}"
            })
        for u, v, attrs in G.edges(data=True):
            edges.append({
                "from": str(u),
                "to": str(v),
                "value": float(attrs.get("weight", 1.0))
            })
    return {
        "nodes": nodes,
        "edges": edges,
        "word_data": word_data_list if isinstance(word_data_list, list) else []
    }


@router.get("/{channel_name}")
def api_get_channel_analytics(channel_name: str):
    settings = get_settings()
    channel_info = next((c for c in settings.get("channels", []) if c["name"] == channel_name), None)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
        
    secrets, token = _get_channel_credentials(channel_info)
    try:
        from modules.analytics_client import fetch_channel_data_and_analytics, get_mock_channel_analytics
        if secrets and os.path.exists(secrets):
            data = fetch_channel_data_and_analytics(secrets, token)
            if data and not data.get("error"):
                return data
        return get_mock_channel_analytics(channel_name)
    except Exception as e:
        print(f"Aviso al obtener analíticas para {channel_name}: {e}")
        from modules.analytics_client import get_mock_channel_analytics
        return get_mock_channel_analytics(channel_name)


@router.get("/videos/{channel_name}")
def api_get_channel_videos_list(channel_name: str):
    settings = get_settings()
    channel_info = next((c for c in settings.get("channels", []) if c["name"] == channel_name), None)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
        
    secrets, token = _get_channel_credentials(channel_info)
    try:
        from modules.analytics_client import fetch_channel_videos, get_mock_channel_videos
        videos = []
        if secrets and os.path.exists(secrets):
            videos = fetch_channel_videos(secrets, token) or []
        if not videos:
            videos = get_mock_channel_videos(channel_name)
        return {"videos": videos}
    except Exception as e:
        print(f"Aviso al obtener videos para {channel_name}: {e}")
        from modules.analytics_client import get_mock_channel_videos
        return {"videos": get_mock_channel_videos(channel_name)}


@router.get("/video-details/{video_id}")
def api_get_video_details(video_id: str):
    from modules.analytics_client import fetch_video_transcript, load_metadata_cache, load_videos_list_cache
    
    transcript = ""
    try:
        transcript = fetch_video_transcript(video_id)
    except Exception as e:
        transcript = f"No se pudo cargar la transcripción: {e}"

    video_meta = {}
    try:
        videos_cache = load_videos_list_cache()
        for cid, cdata in videos_cache.items():
            for v in cdata.get("videos", []):
                if v.get("video_id") == video_id:
                    video_meta = v
                    break
            if video_meta:
                break

        if not video_meta:
            meta_cache = load_metadata_cache()
            for cid, cdata in meta_cache.items():
                if video_id in cdata:
                    video_meta = cdata[video_id]
                    break
    except Exception as e:
        print(f"Error buscando metadatos para {video_id}: {e}")

    # Fetch generation metadata if available
    generation_metadata = {}
    title = video_meta.get("title", "")
    if title:
        try:
            from modules.analytics_client import load_generation_metadata
            safe_title = "".join([c for c in title if c.isalnum() or c==' ']).rstrip().replace(" ", "_") or "Video_Render_Mix"
            gen_cache = load_generation_metadata()
            if safe_title in gen_cache:
                generation_metadata = gen_cache[safe_title]
        except Exception as e_gen:
            print(f"Error buscando metadatos de generacion para {title}: {e_gen}")

    return {
        "status": "success",
        "video_id": video_id,
        "transcript": transcript or "Sin transcripción disponible para este vídeo.",
        "description": video_meta.get("description") or "Sin descripción disponible para este vídeo.",
        "tags": video_meta.get("tags") or [],
        "date": video_meta.get("date") or video_meta.get("published_at", "Reciente"),
        "views": video_meta.get("views", 0),
        "likes": video_meta.get("likes", 0),
        "comments": video_meta.get("comments", 0),
        "score": video_meta.get("score", 0),
        "rank": video_meta.get("rank", "D"),
        "color": video_meta.get("rank_color") or video_meta.get("color", "#e50914"),
        "title": title,
        "generation_metadata": generation_metadata
    }


@router.get("/viral-graph/{channel_name}")
def api_get_viral_graph(channel_name: str, video_type: str = "shorts"):
    settings = get_settings()
    channel_info = next((c for c in settings.get("channels", []) if c["name"] == channel_name), None)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
        
    secrets, token = _get_channel_credentials(channel_info)
    try:
        from modules.analytics_client import fetch_channel_videos, get_mock_channel_videos
        from modules.graph_analyzer import generate_viral_graph_data
        
        videos = []
        if secrets and os.path.exists(secrets):
            videos = fetch_channel_videos(secrets, token) or []
            
        if not videos:
            videos = get_mock_channel_videos(channel_name)
            
        res = generate_viral_graph_data(videos, video_type_filter=video_type)
        if isinstance(res, tuple) and len(res) == 2:
            G, word_data_list = res
        else:
            G, word_data_list = None, []
            
        return _format_visjs_graph(G, word_data_list)
    except Exception as e:
        print(f"Aviso en grafo viral para {channel_name}: {e}")
        return {"nodes": [], "edges": [], "word_data": []}


@router.post("/viral-audit/{channel_name}")
def api_generate_viral_audit(channel_name: str, payload: dict):
    video_type = payload.get("video_type", "shorts")
    settings = get_settings()
    channel_info = next((c for c in settings.get("channels", []) if c["name"] == channel_name), None)
    if not channel_info:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
        
    groq_key = get_groq_api_key()
    if not groq_key:
        raise HTTPException(status_code=400, detail="Falta configurar la API Key de Groq.")
        
    secrets, token = _get_channel_credentials(channel_info)
    try:
        from modules.analytics_client import fetch_channel_videos, get_mock_channel_videos
        from modules.graph_analyzer import fetch_groq_creative_insights, generate_viral_graph_data
        
        videos = []
        if secrets and os.path.exists(secrets):
            videos = fetch_channel_videos(secrets, token) or []
            
        if not videos:
            videos = get_mock_channel_videos(channel_name)
            
        res = generate_viral_graph_data(videos, video_type_filter=video_type)
        if isinstance(res, tuple) and len(res) == 2:
            _, word_data_list = res
        else:
            word_data_list = []
        
        report = fetch_groq_creative_insights(
            api_key=groq_key,
            word_data_list=word_data_list,
            winning_combos=[],
            video_type=video_type,
            all_videos=videos
        )
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando informe con IA: {e}")
