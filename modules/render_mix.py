import os
import subprocess
import shutil
import random
import time
import json
import traceback
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from modules.render_utils import (
    detect_hardware_encoder, 
    convert_to_word_by_word_srt, 
    safe_remove, 
    get_video_duration,
    extract_sfx_events,
    normalize_audio
)
from modules.telemetry import TelemetryLogger
def get_video_resolution(file_path):
    import subprocess
    import json
    import os
    
    if not os.path.exists(file_path):
        return 0, 0
        
    cmd = [
        "ffprobe", "-v", "quiet", 
        "-print_format", "json", 
        "-show_streams", 
        file_path
    ]
    sub_kwargs = {}
    if os.name == 'nt':
        sub_kwargs['creationflags'] = 0x00000040
        
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True, errors='replace', **sub_kwargs)
        data = json.loads(res.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                w = int(stream.get("width", 0))
                h = int(stream.get("height", 0))
                if w > 0 and h > 0:
                    return w, h
    except Exception as e:
        print(f"Error obtaining resolution for {file_path}: {e}")
        
    return 0, 0

def is_portrait_media(media_path, item_type):
    try:
        if item_type == "image":
            from PIL import Image
            with Image.open(media_path) as img:
                w, h = img.size
        else:
            w, h = get_video_resolution(media_path)
            
        if w > 0 and h > 0:
            aspect = w / h
            return 0.5 <= aspect <= 0.62
    except Exception as e:
        print(f"Error checking aspect ratio for {media_path}: {e}")
    return False

_WHISPER_MODEL = None

def apply_audio_speed_ramping(audio_path, json_data, temp_dir):
    """
    Aplica Speed Ramping al audio de narración basándose en las palabras
    clave de cada segmento de Whisper. Retorna el nuevo audio procesado
    y el JSON de transcripción con los timestamps ajustados.
    """
    import subprocess
    import json
    import os
    from modules.render_utils import get_video_duration
    
    suspense_keywords = [
        "terror", "miedo", "sangre", "muerte", "sombra", "oscuridad", 
        "grito", "espejo", "dolor", "fantasma", "rostro", "monstruo",
        "silencio", "detrás", "atrás", "peligro", "morir", "asesino"
    ]
    
    segments = json_data.get("segments", [])
    if not segments:
        return audio_path, json_data
        
    filter_parts = []
    concat_inputs = []
    
    new_segments = []
    current_new_time = 0.0
    
    for idx, seg in enumerate(segments):
        old_start = seg["start"]
        old_end = seg["end"]
        old_dur = old_end - old_start
        if old_dur <= 0:
            continue
            
        text = seg.get("text", "").lower()
        
        # Determinar factor de velocidad (tempo)
        # Ralentizar (0.90x) si contiene palabras de suspenso, acelerar (1.08x) si es normal
        has_suspense = any(kw in text for kw in suspense_keywords)
        tempo = 0.90 if has_suspense else 1.08
        
        part_label = f"a{idx}"
        filter_parts.append(
            f"[0:a]atrim=start={old_start:.3f}:end={old_end:.3f},asetpts=PTS-STARTPTS,atempo={tempo:.3f}[{part_label}]"
        )
        concat_inputs.append(f"[{part_label}]")
        
        new_dur = old_dur / tempo
        new_start = current_new_time
        new_end = new_start + new_dur
        
        new_seg = seg.copy()
        new_seg["start"] = new_start
        new_seg["end"] = new_end
        
        if "words" in seg:
            new_words = []
            for w in seg["words"]:
                w_old_start = w["start"]
                w_old_end = w["end"]
                w_new_start = new_start + (w_old_start - old_start) / tempo
                w_new_end = new_start + (w_old_end - old_start) / tempo
                new_w = w.copy()
                new_w["start"] = w_new_start
                new_w["end"] = w_new_end
                new_words.append(new_w)
            new_seg["words"] = new_words
            
        new_segments.append(new_seg)
        current_new_time = new_end
        
    if not concat_inputs:
        return audio_path, json_data
        
    concat_filter = "".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=0:a=1[a_out]"
    full_filter = ";".join(filter_parts) + ";" + concat_filter
    
    ramped_audio_path = os.path.abspath(os.path.join(temp_dir, "ramped_audio.wav"))
    cmd = [
        "ffmpeg", "-y", "-threads", "2",
        "-i", audio_path,
        "-filter_complex", full_filter,
        "-map", "[a_out]",
        "-ac", "2", "-ar", "44100",
        ramped_audio_path
    ]
    
    try:
        sub_kwargs = {}
        if os.name == 'nt':
            sub_kwargs['creationflags'] = 0x00000040
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
        new_json_data = {"segments": new_segments}
        return ramped_audio_path, new_json_data
    except Exception as e:
        print(f"Error aplicando audio speed ramping: {e}")
        return audio_path, json_data

def render_mix_mode(audio_path, mixed_media, cover_path, output_folder, title, description, vhs_enabled, music_path=None, status_callback=None, groq_key=None, aspect_ratio="9:16", lut_name=None, sub_style="Reddit History", reddit_card_title=None, pacing="Dinámico [2.0s]", vol_voice=100.0, vol_music=40.0, vol_sfx=100.0, **kwargs):
    enable_subtitles = kwargs.get("enable_subtitles", False)
    sub_kwargs = {}
    # Telemetry start
    telemetry = TelemetryLogger(log_path=os.path.join(os.getcwd(), "render_telemetry.log"))
    _telemetry_start = time.time()
    
    # Parse pacing duration
    pacing_dur = 2.0
    if pacing and "[" in pacing:
        try:
            pacing_val = pacing.split("[")[1].split("s]")[0]
            pacing_dur = float(pacing_val)
        except Exception as pe:
            print(f"Error parsing pacing: {pe}. Using default 2.0s")
            
    # Dynamic card duration based on pacing (shorter card = faster retention hook)
    if pacing_dur <= 1.3:
        card_duration = 3.0
    elif pacing_dur <= 2.1:
        card_duration = 4.0
    else:
        card_duration = 5.0

    if os.name == 'nt':
        # 0x00000040 es IDLE_PRIORITY_CLASS (Prioridad de fondo mínima)
        sub_kwargs['creationflags'] = 0x00000040

    safe_title = "".join([c for c in title if c.isalnum() or c==' ']).rstrip().replace(" ", "_") or "Video_Render_Mix"

    project_root = os.getcwd()
    cache_base = os.path.join(project_root, 'cache')
    cache_ass = os.path.join(cache_base, 'ass', safe_title)
    cache_json = os.path.join(cache_base, 'json', safe_title)
    cache_chunks = os.path.join(cache_base, 'chunks', safe_title)
    cache_audio = os.path.join(cache_base, 'audio', safe_title)
    cache_thumb = os.path.join(cache_base, 'thumbnails', safe_title)
    for d in [cache_base, cache_ass, cache_json, cache_chunks, cache_audio, cache_thumb]:
        os.makedirs(d, exist_ok=True)
    temp_dir = cache_json

    # --- CONFIGURACIÓN DE FILTRO LUT ---
    lut_filter = ""
    if lut_name and lut_name != "Ninguno":
        lut_map = {
            "Gore Rojo": "gore_red.cube",
            "Terror Frío": "cold_terror.cube",
            "Misterio Oscuro": "misterio_oscuro.cube",
            "Vintage VHS": "vintage_vhs.cube"
        }
        cube_file = lut_map.get(lut_name)
        if cube_file:
            lut_path = os.path.abspath(os.path.join(project_root, "assets", "video", "luts", cube_file))
            if os.path.exists(lut_path):
                escaped_lut = lut_path.replace('\\', '/').replace(':', '\\:')
                lut_filter = f",lut3d=file='{escaped_lut}'"
    
    # --- CONFIGURACIÓN DE RESOLUCIÓN DINÁMICA (FIJO A 720P) ---
    if aspect_ratio == "16:9":
        target_w, target_h = 1280, 720
        scale_w, scale_h = 1517, 854
    else:
        target_w, target_h = 720, 1280
        scale_w, scale_h = 854, 1517
    cache_file = os.path.join(cache_json, "srt_cache_mix.json")
    
        
    try:
        if status_callback: status_callback("🚀 INICIANDO MODO MIX (FULL FX)...", "#00E5FF")
        
        audio_full_path = os.path.abspath(audio_path)
        
        # --- PRE-RECORTAR SILENCIO INICIAL DE NARRACIÓN ---
        trimmed_audio_path = os.path.abspath(os.path.join(cache_audio, "trimmed_voice.wav"))
        trim_cmd = [
            "ffmpeg", "-y", "-threads", "2",
            "-i", audio_full_path,
            "-af", "silenceremove=start_periods=1:start_duration=0:start_threshold=-40dB",
            trimmed_audio_path
        ]
        try:
            if status_callback: status_callback("✂️ RECORTANDO SILENCIO INICIAL DE NARRACIÓN...", "#00E5FF")
            subprocess.run(trim_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
            if os.path.exists(trimmed_audio_path) and os.path.getsize(trimmed_audio_path) > 0:
                audio_full_path = trimmed_audio_path
        except Exception as e:
            print(f"Error pre-recortando silencio de narración: {e}")
            
        audio_dur = get_video_duration(audio_full_path)

        # --- SUBTITULOS CON CACHÉ Y SPEED RAMPING ---
        srt_path = os.path.join(cache_ass, "subs_mix.ass")
        final_json_path = os.path.join(cache_json, "data_mix.json")
        
        # Obtener metadatos del archivo de entrada original (antes de que FFMPEG modifique nada)
        input_audio_abspath = os.path.abspath(audio_path)
        input_audio_mtime = os.path.getmtime(input_audio_abspath) if os.path.exists(input_audio_abspath) else 0
        input_audio_size = os.path.getsize(input_audio_abspath) if os.path.exists(input_audio_abspath) else 0
        
        use_cache = False
        rebuild_srt_only = False
        cached_ramped_audio_path = None
        cached_ramped_duration = None
        
        if enable_subtitles:
            if os.path.exists(cache_file) and os.path.exists(final_json_path):
                try:
                    with open(cache_file, "r") as f: 
                        cache_data = json.load(f)
                    
                    # Verificar si el archivo original coincide en ruta, mtime y tamaño
                    if (cache_data.get("original_audio_path") == input_audio_abspath and 
                        cache_data.get("original_mtime") == input_audio_mtime and
                        cache_data.get("original_size") == input_audio_size):
                        
                        # La transcripción original en caché es válida
                        use_cache = True
                        cached_ramped_audio_path = cache_data.get("audio_path")
                        cached_ramped_duration = cache_data.get("duration")
                        
                        # Si el archivo del audio con ramping ya no existe físicamente, forzar regeneración
                        if not cached_ramped_audio_path or not os.path.exists(cached_ramped_audio_path):
                            use_cache = False
                        
                        # Si la transcripción es válida, verificar si el estilo de subtítulos o aspect ratio cambiaron
                        # o si el archivo .ass final no existe en disco
                        elif (cache_data.get("sub_style") != sub_style or 
                              cache_data.get("aspect_ratio") != aspect_ratio or 
                              not os.path.exists(srt_path) or os.path.getsize(srt_path) == 0):
                            rebuild_srt_only = True
                except Exception as e: 
                    print(f"Error leyendo cache de subtítulos: {e}")

            if use_cache:
                if status_callback: status_callback("♻️ USANDO SUBTÍTULOS EN CACHÉ", "#00E676")
                try:
                    with open(final_json_path, "r", encoding="utf-8") as f:
                        result = json.load(f)
                    
                    # Reutilizar el audio con ramping ya generado
                    audio_full_path = cached_ramped_audio_path
                    audio_dur = cached_ramped_duration
                    
                    # Si se necesita rehacer solo el archivo de subtítulos por cambio de estilo o resolución
                    if rebuild_srt_only:
                        if status_callback: status_callback("🔤 REGENERANDO SUBTÍTULOS CON NUEVO ESTILO...", "#00E676")
                        convert_to_word_by_word_srt(final_json_path, srt_path, status_callback, aspect_ratio=aspect_ratio, sub_style=sub_style)
                        
                        # Actualizar cache_file con los nuevos parámetros de estilo y aspect ratio
                        with open(cache_file, "w") as f:
                            json.dump({
                                "original_audio_path": input_audio_abspath,
                                "original_duration": cache_data.get("original_duration"),
                                "original_mtime": input_audio_mtime,
                                "original_size": input_audio_size,
                                "audio_path": audio_full_path,
                                "duration": audio_dur,
                                "sub_style": sub_style,
                                "aspect_ratio": aspect_ratio
                            }, f)
                except Exception as e:
                    print(f"Error al cargar recursos de caché: {e}")
                    use_cache = False

            if not use_cache:
                if status_callback: status_callback("🧠 GENERANDO SUBTÍTULOS (GROQ)...", "#FFD700")
                try:
                    result = None
                    # Intentar transcribir con Groq si hay API Key disponible
                    if groq_key:
                        try:
                            from modules.render_utils import transcribe_with_groq
                            result = transcribe_with_groq(audio_full_path, groq_key, language="es")
                        except Exception as g_err:
                            print(f"Error transcribiendo con Groq (se intentará Whisper local): {g_err}")
                    
                    # Si falló Groq o no había API Key, usar Whisper local
                    if not result:
                        if status_callback: status_callback("🧠 Groq falló o no configurado. Usando Whisper local...", "orange")
                        global _WHISPER_MODEL
                        import whisper
                        if _WHISPER_MODEL is None:
                            _WHISPER_MODEL = whisper.load_model("tiny")
                        result = _WHISPER_MODEL.transcribe(audio_full_path, word_timestamps=True, language="es")
                    
                    if not result:
                        raise Exception("Fallo en transcripción Groq/Whisper")
                except Exception as w_err:
                    print(f"Transcription Error: {w_err}")
                    if status_callback: status_callback(f"⚠️ Error Subtítulos: {str(w_err)[:20]}", "orange")
                    result = None

                if result:
                    if status_callback: status_callback("🎚️ APLICANDO SPEED RAMPING AL AUDIO...", "#FFD700")
                    original_audio_path = audio_full_path
                    original_duration = audio_dur
                    
                    ramped_audio_path, new_json = apply_audio_speed_ramping(audio_full_path, result, cache_audio)
                    # Normalize audio loudness for consistent volume
                    normalized_audio_path = normalize_audio(ramped_audio_path, cache_audio)
                    audio_full_path = normalized_audio_path
                    audio_dur = get_video_duration(audio_full_path)
                    result = new_json
                    
                    with open(final_json_path, 'w', encoding='utf-8') as f: 
                        json.dump(result, f)
                    convert_to_word_by_word_srt(final_json_path, srt_path, status_callback, aspect_ratio=aspect_ratio, sub_style=sub_style)
                    
                    with open(cache_file, "w") as f:
                        json.dump({
                            "original_audio_path": input_audio_abspath,
                            "original_duration": original_duration,
                            "original_mtime": input_audio_mtime,
                            "original_size": input_audio_size,
                            "audio_path": audio_full_path,
                            "duration": audio_dur,
                            "sub_style": sub_style,
                            "aspect_ratio": aspect_ratio
                        }, f)
                else:
                    srt_path = None
        else:
            # Omitimos transcripción y speed ramping. Solo normalizamos el audio.
            if status_callback: status_callback("🎚️ NORMALIZANDO AUDIO DE NARRACIÓN (SIN SUBTÍTULOS)...", "#FFD700")
            try:
                normalized_audio_path = normalize_audio(audio_full_path, cache_audio)
                audio_full_path = normalized_audio_path
                audio_dur = get_video_duration(audio_full_path)
            except Exception as norm_err:
                print(f"Error normalizando audio: {norm_err}")
            srt_path = None
        if status_callback: status_callback("⚙️ VERIFICANDO ACELERACIÓN DE HARDWARE...", "#00E5FF")
        enc_params = detect_hardware_encoder(output_folder)
        # Apply CRF based on requested render quality
        crf_value = "20"
        render_quality = kwargs.get('render_quality')
        if render_quality:
            quality = str(render_quality).lower()
            if quality == "high":
                crf_value = "18"
            elif quality == "low":
                crf_value = "23"
        # Append CRF flag to encoder params if supported
        if "-c:v" in enc_params:
            enc_params += ["-crf", crf_value]
        total_visual_dur = audio_dur + 0.3

        # --- LA LÓGICA DE B-ROLL HA SIDO MOVIDA AL TIMELINE (PASO 3) ---
        precalculated_durations = None
        sub_dur = 0.25 # Duración ultra-rápida para flashes subliminales (7-8 frames)
        downloaded_brolls = []
        downloaded_brolls_to_clean = []
        horror_intervals = []
        
        # --- CÁLCULO DE TIEMPOS DINÁMICOS Y COMPENSACIÓN DE TRANSICIONES ---
        sub_items = [m for m in mixed_media if isinstance(m, dict) and m.get("is_subliminal")]
        
        total_t_dur = 0
        for i in range(1, len(mixed_media)):
            is_sub_p = isinstance(mixed_media[i-1], dict) and mixed_media[i-1].get("is_subliminal")
            is_sub_c = isinstance(mixed_media[i], dict) and mixed_media[i].get("is_subliminal")
            total_t_dur += 0.05 if (is_sub_p or is_sub_c) else 0.5
            
        total_sub_time = len(sub_items) * sub_dur
        remaining_time = max(0.1, total_visual_dur - total_sub_time + total_t_dur)
        
        if precalculated_durations is not None:
            clip_durations = precalculated_durations
        else:
            # Seed randomly based on title to keep durations deterministic across renders for cache hits
            fallback_seed = int(hashlib.sha256(title.encode()).hexdigest(), 16) % (10**8)
            random.seed(fallback_seed)
            
            weights = []
            for m in mixed_media:
                is_sub = isinstance(m, dict) and m.get("is_subliminal")
                if is_sub:
                    weights.append(0.0)
                else:
                    if random.random() < 0.18:
                        weights.append(random.uniform(0.12, 0.20))
                    else:
                        weights.append(random.uniform(0.70, 1.30))
                        
            # Restore system randomness state
            random.seed(None)
                        
            normal_weights_sum = sum(w for w in weights if w > 0.0)
            if normal_weights_sum <= 0:
                normal_weights_sum = 1.0
                
            clip_durations = []
            for w in weights:
                if w == 0.0:
                    clip_durations.append(sub_dur)
                else:
                    clip_durations.append((w / normal_weights_sum) * remaining_time)

        # PROCESAMIENTO HÍBRIDO CON MISMAS PROBABILIDADES
        hw_failed = [False]
        processed_mix = 0
        if status_callback: status_callback("🎬 PROCESANDO Y RENDERIZANDO CLIPS EN PARALELO...", "#FF9100")
        def process_chunk(args):
            _start_chunk = time.time()
            nonlocal processed_mix, hw_failed
            try:
                i, item, enc, dur, vhs_p, title, sub_style, horror_intervals, clip_durations = args
                if status_callback:
                    status_callback(f"🎬 RENDERIZANDO CLIP {i+1} de {len(mixed_media)}...", "#FF9100")
                
                # --- CALCULAR INTERVALOS LOCALES DE SACUDIDAS Y GLITCHES ---
                chunk_start = sum(clip_durations[:i])
                chunk_end = chunk_start + dur
                local_glitches = []
                for s, e in horror_intervals:
                    overlap_start = max(chunk_start, s)
                    overlap_end = min(chunk_end, e)
                    if overlap_start < overlap_end:
                        local_glitches.append((overlap_start - chunk_start, overlap_end - chunk_start))
                
                if local_glitches:
                    shake_expr = "+".join([f"gte(t\\,{s:.3f})*lte(t\\,{e:.3f})" for s, e in local_glitches])
                    shake_expr_zoom = "+".join([f"gte(on/30\\,{s:.3f})*lte(on/30\\,{e:.3f})" for s, e in local_glitches])
                    glitch_fx = f",negate=enable='({shake_expr})*lt(mod(t\\,0.1)\\,0.05)',noise=alls=45:allf=t:enable='{shake_expr}'"
                else:
                    shake_expr = "0"
                    shake_expr_zoom = "0"
                    glitch_fx = ""
                
                # SOPORTE HÍBRIDO: Diccionario o String
                is_subliminal = False
                if isinstance(item, dict):
                    media_path = os.path.abspath(item.get("path", ""))
                    has_audio = item.get("has_audio", True)
                    item_type = item.get("type", "image")
                    is_subliminal = item.get("is_subliminal", False)
                else:
                    media_path = os.path.abspath(str(item))
                    has_audio = True
                    ext = os.path.splitext(media_path)[1].lower()
                    item_type = "video" if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif'] else "image"
                
                if not os.path.exists(media_path): return None

                # --- DESINFECCIÓN AL VUELO DE ANIMACIONES (GIF / WEBP) ---
                if media_path.lower().endswith(('.gif', '.webp')):
                    try:
                        img = Image.open(media_path)
                        # Comprobar si es una animación multi-frame
                        media_hash = hashlib.md5(media_path.encode()).hexdigest()[:8]
                        
                        if getattr(img, "is_animated", False) and img.n_frames > 1:
                            # Creamos un archivo MP4 temporal para este render en cache
                            temp_mp4_path = os.path.abspath(os.path.join(cache_chunks, f"converted_media_{i}_{media_hash}.mp4"))
                            
                            # Si no existe o tiene 0 bytes, convertimos
                            if not os.path.exists(temp_mp4_path) or os.path.getsize(temp_mp4_path) == 0:
                                temp_frames_dir = os.path.abspath(os.path.join(cache_chunks, f"temp_frames_{i}_{media_hash}"))
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
                                
                                cmd_conv = [
                                    "ffmpeg", "-y", "-threads", "2",
                                    "-f", "image2",
                                    "-framerate", f"{fps:.2f}",
                                    "-i", os.path.join(temp_frames_dir, "frame_%03d.png"),
                                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                                    "-an", temp_mp4_path
                                ]
                                sub_kwargs_conv = {}
                                if os.name == 'nt':
                                    sub_kwargs_conv['creationflags'] = 0x00000040
                                    
                                subprocess.run(cmd_conv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs_conv)
                                shutil.rmtree(temp_frames_dir, ignore_errors=True)
                                
                            if os.path.exists(temp_mp4_path) and os.path.getsize(temp_mp4_path) > 0:
                                media_path = temp_mp4_path
                                item_type = "video"
                        else:
                            # Es una imagen estática (GIF/WebP de 1 frame). Convertimos a un JPG limpio temporal
                            temp_jpg_path = os.path.abspath(os.path.join(cache_chunks, f"converted_media_{i}_{media_hash}.jpg"))
                            if not os.path.exists(temp_jpg_path):
                                img.convert("RGB").save(temp_jpg_path, "JPEG")
                            if os.path.exists(temp_jpg_path):
                                media_path = temp_jpg_path
                                item_type = "image"
                    except Exception as conv_err:
                        print(f">>> [RENDER CONVERSION ERROR] No se pudo desinfectar animación {media_path}: {conv_err}")

                # Compute deterministic cache hash for the chunk
                has_card = (i == 0 and sub_style == "Reddit History")
                hash_input = f"{str(media_path).lower()}_{round(dur, 3)}_{str(vhs_p).lower()}_{has_card}_{target_w}_{target_h}_{horror_intervals}"
                chunk_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
                cached_chunk_path = os.path.abspath(os.path.join(cache_chunks, f"chunk_mix_{i:03d}_{chunk_hash}.mp4"))
                
                # --- RENDERIZADO DE CHUNK (con manejo de errores) ---
                try:
                    if os.path.exists(cached_chunk_path) and os.path.getsize(cached_chunk_path) > 0:
                        # Use cached chunk
                        _end_cache = time.time()
                        telemetry.record({
                            "function": "process_chunk", 
                            "chunk_index": i, 
                            "status": "cache_hit", 
                            "duration_seconds": _end_cache - _start_chunk,
                            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
                        })
                        return cached_chunk_path
                    # else render to cache path
                    chunk_name = cached_chunk_path
                    render_dur = dur
                    frames = int(render_dur * 30)
                except Exception as rc_err:
                    print(f"[ERROR] Renderizado del chunk {i} falló: {rc_err}")
                    if status_callback:
                        status_callback(f"⚠️ ERROR RENDER CHUNK {i}: {rc_err}", "orange")
                    raise
                
                # --- EFECTOS SUBLIMINALES (BLUR & FLICKER) ---
                if is_subliminal:
                    sub_fx = f"boxblur=2:1,eq=brightness='0.2*sin(30*PI*t)'"
                    xa, xf, ya, yf = 0.0, 0.0, 0.0, 0.0
                    ze = "1.0" 
                else:
                    sub_fx = "null"
                    shake_patterns = [(0.18, 7.0, 0.18, 5.3), (0.24, 4.5, 0.27, 7.1), (0.09, 12.0, 0.12, 9.0), (0.21, 3.0, 0.17, 11.0), (0.27, 8.0, 0.24, 6.5)]
                    xa, xf, ya, yf = random.choice(shake_patterns)
                    ze = random.choice(["max(zoom,1.1)+0.0035", "max(zoom,1.1)+0.006"])
                
                # Efectos de estilo (Solo para normales y videos)
                if not is_subliminal:
                    focus = random.choice(["unsharp=5:5:-0.5:5:5:0,unsharp=5:5:0.7:5:5:0", "unsharp=7:7:-0.35:3:3:0", "null"])
                    fb, fm, ff = random.uniform(0.5, 1.5), random.uniform(3, 7), random.uniform(15, 25)
                    flick = f"eq=brightness='0.07*sin({fb:.2f}*PI*t)+0.04*sin({fm:.2f}*PI*t)+0.03*sin({ff:.2f}*PI*t)'"
                    vign = f"vignette='PI/4+0.12*sin({random.uniform(0.5,2):.2f}*PI*t)':eval=frame"
                    
                    cd = 0.07; c1, c2 = round(random.uniform(0.1, 1.2), 2), round(random.uniform(1.5, dur-0.2), 2)
                    dice = random.random()
                    if dice < 0.4: mcut = f"drawbox=x=0:y=0:w=iw:h=ih:color=black@1:t=fill:enable='between(t,{c1},{c1+cd})+between(t,{c2},{c2+cd})'"
                    elif dice < 0.8: mcut = f"noise=alls=100:allf=t:enable='between(t,{c1},{c1+cd})+between(t,{c2},{c2+cd})'"
                    else: mcut = "null"
                    
                    fish = "lenscorrection=k1=0.12:k2=0.12" if random.random() < 0.5 else "null"
                    stut = "select='lt(random(1),0.93)',fps=30" if random.random() < 0.2 else "null"
                    sat = "eq=saturation=1.45:contrast=1.05"
                    
                    # Cadena de FX completa
                    fx_chain = f"{fish},{focus},{flick},{vign},{stut},{mcut},{sat}"
                    
                    # Inyección de gancho visual para el primer clip (i == 0)
                    if i == 0:
                        strobe_fx = "negate=enable='between(t\\,0\\,0.15)'"
                        
                        if sub_style == "Reddit History":
                            # En modo Reddit, no queremos el drawtext intermitente gigante
                            fx_chain = f"{strobe_fx},{fx_chain}"
                        elif sub_style == "Roblox Gaming":
                            # HOOK ROBLOX GAMING: Texto gaming limpio, estático, sin parpadeo
                            font_path_roblox = "C\\:/Windows/Fonts/ariblk.ttf"
                            if not os.path.exists("C:\\Windows\\Fonts\\ariblk.ttf"):
                                font_path_roblox = "C\\:/Windows/Fonts/arialbd.ttf"
                                if not os.path.exists("C:\\Windows\\Fonts\\arialbd.ttf"):
                                    font_path_roblox = "arial"
                            
                            if font_path_roblox == "arial":
                                font_param_roblox = "font='Arial'"
                            else:
                                font_param_roblox = f"fontfile='{font_path_roblox}'"
                            
                            clean_title_roblox = title.replace("'", "").replace('"', '').replace(":", " ").replace("\\", " ").strip().upper()
                            words_roblox = clean_title_roblox.split()
                            # Máximo 5 palabras para el hook (2 líneas de ~3 palabras)
                            hook_words = words_roblox[:5]
                            mid = (len(hook_words) + 1) // 2
                            line1_roblox = " ".join(hook_words[:mid])
                            line2_roblox = " ".join(hook_words[mid:])
                            
                            # Fondo oscuro semitransparente para el hook (drawbox)
                            hook_bg = "drawbox=x=0:y=(h-320)/2:w=iw:h=320:color=black@0.55:t=fill:enable='between(t\\,0\\,2.5)'"
                            # Línea 1: texto principal blanco con borde negro grueso
                            dt1_roblox = (
                                f"drawtext={font_param_roblox}:text='{line1_roblox}':"
                                f"fontcolor=white:fontsize=95:borderw=8:bordercolor=black:"
                                f"x=(w-text_w)/2:y=(h-text_h)/2-55:"
                                f"enable='between(t\\,0\\,2.5)'"
                            )
                            # Línea 2: texto secundario en naranja gaming
                            if line2_roblox:
                                dt2_roblox = (
                                    f"drawtext={font_param_roblox}:text='{line2_roblox}':"
                                    f"fontcolor=0xFFA500:fontsize=90:borderw=8:bordercolor=black:"
                                    f"x=(w-text_w)/2:y=(h-text_h)/2+55:"
                                    f"enable='between(t\\,0\\,2.5)'"
                                )
                                fx_chain = f"{fx_chain},{hook_bg},{dt1_roblox},{dt2_roblox}"
                            else:
                                fx_chain = f"{fx_chain},{hook_bg},{dt1_roblox}"
                        else:
                            # Buscar fuente disponible en Windows
                            font_path = "C\\:/Windows/Fonts/ariblk.ttf"
                            if not os.path.exists("C:\\Windows\\Fonts\\ariblk.ttf"):
                                font_path = "C\\:/Windows/Fonts/arialbd.ttf"
                                if not os.path.exists("C:\\Windows\\Fonts\\arialbd.ttf"):
                                    font_path = "arial"
                                    
                            if font_path == "arial":
                                font_param = "font='Arial'"
                            else:
                                font_param = f"fontfile='{font_path}'"
                                
                            # Limpiar y preparar texto del título
                            clean_title = title.replace("'", "").replace('"', '').replace(":", " ").replace("\\", " ").strip().upper()
                            words = clean_title.split()
                            
                            # Agrupar en líneas de hasta 3 palabras
                            raw_lines = []
                            curr = []
                            for w in words:
                                curr.append(w)
                                if len(curr) >= 3:
                                    raw_lines.append(" ".join(curr))
                                    curr = []
                            if curr:
                                raw_lines.append(" ".join(curr))
                                
                            hook_lines = raw_lines[:3]
                            drawtext_filters = []
                            num_lines = len(hook_lines)
                            
                            for idx, line in enumerate(hook_lines):
                                if num_lines == 1:
                                    y_pos = "(h-text_h)/2"
                                elif num_lines == 2:
                                    y_pos = f"(h-text_h)/2-{70 - idx*140}"
                                else:
                                    y_pos = f"(h-text_h)/2-{140 - idx*140}"
                                    
                                enable_expr = "between(t\\,0\\,2.2)*lt(mod(t\\,0.3)\\,0.2)"
                                dt = (
                                    f"drawtext={font_param}:text='{line}':fontcolor=red:"
                                    f"fontsize=80:borderw=10:bordercolor=black:"
                                    f"x=(w-text_w)/2:y={y_pos}:enable='{enable_expr}'"
                                )
                                drawtext_filters.append(dt)
                                
                            drawtext_chain = ",".join(drawtext_filters)
                            if drawtext_chain:
                                fx_chain = f"{strobe_fx},{fx_chain},{drawtext_chain}"
                            else:
                                fx_chain = f"{strobe_fx},{fx_chain}"
                else:
                    # Subliminales limpias
                    fx_chain = "null"

                is_portrait = is_portrait_media(media_path, item_type)
                if i == 0 and not is_subliminal:
                    # GANCHO AGRESIVO: Sismo cinemático (temblor sutil) + Zoom-In progresivo en los primeros segundos
                    if item_type == "video":
                        sx_base = f"200*0.02*(0.8*sin(6*PI*t)+0.2*sin(12*PI*t))*exp(-1.2*t)"
                        sy_base = f"350*0.02*(0.8*sin(5*PI*t+1.57)+0.2*sin(10*PI*t))*exp(-1.2*t)"
                        if local_glitches:
                            sx = f"{sx_base} + 18*sin(60*t)*({shake_expr})"
                            sy = f"{sy_base} + 18*cos(50*t)*({shake_expr})"
                        else:
                            sx = sx_base
                            sy = sy_base
                        scale_w_eff = int(target_w * 1.35)
                        scale_h_eff = int(target_h * 1.35)
                        if is_portrait:
                            vf_base = f"scale={scale_w_eff}:{scale_h_eff}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h}:'(iw-ow)/2+{sx}':'(ih-oh)/2+{sy}'"
                        else:
                            # Blur padding layout
                            vf_base = (
                                f"split[bg][fg];"
                                f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},boxblur=15:1[bg_blur];"
                                f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=bilinear[fg_scaled];"
                                f"[bg_blur][fg_scaled]overlay=x='(W-w)/2+{sx}':y='(H-h)/2+{sy}',setsar=1/1,setdar=9/16"
                            )
                        if media_path.lower().endswith(".gif"):
                            input_opts_list = ["-hwaccel", "auto", "-ignore_loop", "0"]
                        else:
                            input_opts_list = ["-hwaccel", "auto", "-stream_loop", "-1"]
                    else:
                        ze = "1.1+0.004*on"
                        xe_base = f"(iw-iw/zoom)*0.4*(0.8*sin(6*PI*on/30)+0.2*sin(12*PI*on/30))*exp(-1.2*on/30)"
                        ye_base = f"(ih-ih/zoom)*0.4*(0.8*sin(5*PI*on/30+1.57)+0.2*sin(10*PI*on/30))*exp(-1.2*on/30)"
                        if local_glitches:
                            xe = f"{xe_base} + 18*sin(60*on/30)*({shake_expr_zoom})"
                            ye = f"{ye_base} + 18*cos(50*on/30)*({shake_expr_zoom})"
                        else:
                            xe = xe_base
                            ye = ye_base
                        if is_portrait:
                            vf_base = f"loop=loop=-1:size=1:start=0,scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},setsar=1/1,zoompan=z='{ze}':d={frames+2}:x='(iw-iw/zoom)/2+{xe}':y='(ih-ih/zoom)/2+{ye}':s={target_w}x{target_h}:fps=30,setdar=9/16"
                        else:
                            vf_base = (
                                f"loop=loop=-1:size=1:start=0,split[bg][fg];"
                                f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},boxblur=15:1[bg_blur];"
                                f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=bilinear[fg_scaled];"
                                f"[bg_blur][fg_scaled]overlay=x='(W-w)/2':y='(H-h)/2',setsar=1/1,"
                                f"zoompan=z='{ze}':d={frames+2}:x='(iw-iw/zoom)/2+{xe}':y='(ih-ih/zoom)/2+{ye}':s={target_w}x{target_h}:fps=30,setdar=9/16"
                            )
                        input_opts_list = ["-loop", "1"]
                else:
                    # Comportamiento normal (restante de clips)
                    # Si el clip es largo (>pacing_dur), aplicar el "Re-encuadre de Emergencia Automático" (Punch-In / Jump Cut) en el 60% de su duración
                    if dur > pacing_dur:
                        jump_frame = int(dur * 0.6 * 30)
                        # Zoom-in repentino del 1.1x al 1.35x para imagen
                        ze_normal = f"if(gte(on,{jump_frame}), max(zoom,1.35)+0.0035, max(zoom,1.1)+0.0035)"
                    else:
                        ze_normal = "max(zoom,1.1)+0.0035"

                    if item_type == "video":
                        sx_base = f"200*{xa:.2f}*0.05*(0.8*sin({xf:.1f}*PI*t)+0.2*sin({xf*3.14:.1f}*PI*t))"
                        sy_base = f"350*{ya:.2f}*0.05*(0.8*sin({yf:.1f}*PI*t+1.57)+0.2*sin({yf*2.71:.1f}*PI*t))"
                        if local_glitches:
                            sx = f"{sx_base} + 18*sin(60*t)*({shake_expr})"
                            sy = f"{sy_base} + 18*cos(50*t)*({shake_expr})"
                        else:
                            sx = sx_base
                            sy = sy_base
                        if is_portrait:
                            if dur > pacing_dur:
                                jump_t = dur * 0.6
                                vf_base = (
                                    f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h}:'(iw-ow)/2+{sx}':'(ih-oh)/2+{sy}',"
                                    f"zoompan=z='if(gte(time,{jump_t:.2f}),1.25,1.0)':d=1:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s={target_w}x{target_h}:fps=30"
                                )
                            else:
                                vf_base = f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h}:'(iw-ow)/2+{sx}':'(ih-oh)/2+{sy}'"
                        else:
                            # Blur padding layout for video
                            if dur > pacing_dur:
                                jump_t = dur * 0.6
                                vf_base = (
                                    f"split[bg][fg];"
                                    f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},boxblur=15:1[bg_blur];"
                                    f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=bilinear[fg_scaled];"
                                    f"[bg_blur][fg_scaled]overlay=x='(W-w)/2+{sx}':y='(H-h)/2+{sy}',setsar=1/1,"
                                    f"zoompan=z='if(gte(time,{jump_t:.2f}),1.25,1.0)':d=1:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s={target_w}x{target_h}:fps=30,setdar=9/16"
                                )
                            else:
                                vf_base = (
                                    f"split[bg][fg];"
                                    f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},boxblur=15:1[bg_blur];"
                                    f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=bilinear[fg_scaled];"
                                    f"[bg_blur][fg_scaled]overlay=x='(W-w)/2+{sx}':y='(H-h)/2+{sy}',setsar=1/1,setdar=9/16"
                                )
                        is_qsv = any("h264_qsv" in str(param) for param in enc)
                        hwaccel_val = "qsv" if is_qsv else "auto"
                        if media_path.lower().endswith(".gif"):
                            input_opts_list = ["-hwaccel", hwaccel_val, "-ignore_loop", "0"]
                            input_opts_list_cpu = ["-hwaccel", "auto", "-ignore_loop", "0"]
                        else:
                            input_opts_list = ["-hwaccel", hwaccel_val, "-stream_loop", "-1"]
                            input_opts_list_cpu = ["-hwaccel", "auto", "-stream_loop", "-1"]
                    else:
                        xe_base = f"(iw-iw/zoom)*{xa:.2f}*0.03*(0.8*sin({xf:.1f}*on/30)+0.2*sin({xf*3.14:.1f}*on/30))"
                        ye_base = f"(ih-ih/zoom)*{ya:.2f}*0.03*(0.8*sin({yf:.1f}*on/30+1.57)+0.2*sin({yf*2.71:.1f}*on/30))"
                        if local_glitches:
                            xe = f"{xe_base} + 18*sin(60*on/30)*({shake_expr_zoom})"
                            ye = f"{ye_base} + 18*cos(50*on/30)*({shake_expr_zoom})"
                        else:
                            xe = xe_base
                            ye = ye_base
                        if is_portrait:
                            vf_base = f"loop=loop=-1:size=1:start=0,scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},setsar=1/1,zoompan=z='{ze_normal}':d={frames+2}:x='(iw-iw/zoom)/2+{xe}':y='(ih-ih/zoom)/2+{ye}':s={target_w}x{target_h}:fps=30,setdar=9/16"
                        else:
                            vf_base = (
                                f"loop=loop=-1:size=1:start=0,split[bg][fg];"
                                f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},boxblur=15:1[bg_blur];"
                                f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=bilinear[fg_scaled];"
                                f"[bg_blur][fg_scaled]overlay=x='(W-w)/2':y='(H-h)/2',setsar=1/1,"
                                f"zoompan=z='{ze_normal}':d={frames+2}:x='(iw-iw/zoom)/2+{xe}':y='(ih-ih/zoom)/2+{ye}':s={target_w}x{target_h}:fps=30,setdar=9/16"
                            )
                        input_opts_list = ["-loop", "1"]
                        input_opts_list_cpu = ["-loop", "1"]
                
                # UNIFICACIÓN DE EFECTOS
                card_png_path = None
                if i == 0 and sub_style == "Reddit History":
                    card_png_path = os.path.abspath(os.path.join(cache_chunks, "reddit_card.png"))
                    try:
                        from modules.render_utils import generate_reddit_card
                        card_text = reddit_card_title if reddit_card_title else title
                        if "#" in card_text:
                            card_text = card_text.split("#")[0].strip()
                        generate_reddit_card(card_text, card_png_path, aspect_ratio)
                    except Exception as e:
                        print(f"Error generating Reddit card: {e}")
                        card_png_path = None

                if card_png_path and os.path.exists(card_png_path):
                    # Desenfoque periférico (boxblur) de fondo en los primeros segundos
                    vf_final = f"{vf_base},boxblur=15:enable='between(t\\,0\\,{card_duration})',format=yuv420p,{fx_chain},{sub_fx}{lut_filter}{glitch_fx}"
                    # Mezclar con el VHS y superponer el card con animación de entrada slide-up
                    cvf = f"[0:v]{vf_final},format=gbrp[b];[1:v]scale={target_w}:{target_h}:flags=bilinear,hue=s=0,format=gbrp[v];[b][v]blend=all_mode=screen:all_opacity=0.08[mixed];[mixed][2:v]overlay=(W-w)/2:y='((H-h)/2+(H-(H-h)/2)*exp(-8*t))*lt(t,0.6)+(H-h)/2*gte(t,0.6)':enable='between(t\\,0\\,{card_duration})',format=yuv420p"
                    
                    active_enc = ["-c:v", "libx264", "-preset", "ultrafast", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high"] if hw_failed[0] else enc
                    loop_opts = ["-stream_loop", "-1"] if item_type == "video" else []
                    cmd = ["ffmpeg", "-y", "-threads", "2", "-filter_complex_threads", "2"] + input_opts_list + loop_opts + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-i", card_png_path, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30"] + active_enc + ["-an", chunk_name]
                    try:
                        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                    except Exception as e:
                        if not hw_failed[0]:
                            print(f"HW encoder failed for chunk {i}, falling back to CPU. Error: {e}")
                            hw_failed[0] = True
                        cmd_fallback = ["ffmpeg", "-y", "-threads", "2", "-filter_complex_threads", "2"] + input_opts_list_cpu + loop_opts + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-i", card_png_path, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high", "-an", chunk_name]
                        subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                else:
                    vf_final = f"{vf_base},format=yuv420p,{fx_chain},{sub_fx}{lut_filter}{glitch_fx}"
                    cvf = f"[0:v]{vf_final},format=gbrp[b];[1:v]scale={target_w}:{target_h}:flags=bilinear,hue=s=0,format=gbrp[v];[b][v]blend=all_mode=screen:all_opacity=0.08,format=yuv420p"
                    
                    active_enc = ["-c:v", "libx264", "-preset", "ultrafast", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high"] if hw_failed[0] else enc
                    loop_opts = ["-stream_loop", "-1"] if item_type == "video" else []
                    cmd = ["ffmpeg", "-y", "-threads", "2", "-filter_complex_threads", "2"] + input_opts_list + loop_opts + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30"] + active_enc + ["-an", chunk_name]
                    try:
                        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                    except Exception as e:
                        if not hw_failed[0]:
                            print(f"HW encoder failed for chunk {i}, falling back to CPU. Error: {e}")
                            hw_failed[0] = True
                        cmd_fallback = ["ffmpeg", "-y", "-threads", "2", "-filter_complex_threads", "2"] + input_opts_list_cpu + loop_opts + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high", "-an", chunk_name]
                        subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                

                processed_mix += 1
                if status_callback: status_callback(f"🌪️ MEZCLANDO MEDIA: {processed_mix}/{len(mixed_media)}", "#00E5FF")
                _end_chunk = time.time()
                telemetry.record({
                    "function": "process_chunk", 
                    "chunk_index": i, 
                    "status": "rendered", 
                    "duration_seconds": _end_chunk - _start_chunk,
                    "timestamp": __import__('datetime').datetime.utcnow().isoformat()
                })
                return chunk_name
            except Exception as e:
                print(f"Error procesando chunk {i}: {e}")
                return None

        vhs_bg = os.path.abspath(os.path.join("assets", "video", "fx", "vhs_overlay.mp4"))
        
        # --- PRECALCULAR TRANSICIONES, OFFSETS Y DURACIONES FÍSICAS DE CHUNKS ---
        possible_transitions = ["hblur", "pixelize", "distance", "radial", "smoothleft", "zoomin", "circlecrop", "fadeblack"]
        transition_offsets = []
        t_durs = []
        chosen_transition_names = []
        current_offset = 0.0
        
        num_clips = len(mixed_media)
        for i in range(1, num_clips):
            is_sub_prev = isinstance(mixed_media[i-1], dict) and mixed_media[i-1].get("is_subliminal")
            is_sub_curr = isinstance(mixed_media[i], dict) and mixed_media[i].get("is_subliminal")
            
            if is_sub_prev or is_sub_curr:
                t_name = "fade"
                t_dur = 0.05
            else:
                t_name = random.choice(possible_transitions)
                t_dur = 0.5
                
            min_clip_dur = min(clip_durations[i-1], clip_durations[i])
            if t_dur >= min_clip_dur:
                t_dur = max(0.05, min_clip_dur - 0.1)
                
            current_offset += clip_durations[i-1] - t_dur
            if current_offset < 0:
                current_offset = 0.0
                
            transition_offsets.append(current_offset)
            t_durs.append(t_dur)
            chosen_transition_names.append(t_name)

        # Calcular duración física necesaria de cada chunk para compensar pérdidas por xfade
        chunk_durations = []
        for i in range(num_clips):
            if i < num_clips - 1:
                t_dur_next = t_durs[i]
                D_i = clip_durations[i] + t_dur_next + 1.5
            else:
                offset_last = transition_offsets[-1] if transition_offsets else 0.0
                D_i = max(clip_durations[i] + 1.5, total_visual_dur - offset_last + 2.5)
            chunk_durations.append(D_i)

        tks = []
        for i, m in enumerate(mixed_media):
            d = chunk_durations[i]
            tks.append((i, m, enc_params, d, vhs_bg, title, sub_style, horror_intervals, clip_durations))

        # Evitar saturar el CPU y disco con múltiples renders simultáneos.
        max_workers = 1

        with ThreadPoolExecutor(max_workers=max_workers) as ex: 
            chunk_files = [c for c in list(ex.map(process_chunk, tks)) if c]
        
        if not chunk_files: raise Exception("No se procesaron clips en modo MIX.")

        # COMPOSICIÓN, MEZCLA FINAL DE AUDIO Y SUBTÍTULOS ASS (ETAPA DE DOS PASOS PARA PREVENIR OUT-OF-MEMORY)
        if status_callback: status_callback("🔗 PASO 1/2: COMPONIENDO VIDEO Y SUPERPOSICIONES...", "#FFD700")
        
        body_video_only_ts = os.path.abspath(os.path.join(cache_chunks, "body_video_only.ts"))
        body_ts = os.path.abspath(os.path.join(cache_chunks, "body_mix.ts"))
        
        # --- COMPOSICIÓN DE VIDEO CON TRANSICIONES DINÁMICAS ---
        f_s = "[0:v]copy[v0];"
        for i in range(1, len(chunk_files)):
            t_idx = min(i - 1, len(chosen_transition_names) - 1)
            t_name = chosen_transition_names[t_idx]
            t_dur = t_durs[t_idx]
            offset_val = transition_offsets[t_idx]
            f_s += f"[v{i-1}][{i}:v]xfade=transition={t_name}:duration={t_dur:.2f}:offset={offset_val:.2f}[v{i}];"
            
        last_v = f"v{len(chunk_files)-1}"
        mid_t = total_visual_dur * 0.48
        f_s += f"[{last_v}]negate=enable='between(t,{mid_t:.2f},{mid_t+0.15:.2f})'[v_final]"

        in_cmd_video = []
        for c in chunk_files:
            in_cmd_video.extend(["-i", c])
        
        num_chunks = len(chunk_files)
        for idx, broll in enumerate(downloaded_brolls):
            in_cmd_video.extend(["-stream_loop", "-1", "-i", broll["path"]])
            broll["input_idx_video"] = num_chunks + idx

        if downloaded_brolls:
            broll_filters = ""
            v_current = "v_final"
            for idx, broll in enumerate(downloaded_brolls):
                v_next = f"v_broll_{idx}"
                broll_filters += f"[{broll['input_idx_video']}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=bilinear,crop={target_w}:{target_h},format=yuv420p[broll_{idx}_scaled];"
                broll_filters += f"[{v_current}][broll_{idx}_scaled]overlay=0:0:enable='between(t,{broll['start']:.3f},{broll['end']:.3f})'[{v_next}];"
                v_current = v_next
            f_s += ";" + broll_filters.strip(";")
            v_l = v_current
        else:
            v_l = "v_final"

        temp_srt_mirror = os.path.abspath(os.path.join(cache_ass, "temp_subs_final.ass"))
        if enable_subtitles and srt_path and os.path.exists(srt_path):
            try:
                shutil.copy2(srt_path, temp_srt_mirror)
                time.sleep(0.2)
                abs_srt = temp_srt_mirror.replace('\\', '/').replace(':', '\\:')
                f_s += f";[{v_l}]subtitles=filename='{abs_srt}'[vs]"
                v_l = "vs"
            except Exception as e:
                print(f"Error copiando subtítulos: {e}")

        cpu_params = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-maxrate", "5M", "-bufsize", "10M", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high"]
        if hw_failed[0] or "-c:v" not in enc_params or "libx264" in enc_params:
            final_enc_params = cpu_params
        else:
            final_enc_params = enc_params

        # Se inyecta -r 30 para limitar el framerate de la composición final
        cmd_video = ["ffmpeg", "-y", "-threads", "2", "-filter_complex_threads", "2"] + in_cmd_video + ["-filter_complex", f_s, "-map", f"[{v_l}]", "-r", "30"] + final_enc_params + ["-an", "-f", "mpegts", "-t", str(total_visual_dur), body_video_only_ts]
        err_log = os.path.join(cache_base, "ffmpeg_video_err.log")
        try:
            with open(err_log, "w", encoding="utf-8", errors="replace") as f_err:
                subprocess.run(cmd_video, check=True, stdout=subprocess.DEVNULL, stderr=f_err, **sub_kwargs)
            safe_remove(err_log)
        except subprocess.CalledProcessError as e:
            try:
                with open(err_log, "r", encoding="utf-8", errors="replace") as f_read:
                    err_text = f_read.read()
            except:
                err_text = "No se pudo leer el archivo de log."
            safe_remove(err_log)
            print(f"--- FFMPEG VIDEO ERROR LOG ---\n{err_text}\n------------------------")
            if final_enc_params != cpu_params:
                print("Video-only render with hardware encoder failed. Retrying with CPU fallback...")
                cmd_video_fallback = ["ffmpeg", "-y", "-threads", "2", "-filter_complex_threads", "2"] + in_cmd_video + ["-filter_complex", f_s, "-map", f"[{v_l}]", "-r", "30"] + cpu_params + ["-an", "-f", "mpegts", "-t", str(total_visual_dur), body_video_only_ts]
                try:
                    with open(err_log, "w", encoding="utf-8", errors="replace") as f_err2:
                        subprocess.run(cmd_video_fallback, check=True, stdout=subprocess.DEVNULL, stderr=f_err2, **sub_kwargs)
                    safe_remove(err_log)
                except subprocess.CalledProcessError as e_fallback:
                    try:
                        with open(err_log, "r", encoding="utf-8", errors="replace") as f_read2:
                            err_text_fallback = f_read2.read()
                    except:
                        err_text_fallback = "No se pudo leer el archivo de log."
                    safe_remove(err_log)
                    print(f"--- FFMPEG VIDEO FALLBACK ERROR LOG ---\n{err_text_fallback}\n------------------------")
                    raise Exception(f"Fallo en renderizado de video FFmpeg (Fallback CPU también falló): {err_text_fallback[:100]}")
            else:
                raise Exception(f"Fallo en renderizado de video FFmpeg: {err_text[:100]}")

        # --- PASO 2/2: COMPOSICIÓN Y MEZCLA DE AUDIOS ---
        if status_callback: status_callback("🎚️ PASO 2/2: MEZCLANDO Y SINCRONIZANDO AUDIO...", "#FFD700")

        trans_dir = os.path.join("assets", "audio", "transitions")
        riser_path = os.path.abspath(os.path.join(trans_dir, "real_riser.mp3"))
        impact_path = os.path.abspath(os.path.join(trans_dir, "real_impact.mp3"))
        sfx_pool = [
            os.path.abspath(os.path.join(trans_dir, "real_glitch.mp3")),
            os.path.abspath(os.path.join(trans_dir, "real_boom.mp3")),
            os.path.abspath(os.path.join(trans_dir, "real_whoosh.mp3"))
        ]

        in_cmd_audio = ["-i", body_video_only_ts]
        in_cmd_audio.extend(["-i", audio_full_path])
        idx_voice = 1
        
        in_cmd_audio.extend(["-i", riser_path, "-i", impact_path])
        idx_riser = 2
        idx_impact = 3
        
        n_x = 4
        a_c = 0
        
        num_trans = len(transition_offsets)
        a_m = f"[{idx_riser}:a]asplit={num_trans}" + "".join([f"[r_raw{i}]" for i in range(num_trans)]) + ";"
        a_m += f"[{idx_impact}:a]asplit={num_trans+1}" + "".join([f"[im_raw{i}]" for i in range(num_trans+1)]) + ";"

        vol_voice_mult = vol_voice / 100.0
        vol_music_mult = 0.4 * (vol_music / 100.0)
        vol_sfx_mult = vol_sfx / 100.0

        if music_path:
            a_m += f"[{idx_voice}:a]loudnorm=I=-16,volume={vol_voice_mult:.2f},asplit=2[v_main][v_sc];"
        else:
            a_m += f"[{idx_voice}:a]loudnorm=I=-16,volume={vol_voice_mult:.2f}[v_main];"
        
        a_i = "[v_main]"; a_c += 1
        
        a_m += f"[im_raw{num_trans}]atrim=0:1.0,volume={0.8 * vol_sfx_mult:.2f}[init_impact];"
        a_i += "[init_impact]"; a_c += 1

        for i, offset in enumerate(transition_offsets):
            sfx_path = random.choice(sfx_pool)
            in_cmd_audio.extend(["-i", sfx_path])
            idx_sfx = n_x; n_x += 1
            
            a_m += f"[r_raw{i}]atrim=0:0.5,afade=t=in:st=0:d=0.4,volume={0.6 * vol_sfx_mult:.2f},adelay={max(0, int((offset-0.5)*1000))}|{max(0, int((offset-0.5)*1000))}[r{i}];"
            a_m += f"[im_raw{i}]atrim=0:0.5,volume={1.0 * vol_sfx_mult:.2f},adelay={int(offset*1000)}|{int(offset*1000)}[im{i}];"
            a_m += f"[{idx_sfx}:a]silenceremove=start_periods=1:start_duration=0:start_threshold=-40dB,atrim=0:1.0,afade=t=out:st=0.5:d=0.5,volume={1.0 * vol_sfx_mult:.2f},adelay={int(offset*1000)}|{int(offset*1000)}[s{i}];"
            
            a_i += f"[r{i}][im{i}][s{i}]"
            a_c += 3

        # --- PREPARACIÓN DE SFX EVENTOS Y CAPAS (Pilar 1, 3 y 4) ---
        json_path = os.path.join(temp_dir, "data_mix.json")
        sfx_events = extract_sfx_events(json_path)
        
        # Clasificar los eventos
        ambient_events = [e for e in sfx_events if e["type"] == "ambient"]
        impact_events = [e for e in sfx_events if e["type"] == "impact"]
        
        # Ordenar ambientes cronológicamente para calcular duraciones (Pilar 3: Solo 1 ambiente activo)
        ambient_events.sort(key=lambda x: x["start"])
        
        # Generar expresión de Ducking de Música reactiva a impactos (Pilar 4)
        # Atenuar 50% extra durante 1.8 segundos cuando ocurre un impacto fuerte
        music_ducking_expr = f"{vol_music_mult:.4f}"
        if music_path and impact_events:
            ducking_clauses = []
            for e in impact_events:
                t1 = e["start"]
                t2 = t1 + 1.8
                ducking_clauses.append(f"between(t,{t1:.3f},{t2:.3f})")
            
            sum_clauses = " + ".join(ducking_clauses)
            # Expresión de volumen FFmpeg: evalúa si t está en un rango de impacto y baja a la mitad
            music_ducking_expr = f"({vol_music_mult:.4f}*(1.0-0.5*min(1.0,{sum_clauses})))"

        # --- MUSICA DE FONDO (con ducking adaptativo) ---
        try:
            if music_path:
                in_cmd_audio.extend(["-i", os.path.abspath(music_path)])
                # Usar expresión matemática en el filtro volume para el Pilar 4
                a_m += f"[{n_x}:a]silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,volume=eval=frame:volume='{music_ducking_expr}'[m_pre];[m_pre][v_sc]sidechaincompress=threshold=0.04:ratio=6:attack=2:release=150[bg_duck];"
                a_i += "[bg_duck]"; a_c += 1; n_x += 1
        except Exception as me:
            print(f"[ERROR] Musica de fondo falló: {me}")
            if status_callback:
                status_callback(f"⚠️ ERROR MUSICA DE FONDO: {me}", "orange")

        # --- INYECCIÓN DE SFX DE AMBIENTE (Pilar 1: Bucle + Fade-In/Out) ---
        for idx_a, e in enumerate(ambient_events):
            sfx_path = e["path"]
            start_time = e["start"]
            
            # Calcular duración efectiva del ambiente
            if idx_a < len(ambient_events) - 1:
                end_time = ambient_events[idx_a + 1]["start"]
            else:
                end_time = total_visual_dur
            
            duration = end_time - start_time
            if duration <= 0.5:
                continue # Demasiado corto para inyectar
                
            # Configurar fundidos dinámicos
            fade_dur = min(2.0, duration / 2.0)
            fade_in = f"afade=t=in:ss=0:d={fade_dur:.3f}"
            fade_out = f"afade=t=out:st={duration - fade_dur:.3f}:d={fade_dur:.3f}"
            
            # Inyectar con loop infinito antes del input
            in_cmd_audio.extend(["-stream_loop", "-1", "-i", sfx_path])
            delay_ms = int(start_time * 1000)
            
            # Filtro FFmpeg: Recortar a duración efectiva, aplicar fundidos y delay
            a_m += f"[{n_x}:a]atrim=0:{duration:.3f},{fade_in},{fade_out},volume={0.08 * vol_sfx_mult:.4f},adelay={delay_ms}|{delay_ms}[amb{n_x}];"
            a_i += f"[amb{n_x}]"; a_c += 1; n_x += 1

        # --- INYECCIÓN DE SFX DE IMPACTO (Pilar 1: One-Shot a volumen controlado) ---
        for e in impact_events:
            sfx_path = e["path"]
            start_time = e["start"]
            delay_ms = int(start_time * 1000)
            
            in_cmd_audio.extend(["-i", sfx_path])
            # Inyectar a un volumen de impacto controlado de 0.22 max
            a_m += f"[{n_x}:a]volume={0.22 * vol_sfx_mult:.4f},adelay={delay_ms}|{delay_ms}[imp{n_x}];"
            a_i += f"[imp{n_x}]"; a_c += 1; n_x += 1



        a_m = a_m.strip(";") + f";{a_i}amix=inputs={a_c}:duration=longest:normalize=0[af]"
        
        cmd_audio_merge = ["ffmpeg", "-y", "-threads", "2"] + in_cmd_audio + ["-filter_complex", a_m, "-map", "0:v", "-map", "[af]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100", "-f", "mpegts", "-t", str(total_visual_dur), body_ts]
        err_audio_log = os.path.join(cache_base, "ffmpeg_audio_err.log")
        try:
            with open(err_audio_log, "w", encoding="utf-8", errors="replace") as f_err:
                subprocess.run(cmd_audio_merge, check=True, stdout=subprocess.DEVNULL, stderr=f_err, **sub_kwargs)
            safe_remove(err_audio_log)
        except subprocess.CalledProcessError as e:
            try:
                with open(err_audio_log, "r", encoding="utf-8", errors="replace") as f_read:
                    err_text = f_read.read()
            except:
                err_text = "No se pudo leer el archivo de log."
            safe_remove(err_audio_log)
            print(f"--- FFMPEG AUDIO MERGE ERROR LOG ---\n{err_text}\n------------------------")
            raise Exception(f"Fallo en mezcla final de audio FFmpeg: {err_text[:200]}")

        # FINAL CON GESTIÓN DE PERMISOS
        if status_callback: status_callback("💾 GUARDANDO RENDER MIX...", "#00FF41")
        v_final = os.path.join(output_folder, f"{safe_title}.mp4")
        counter = 1; base_v_final = v_final
        while True:
            try:
                if os.path.exists(v_final): os.remove(v_final)
                break
            except:
                v_final = base_v_final.replace(".mp4", f"_({counter}).mp4")
                counter += 1
                if counter > 10: break

        cmd_final = ["ffmpeg", "-y", "-threads", "2", "-i", body_ts, "-c", "copy", "-movflags", "+faststart", v_final]
        err_final_log = os.path.join(cache_base, "ffmpeg_final_err.log")
        try:
            with open(err_final_log, "w", encoding="utf-8", errors="replace") as f_err:
                subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=f_err, **sub_kwargs)
            safe_remove(err_final_log)
        except subprocess.CalledProcessError as e:
            try:
                with open(err_final_log, "r", encoding="utf-8", errors="replace") as f_read:
                    err_text = f_read.read()
            except:
                err_text = "No se pudo leer el archivo de log."
            safe_remove(err_final_log)
            print(f"--- FFMPEG FINAL REMUX ERROR LOG ---\n{err_text}\n------------------------")
            raise Exception(f"Fallo en copia final de video FFmpeg: {err_text[:200]}")

        # Guardar título y descripción en un archivo .txt complementario
        try:
            txt_final = v_final.rsplit(".", 1)[0] + ".txt"
            with open(txt_final, "w", encoding="utf-8") as f_desc:
                f_desc.write(f"TÍTULO:\n{title}\n\nDESCRIPCIÓN:\n{description}\n")
            print(f"Saved description file to: {txt_final}")
        except Exception as e_desc:
            print(f"Error guardando descripción txt: {e_desc}")


        # Limpieza (se mantiene la caché de chunks)

        for broll in downloaded_brolls_to_clean: safe_remove(broll["path"])
        safe_remove(body_ts); safe_remove(body_video_only_ts); safe_remove(temp_srt_mirror)



        duration = time.time() - _telemetry_start
        telemetry.record({
            "function": "render_mix_mode",
            "output_path": os.path.join(output_folder, f"{safe_title}.mp4"),
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat()
        })
        return v_final
    except Exception as e:
        import traceback
        traceback.print_exc()
        if status_callback: status_callback(f"🛑 Error Mix: {str(e)[:50]}", "red")
        return None
