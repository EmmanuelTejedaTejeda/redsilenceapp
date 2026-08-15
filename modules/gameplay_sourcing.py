import os
import random
import subprocess
import re
import yt_dlp
from modules.render_utils import get_video_duration, safe_remove

def clean_filename(name):
    return re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_').lower())

def download_youtube_gameplay(query_or_url, output_dir, status_callback=None):
    """
    Busca y descarga un video largo de YouTube usando yt-dlp.
    Retorna la ruta absoluta del archivo descargado.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Determinar si es una URL o una consulta de búsqueda
    is_url = query_or_url.startswith("http://") or query_or_url.startswith("https://")
    search_query = query_or_url if is_url else f"ytsearch1:{query_or_url}"
    
    clean_name = clean_filename(query_or_url[:30])
    output_template = os.path.join(output_dir, f"{clean_name}.%(ext)s")
    
    ydl_opts = {
        # Limitado a 720p para descargas súper rápidas, ahorro de ancho de banda y menor carga de renderizado
        'format': 'bestvideo[height<=720][ext=mp4]/best[height<=720][ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'nopart': True,  # Escribe directamente en el archivo final sin usar .part en Windows
        'download_ranges': lambda info, ctx: [{'start_time': 0, 'end_time': 300}],  # Limita la descarga a los primeros 5 minutos para ahorrar ancho de banda y espacio
        'force_keyframes_at_cuts': True,
    }
    
    if status_callback:
        status_callback(f"🌐 Buscando y conectando con YouTube...", "#FFD700")
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extraer info para obtener el archivo de salida real
            info = ydl.extract_info(search_query, download=True)
            
            if 'entries' in info:
                # Si fue una búsqueda, toma la primera entrada
                video_info = info['entries'][0]
            else:
                video_info = info
                
            downloaded_file = ydl.prepare_filename(video_info)
            # Corregir extensión si yt-dlp descargó en otro contenedor
            if not os.path.exists(downloaded_file):
                ext = video_info.get('ext', 'mp4')
                downloaded_file = os.path.splitext(downloaded_file)[0] + f".{ext}"
                
            if os.path.exists(downloaded_file):
                if status_callback:
                    status_callback(f"✅ Descarga completada: {os.path.basename(downloaded_file)}", "#00FF66")
                return os.path.abspath(downloaded_file)
            else:
                raise Exception("El archivo no se encontró después de la descarga.")
                
    except Exception as e:
        print(f">>> [GAMEPLAY SOURCING] Error en descarga yt-dlp: {e}")
        if status_callback:
            status_callback(f"🛑 Error de descarga: {str(e)[:40]}", "red")
        return None

def slice_video_segments(video_path, target_duration, download_dir, aspect_ratio="9:16", status_callback=None):
    """
    Corta el video largo en segmentos de duración aleatoria (5-12s) hasta completar la duración objetivo.
    Aplica re-encuadre vertical 9:16 con fondo borroso + centro escalado (sin pérdida de contexto/recortes excesivos).
    Codifica en resolución 720p comprimida para mayor velocidad y ligereza.
    Retorna una lista de diccionarios de clips compatibles con el motor Mix.
    """
    video_dur = get_video_duration(video_path)
    if video_dur <= 0:
        print(">>> [GAMEPLAY SOURCING] Error: El video de fondo tiene duración 0.")
        return []
        
    clips = []
    accumulated_time = 0.0
    clip_index = 0
    
    sub_kwargs = {}
    if os.name == 'nt':
        sub_kwargs['creationflags'] = 0x00000040 # IDLE priority
        
    # Definir resolución final optimizada a 720p (reduce peso a la mitad y renderiza al doble de velocidad)
    if aspect_ratio == "16:9":
        target_w, target_h = 1280, 720
    else:
        target_w, target_h = 720, 1280
        
    # Filtro de fondo borroso + primer plano escalado al centro para evitar recortar la acción del gameplay
    blur_padding_filter = (
        f"[0:v]split[bg][fg];"
        f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},boxblur=20:10[bg_blur];"
        f"[fg]scale={target_w}:-2[fg_scaled];"
        f"[bg_blur][fg_scaled]overlay=y=(H-h)/2"
    )
    
    while accumulated_time < (target_duration + 2.0): # Añadir 2 segundos de colchón
        # Duración aleatoria del clip entre 5 y 12 segundos
        clip_dur = random.uniform(5.0, 12.0)
        
        # Evitar exceder el video
        max_start = max(0.0, video_dur - clip_dur - 10.0) # Dejar 10s de margen al final
        if max_start <= 0:
            start_time = 0.0
            clip_dur = min(clip_dur, video_dur)
        else:
            start_time = random.uniform(0.0, max_start)
            
        output_name = f"gameplay_clip_{clip_index:03d}_{random.randint(1000, 9999)}.mp4"
        output_path = os.path.abspath(os.path.join(download_dir, output_name))
        
        if status_callback:
            status_callback(f"✂️ Generando clip {clip_index+1} ({clip_dur:.1f}s)...", "#FF9100")
            
        # Comprimir con CRF 28 (excelente compresión y ligereza) y preset ultrafast
        cmd = [
            "ffmpeg", "-y", "-threads", "2",
            "-ss", f"{start_time:.3f}",
            "-i", video_path,
            "-t", f"{clip_dur:.3f}",
            "-filter_complex", blur_padding_filter,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-an", # Eliminar el audio original para que no interfiera
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10240:
                clips.append({
                    "path": output_path,
                    "type": "video",
                    "has_audio": False,
                    "is_subliminal": False,
                    "ctime": os.path.getctime(output_path)
                })
                accumulated_time += clip_dur
                clip_index += 1
            else:
                print(f"[GAMEPLAY SOURCING] Error: FFmpeg generó un clip vacío o corrupto ({output_path}). El video fuente podría estar incompleto.")
                if os.path.exists(video_path):
                    print(f"[GAMEPLAY SOURCING] Eliminando video fuente corrupto de la caché: {video_path}")
                    try:
                        os.remove(video_path)
                    except Exception as ve:
                        print(f"Error al eliminar video fuente corrupto: {ve}")
                return []
        except Exception as e:
            print(f"Error cortando segmento {clip_index}: {e}")
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception:
                    pass
            return []
            
    return clips
