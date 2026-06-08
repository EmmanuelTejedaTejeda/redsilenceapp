import os
import subprocess
import random
import time
import json
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from modules.render_utils import (
    detect_hardware_encoder, 
    convert_to_word_by_word_srt, 
    safe_remove, 
    get_video_duration,
    extract_sfx_events
)

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

def render_mix_mode(audio_path, mixed_media, cover_path, output_folder, title, description, vhs_enabled, music_path=None, status_callback=None, groq_key=None, aspect_ratio="9:16", lut_name=None, sub_style="TikTok / Hormozi", reddit_card_title=None, pacing="Dinámico [2.0s]", vol_voice=100.0, vol_music=40.0, vol_sfx=100.0):
    sub_kwargs = {}
    
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
    
    # --- CONFIGURACIÓN DE RESOLUCIÓN DINÁMICA ---
    if aspect_ratio == "16:9":
        target_w, target_h = 1920, 1080
        scale_w, scale_h = 2275, 1280
    else:
        target_w, target_h = 1080, 1920
        scale_w, scale_h = 1280, 2275
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
        use_cache = False
        audio_mtime = os.path.getmtime(audio_full_path) if os.path.exists(audio_full_path) else 0
        audio_size = os.path.getsize(audio_full_path) if os.path.exists(audio_full_path) else 0
        if os.path.exists(cache_file) and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0 and os.path.exists(final_json_path):
            try:
                with open(cache_file, "r") as f: cache_data = json.load(f)
                if (cache_data.get("original_audio_path") == audio_full_path and 
                    abs(cache_data.get("original_duration", 0) - audio_dur) < 0.1 and
                    cache_data.get("original_mtime") == audio_mtime and
                    cache_data.get("original_size") == audio_size):
                    use_cache = True
            except Exception as e: 
                print(f"Error leyendo cache de subtítulos: {e}")

        if use_cache:
            if status_callback: status_callback("♻️ USANDO SUBTÍTULOS EN CACHÉ", "#00E676")
            try:
                with open(final_json_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
            except Exception:
                use_cache = False
        else:
            if status_callback: status_callback("🧠 GENERANDO SUBTÍTULOS (GROQ)...", "#FFD700")
            try:
                from modules.render_utils import transcribe_with_groq
                if groq_key:
                    result = transcribe_with_groq(audio_full_path, groq_key, language="es")
                else:
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
            audio_full_path = ramped_audio_path
            audio_dur = get_video_duration(audio_full_path)
            result = new_json
            
            with open(final_json_path, 'w', encoding='utf-8') as f: json.dump(result, f)
            convert_to_word_by_word_srt(final_json_path, srt_path, status_callback, aspect_ratio=aspect_ratio, sub_style=sub_style)
            
            with open(cache_file, "w") as f:
                json.dump({
                    "original_audio_path": original_audio_path,
                    "original_duration": original_duration,
                    "original_mtime": audio_mtime,
                    "original_size": audio_size,
                    "audio_path": audio_full_path,
                    "duration": audio_dur
                }, f)
        else:
            srt_path = None

        if status_callback: status_callback("⚙️ VERIFICANDO ACELERACIÓN DE HARDWARE...", "#00E5FF")
        enc_params = detect_hardware_encoder(output_folder)
        total_visual_dur = audio_dur + 0.3

        # --- CARGAR AJUSTES PARA PEXELS KEY ---
        pexels_key = ""
        try:
            settings_path = os.path.abspath(os.path.join(project_root, "config", "settings.json"))
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    pexels_key = settings.get("pexels_api_key", "")
        except Exception as e:
            print(f"Error cargando settings para Pexels Key: {e}")

        # --- EXTRACCIÓN DE INTERVALOS DE HORROR Y B-ROLL ---
        horror_intervals = []
        horror_keywords = [
            "terror", "miedo", "sangre", "muerte", "sombra", "oscuridad",
            "grito", "espejo", "dolor", "fantasma", "rostro", "monstruo",
            "silencio", "detrás", "atrás", "peligro", "morir", "asesino",
            "cuerpo", "cadáver", "tumba", "cementerio", "alma", "espíritu",
            "sangriento", "oscura", "gritos", "fantasmas", "monstruos",
            "silencioso", "peligroso", "muerto", "muerta", "muertos",
            "grifo", "horror", "creepy", "susto", "oscuro"
        ]

        broll_keywords_map = {
            # Terror / Spooky
            "sombra": "scary shadow",
            "sombras": "dark shadows",
            "fantasma": "ghost spooky",
            "fantasmas": "ghosts",
            "espectro": "apparition spooky",
            "espíritu": "spirit ghostly",
            "espiritu": "spirit ghostly",
            "almas": "lost souls",
            "demonio": "demon scary",
            "demonios": "demons",
            "monstruo": "scary monster",
            "monstruos": "monsters",
            "criatura": "creature creepy",
            "pesadilla": "nightmare dark",
            "aparición": "paranormal activity",
            "aparicion": "paranormal activity",
            
            # Lugares / Ambientación
            "cementerio": "cemetery spooky",
            "tumba": "grave cemetery",
            "tumbas": "graves cemetery",
            "bosque": "dark forest",
            "bosques": "dark forest night",
            "habitación": "dark empty room",
            "habitacion": "dark empty room",
            "cuarto": "spooky bedroom",
            "sótano": "dark basement",
            "sotano": "dark basement",
            "ático": "dusty attic",
            "atico": "dusty attic",
            "pasillo": "dark hallway",
            "casa": "abandoned house creepy",
            "cabaña": "spooky cabin",
            "cabana": "spooky cabin",
            "calle": "dark empty street",
            "niebla": "foggy night",
            
            # Cuerpo / Muerte
            "sangre": "blood splash",
            "sangriento": "bloody horror",
            "muerte": "grim reaper silhouette",
            "muerto": "dead body outline",
            "muerta": "dead body outline",
            "cadáver": "corpse dark",
            "cadaver": "corpse dark",
            "cuerpo": "human silhouette dark",
            "rostro": "creepy face",
            "cara": "scary face close up",
            "ojos": "staring eyes dark",
            "manos": "creepy hands",
            "mano": "creepy hand reaching",
            "huesos": "skeleton bones",
            
            # Acciones / Eventos
            "grito": "screaming mouth",
            "gritos": "screaming silhouette",
            "llanto": "crying person dark",
            "pasos": "footsteps shadow walking",
            "respiración": "breathing silhouette",
            "respiracion": "breathing silhouette",
            "correr": "running in panic",
            "escapar": "escaping dark",
            "susurro": "whispering mouth",
            "susurros": "whispering shadow",
            
            # Objetos / Símbolos
            "espejo": "scary mirror reflection",
            "puerta": "creepy door opening",
            "ventana": "rainy window dark",
            "grifo": "dripping faucet tap",
            "agua": "dark deep water",
            "velas": "burning candles dark",
            "vela": "candle flame dark",
            "reloj": "old ticking clock",
            "teléfono": "old rotary phone",
            "telefono": "old rotary phone",
            "llave": "rusty key lock",
            "cuchillo": "knife silhouette",
            
            # Sensaciones / Adjetivos
            "oscuridad": "pitch black dark",
            "oscuro": "dark texture",
            "oscura": "dark background",
            "silencio": "quiet forest",
            "miedo": "scary face horror",
            "terror": "spooky background",
            "peligro": "warning alert dark",
            "frío": "cold winter forest",
            "frio": "cold winter forest"
        }

        broll_matches = []
        if result and "segments" in result:
            for segment in result["segments"]:
                words_data = segment.get("words", [])
                if words_data:
                    for w in words_data:
                        w_text = w["word"].strip().replace('"', '').upper()
                        clean_w = "".join([c for c in w_text if c.isalnum()]).lower()
                        # Horror check
                        if clean_w in horror_keywords:
                            horror_intervals.append((w["start"], w["end"]))
                        # B-roll check
                        if clean_w in broll_keywords_map:
                            broll_matches.append({
                                "query": broll_keywords_map[clean_w],
                                "start": w["start"],
                                "end": w["end"]
                            })
                else:
                    text = segment.get("text", "").strip()
                    if text:
                        words = text.split()
                        seg_start = segment.get("start", 0.0)
                        seg_end = segment.get("end", 0.0)
                        dur_per_word = (seg_end - seg_start) / max(1, len(words))
                        for i, w in enumerate(words):
                            w_text = w.strip().replace('"', '').upper()
                            clean_w = "".join([c for c in w_text if c.isalnum()]).lower()
                            # Horror check
                            if clean_w in horror_keywords:
                                horror_intervals.append((seg_start + (i * dur_per_word), seg_start + ((i + 1) * dur_per_word)))
                            # B-roll check
                            if clean_w in broll_keywords_map:
                                broll_matches.append({
                                    "query": broll_keywords_map[clean_w],
                                    "start": seg_start + (i * dur_per_word),
                                    "end": seg_start + ((i + 1) * dur_per_word)
                                })

        # Seleccionar hasta 6 B-rolls sin superposición y sin duplicar la misma consulta en el video
        selected_brolls = []
        used_queries = set()
        for match in broll_matches:
            if len(selected_brolls) >= 6:
                break
            if match["query"] in used_queries:
                continue
                
            p_start = max(0.0, match["start"] - 0.5)
            # Adjust B-roll duration based on pacing_dur
            broll_duration = max(1.2, min(2.5, pacing_dur))
            p_end = min(total_visual_dur, p_start + broll_duration)
            
            overlap = False
            for sel in selected_brolls:
                if not (p_end + 1.0 < sel["start"] or p_start > sel["end"] + 1.0):
                    overlap = True
                    break
            if not overlap:
                selected_brolls.append({
                    "query": match["query"],
                    "start": p_start,
                    "end": p_end,
                    "duration": p_end - p_start
                })
                used_queries.add(match["query"])

        # Descargar B-rolls desde Pexels
        downloaded_brolls = []
        if pexels_key and selected_brolls:
            from modules.pexels_client import search_pexels_video, download_video_file
            for idx, broll in enumerate(selected_brolls):
                if status_callback:
                    status_callback(f"🔍 BUSCANDO B-ROLL: '{broll['query']}'...", "#FFD700")
                video_url = search_pexels_video(broll["query"], pexels_key, orientation="portrait")
                if video_url:
                    local_path = os.path.abspath(os.path.join(cache_chunks, f"broll_{idx}.mp4"))
                    if status_callback:
                        status_callback(f"📥 DESCARGANDO B-ROLL: {broll['query']}...", "#00E5FF")
                    success_dl = download_video_file(video_url, local_path)
                    if success_dl and os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                        broll["path"] = local_path
                        downloaded_brolls.append(broll)
                    else:
                        print(f"Error descargando B-roll de: {video_url}")
                else:
                    print(f"No se encontró video en Pexels para: {broll['query']}")
        
        # --- CÁLCULO DE TIEMPOS DINÁMICOS Y COMPENSACIÓN DE TRANSICIONES ---
        sub_dur = 0.25 # Duración ultra-rápida para flashes subliminales (7-8 frames)
        sub_items = [m for m in mixed_media if isinstance(m, dict) and m.get("is_subliminal")]
        
        # Calcular el tiempo que se va a "perder" (solapar) en todas las transiciones xfade
        total_t_dur = 0
        for i in range(1, len(mixed_media)):
            is_sub_p = isinstance(mixed_media[i-1], dict) and mixed_media[i-1].get("is_subliminal")
            is_sub_c = isinstance(mixed_media[i], dict) and mixed_media[i].get("is_subliminal")
            total_t_dur += 0.05 if (is_sub_p or is_sub_c) else 0.5
            
        total_sub_time = len(sub_items) * sub_dur
        remaining_time = max(0.1, total_visual_dur - total_sub_time + total_t_dur)
        
        # Asignar pesos asimétricos e impredecibles para los cortes (Micro-Cortes de Ritmo)
        # 18% de probabilidad de ser un "flash cut" súper rápido (peso 0.15), el resto aleatorio
        weights = []
        for m in mixed_media:
            is_sub = isinstance(m, dict) and m.get("is_subliminal")
            if is_sub:
                weights.append(0.0)
            else:
                if random.random() < 0.18:
                    weights.append(random.uniform(0.12, 0.20)) # Flash cut
                else:
                    weights.append(random.uniform(0.70, 1.30)) # Corte irregular
                    
        normal_weights_sum = sum(w for w in weights if w > 0.0)
        if normal_weights_sum <= 0:
            normal_weights_sum = 1.0
            
        # Calcular duraciones reales finales asimétricas
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

                chunk_name = os.path.abspath(os.path.join(cache_chunks, f"chunk_mix_{i:03d}.mp4"))
                render_dur = dur + 1.0
                frames = int(render_dur * 30)
                
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

                if i == 0 and not is_subliminal:
                    # GANCHO AGRESIVO: Sismo cinemático (temblor sutil) + Zoom-In progresivo en los primeros segundos
                    if item_type == "video":
                        sx_base = f"(iw-ow)*0.02*(0.8*sin(6*PI*t)+0.2*sin(12*PI*t))*exp(-1.2*t)"
                        sy_base = f"(ih-oh)*0.02*(0.8*sin(5*PI*t+1.57)+0.2*sin(10*PI*t))*exp(-1.2*t)"
                        if local_glitches:
                            sx = f"{sx_base} + 18*sin(60*t)*({shake_expr})"
                            sy = f"{sy_base} + 18*cos(50*t)*({shake_expr})"
                        else:
                            sx = sx_base
                            sy = sy_base
                        scale_w_eff = int(target_w * 1.35)
                        scale_h_eff = int(target_h * 1.35)
                        vf_base = f"scale={scale_w_eff}:{scale_h_eff}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}:'(iw-ow)/2+{sx}':'(ih-oh)/2+{sy}'"
                        input_opts_list = ["-stream_loop", "-1"]
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
                        vf_base = f"loop=loop=-1:size=1:start=0,scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},zoompan=z='{ze}':d={frames+2}:x='(iw-iw/zoom)/2+{xe}':y='(ih-ih/zoom)/2+{ye}':s={target_w}x{target_h}:fps=30"
                        input_opts_list = []
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
                        sx_base = f"(iw-ow)*{xa:.2f}*0.05*(0.8*sin({xf:.1f}*PI*t)+0.2*sin({xf*3.14:.1f}*PI*t))"
                        sy_base = f"(ih-oh)*{ya:.2f}*0.05*(0.8*sin({yf:.1f}*PI*t+1.57)+0.2*sin({yf*2.71:.1f}*PI*t))"
                        if local_glitches:
                            sx = f"{sx_base} + 18*sin(60*t)*({shake_expr})"
                            sy = f"{sy_base} + 18*cos(50*t)*({shake_expr})"
                        else:
                            sx = sx_base
                            sy = sy_base
                        if dur > pacing_dur:
                            # Para video largo, hacemos un jump cut de zoom de 1.0x a 1.25x en el 60%
                            jump_t = dur * 0.6
                            vf_base = (
                                f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}:'(iw-ow)/2+{sx}':'(ih-oh)/2+{sy}',"
                                f"zoompan=z='if(gte(in_time,{jump_t:.2f}),1.25,1.0)':d=1:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s={target_w}x{target_h}:fps=30"
                            )
                        else:
                            vf_base = f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}:'(iw-ow)/2+{sx}':'(ih-oh)/2+{sy}'"
                        input_opts_list = ["-stream_loop", "-1"]
                    else:
                        xe_base = f"(iw-iw/zoom)*{xa:.2f}*0.03*(0.8*sin({xf:.1f}*on/30)+0.2*sin({xf*3.14:.1f}*on/30))"
                        ye_base = f"(ih-ih/zoom)*{ya:.2f}*0.03*(0.8*sin({yf:.1f}*on/30+1.57)+0.2*sin({yf*2.71:.1f}*on/30))"
                        if local_glitches:
                            xe = f"{xe_base} + 18*sin(60*on/30)*({shake_expr_zoom})"
                            ye = f"{ye_base} + 18*cos(50*on/30)*({shake_expr_zoom})"
                        else:
                            xe = xe_base
                            ye = ye_base
                        vf_base = f"loop=loop=-1:size=1:start=0,scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},zoompan=z='{ze_normal}':d={frames+2}:x='(iw-iw/zoom)/2+{xe}':y='(ih-ih/zoom)/2+{ye}':s={target_w}x{target_h}:fps=30"
                        input_opts_list = []
                
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
                    cvf = f"[0:v]{vf_final},format=gbrp[b];[1:v]scale={target_w}:{target_h},hue=s=0,format=gbrp[v];[b][v]blend=all_mode=screen:all_opacity=0.08[mixed];[mixed][2:v]overlay=(W-w)/2:y='((H-h)/2+(H-(H-h)/2)*exp(-8*t))*lt(t,0.6)+(H-h)/2*gte(t,0.6)':enable='between(t\\,0\\,{card_duration})',format=yuv420p"
                    
                    active_enc = ["-c:v", "libx264", "-preset", "ultrafast", "-b:v", "2200k", "-pix_fmt", "yuv420p"] if hw_failed[0] else enc
                    cmd = ["ffmpeg", "-y", "-threads", "2"] + input_opts_list + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-i", card_png_path, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30"] + active_enc + ["-an", chunk_name]
                    try:
                        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                    except Exception as e:
                        if not hw_failed[0]:
                            print(f"HW encoder failed for chunk {i}, falling back to CPU. Error: {e}")
                            hw_failed[0] = True
                        cmd_fallback = ["ffmpeg", "-y", "-threads", "2"] + input_opts_list + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-i", card_png_path, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-an", chunk_name]
                        subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                else:
                    vf_final = f"{vf_base},format=yuv420p,{fx_chain},{sub_fx}{lut_filter}{glitch_fx}"
                    cvf = f"[0:v]{vf_final},format=gbrp[b];[1:v]scale={target_w}:{target_h},hue=s=0,format=gbrp[v];[b][v]blend=all_mode=screen:all_opacity=0.08,format=yuv420p"
                    
                    active_enc = ["-c:v", "libx264", "-preset", "ultrafast", "-b:v", "2200k", "-pix_fmt", "yuv420p"] if hw_failed[0] else enc
                    cmd = ["ffmpeg", "-y", "-threads", "2"] + input_opts_list + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30"] + active_enc + ["-an", chunk_name]
                    try:
                        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                    except Exception as e:
                        if not hw_failed[0]:
                            print(f"HW encoder failed for chunk {i}, falling back to CPU. Error: {e}")
                            hw_failed[0] = True
                        cmd_fallback = ["ffmpeg", "-y", "-threads", "2"] + input_opts_list + ["-i", media_path, "-stream_loop", "-1", "-i", vhs_p, "-t", str(render_dur), "-filter_complex", cvf, "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-an", chunk_name]
                        subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                
                if has_audio and item_type == "video":
                    ach = os.path.abspath(os.path.join(cache_audio, f"audio_mix_{i:03d}.wav"))
                    cmd_audio = ["ffmpeg", "-y", "-threads", "2", "-i", media_path, "-t", str(render_dur), "-vn", "-ac", "2", "-ar", "44100", ach]
                    subprocess.run(cmd_audio, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                
                processed_mix += 1
                if status_callback: status_callback(f"🌪️ MEZCLANDO MEDIA: {processed_mix}/{len(mixed_media)}", "#00E5FF")
                return chunk_name
            except Exception as e:
                print(f"Error procesando chunk {i}: {e}")
                return None

        vhs_bg = os.path.abspath(os.path.join("assets", "video", "fx", "vhs_overlay.mp4"))
        tks = []
        for i, m in enumerate(mixed_media):
            d = clip_durations[i]
            tks.append((i, m, enc_params, d, vhs_bg, title, sub_style, horror_intervals, clip_durations))

        # Evitar saturar el CPU y disco con múltiples renders simultáneos.
        max_workers = min(len(tks), 2)

        with ThreadPoolExecutor(max_workers=max_workers) as ex: 
            chunk_files = [c for c in list(ex.map(process_chunk, tks)) if c]
        
        if not chunk_files: raise Exception("No se procesaron clips en modo MIX.")

        # COMPOSICIÓN, MEZCLA FINAL DE AUDIO Y SUBTÍTULOS ASS (ETAPA DE DOS PASOS PARA PREVENIR OUT-OF-MEMORY)
        if status_callback: status_callback("🔗 PASO 1/2: COMPONIENDO VIDEO Y SUPERPOSICIONES...", "#FFD700")
        
        body_video_only_ts = os.path.abspath(os.path.join(cache_chunks, "body_video_only.ts"))
        body_ts = os.path.abspath(os.path.join(cache_chunks, "body_mix.ts"))
        
        # --- COMPOSICIÓN DE VIDEO CON TRANSICIONES DINÁMICAS ---
        f_s = "[0:v]copy[v0];"
        possible_transitions = ["hblur", "pixelize", "distance", "radial", "smoothleft", "zoomin", "circlecrop", "fadeblack"]
        transition_offsets = []
        current_offset = 0

        for i in range(1, len(chunk_files)):
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
            f_s += f"[v{i-1}][{i}:v]xfade=transition={t_name}:duration={t_dur:.2f}:offset={current_offset:.2f}[v{i}];"
            
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
                broll_filters += f"[{broll['input_idx_video']}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},format=yuv420p[broll_{idx}_scaled];"
                broll_filters += f"[{v_current}][broll_{idx}_scaled]overlay=0:0:enable='between(t,{broll['start']:.3f},{broll['end']:.3f})'[{v_next}];"
                v_current = v_next
            f_s += ";" + broll_filters.strip(";")
            v_l = v_current
        else:
            v_l = "v_final"

        temp_srt_mirror = os.path.abspath(os.path.join(cache_ass, "temp_subs_final.ass"))
        if srt_path and os.path.exists(srt_path):
            try:
                import shutil
                shutil.copy2(srt_path, temp_srt_mirror)
                time.sleep(0.2)
                abs_srt = temp_srt_mirror.replace('\\', '/').replace(':', '\\:')
                f_s += f";[{v_l}]subtitles=filename='{abs_srt}'[vs]"
                v_l = "vs"
            except Exception as e:
                print(f"Error copiando subtítulos: {e}")

        cpu_params = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-maxrate", "5M", "-bufsize", "10M", "-pix_fmt", "yuv420p"]
        if hw_failed[0] or "-c:v" not in enc_params or "libx264" in enc_params:
            final_enc_params = cpu_params
        else:
            final_enc_params = enc_params

        cmd_video = ["ffmpeg", "-y", "-threads", "2"] + in_cmd_video + ["-filter_complex", f_s, "-map", f"[{v_l}]"] + final_enc_params + ["-an", "-f", "mpegts", "-t", str(total_visual_dur), body_video_only_ts]
        try:
            subprocess.run(cmd_video, check=True, capture_output=True, text=True, errors='replace', **sub_kwargs)
        except subprocess.CalledProcessError as e:
            print(f"--- FFMPEG VIDEO ERROR LOG ---\n{e.stderr}\n------------------------")
            if final_enc_params != cpu_params:
                print("Video-only render with hardware encoder failed. Retrying with CPU fallback...")
                cmd_video_fallback = ["ffmpeg", "-y", "-threads", "2"] + in_cmd_video + ["-filter_complex", f_s, "-map", f"[{v_l}]"] + cpu_params + ["-an", "-f", "mpegts", "-t", str(total_visual_dur), body_video_only_ts]
                try:
                    subprocess.run(cmd_video_fallback, check=True, capture_output=True, text=True, errors='replace', **sub_kwargs)
                except subprocess.CalledProcessError as e_fallback:
                    print(f"--- FFMPEG VIDEO FALLBACK ERROR LOG ---\n{e_fallback.stderr}\n------------------------")
                    raise Exception(f"Fallo en renderizado de video FFmpeg (Fallback CPU también falló): {e_fallback.stderr[:100]}")
            else:
                raise Exception(f"Fallo en renderizado de video FFmpeg: {e.stderr[:100]}")

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

        if music_path:
            in_cmd_audio.extend(["-i", os.path.abspath(music_path)])
            a_m += f"[{n_x}:a]silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,volume={vol_music_mult:.2f}[m_pre];[m_pre][v_sc]sidechaincompress=threshold=0.04:ratio=6:attack=2:release=150[bg_duck];"
            a_i += "[bg_duck]"; a_c += 1; n_x += 1
        
        for i, m in enumerate(mixed_media):
            is_dict = isinstance(m, dict)
            has_audio = is_dict and m.get("has_audio")
            is_video = (is_dict and m.get("type") == "video") or (not is_dict and os.path.splitext(str(m))[1].lower() in ['.mp4', '.mov', '.avi'])
            
            if has_audio and is_video:
                ach = os.path.abspath(os.path.join(cache_audio, f"audio_mix_{i:03d}.wav"))
                if os.path.exists(ach):
                    in_cmd_audio.extend(["-i", ach])
                    offset_ms = int(transition_offsets[i-1] * 1000) if i > 0 else 0
                    a_m += f"[{n_x}:a]volume={0.7 * vol_sfx_mult:.2f},adelay={offset_ms}|{offset_ms}[a{i}];"
                    a_i += f"[a{i}]"; a_c += 1; n_x += 1

        json_path = os.path.join(temp_dir, "data_mix.json")
        sfx_events = extract_sfx_events(json_path)
        for sfx_path, sfx_start in sfx_events:
            in_cmd_audio.extend(["-i", sfx_path])
            delay_ms = int(sfx_start * 1000)
            a_m += f"[{n_x}:a]volume={0.9 * vol_sfx_mult:.2f},adelay={delay_ms}|{delay_ms}[sfx{n_x}];"
            a_i += f"[sfx{n_x}]"; a_c += 1; n_x += 1

        midpoint_sfx = os.path.abspath(os.path.join(os.getcwd(), "assets", "audio", "transitions", "real_glitch.mp3"))
        if os.path.exists(midpoint_sfx):
            mid_t = total_visual_dur * 0.48
            in_cmd_audio.extend(["-i", midpoint_sfx])
            delay_ms = int(mid_t * 1000)
            a_m += f"[{n_x}:a]volume={1.4 * vol_sfx_mult:.2f},adelay={delay_ms}|{delay_ms}[mid_sfx];"
            a_i += "[mid_sfx]"
            a_c += 1
            n_x += 1

        a_m = a_m.strip(";") + f";{a_i}amix=inputs={a_c}:duration=longest:normalize=0[af]"
        
        cmd_audio_merge = ["ffmpeg", "-y", "-threads", "2"] + in_cmd_audio + ["-filter_complex", a_m, "-map", "0:v", "-map", "[af]", "-c:v", "copy", "-c:a", "aac", "-ac", "2", "-ar", "44100", "-f", "mpegts", "-t", str(total_visual_dur), body_ts]
        try:
            subprocess.run(cmd_audio_merge, check=True, capture_output=True, text=True, errors='replace', **sub_kwargs)
        except subprocess.CalledProcessError as e:
            print(f"--- FFMPEG AUDIO MERGE ERROR LOG ---\n{e.stderr}\n------------------------")
            raise Exception(f"Fallo en mezcla final de audio FFmpeg: {e.stderr[:200]}")

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

        cmd_final = ["ffmpeg", "-y", "-threads", "2", "-i", body_ts, "-c", "copy", v_final]
        try:
            subprocess.run(cmd_final, check=True, capture_output=True, text=True, errors='replace', **sub_kwargs)
        except subprocess.CalledProcessError as e:
            print(f"--- FFMPEG FINAL REMUX ERROR LOG ---\n{e.stderr}\n------------------------")
            raise Exception(f"Fallo en copia final de video FFmpeg: {e.stderr[:200]}")

        # Guardar título y descripción en un archivo .txt complementario
        try:
            txt_final = v_final.rsplit(".", 1)[0] + ".txt"
            with open(txt_final, "w", encoding="utf-8") as f_desc:
                f_desc.write(f"TÍTULO:\n{title}\n\nDESCRIPCIÓN:\n{description}\n")
            print(f"Saved description file to: {txt_final}")
        except Exception as e_desc:
            print(f"Error guardando descripción txt: {e_desc}")


        # Limpieza
        for c in chunk_files: safe_remove(c)
        for i in range(len(mixed_media)): safe_remove(os.path.join(cache_audio, f"audio_mix_{i:03d}.wav"))
        for broll in downloaded_brolls: safe_remove(broll["path"])
        safe_remove(body_ts); safe_remove(body_video_only_ts); safe_remove(temp_srt_mirror)

        # Generar automáticamente doblajes traducidos mezclados con música
        try:
            auto_generate_translated_dubs(
                audio_path=audio_path,
                music_path=music_path,
                vol_voice=vol_voice,
                vol_music=vol_music,
                output_folder=output_folder,
                safe_title=safe_title,
                title=title,
                description=description,
                status_callback=status_callback
            )
        except Exception as e_dubs:
            print(f"Error en auto-generación de doblajes: {e_dubs}")

        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        if status_callback: status_callback(f"🛑 Error Mix: {str(e)[:50]}", "red")
        return False

def auto_generate_translated_dubs(audio_path, music_path, vol_voice, vol_music, output_folder, safe_title, title="", description="", status_callback=None, project_dir=None):
    try:
        if status_callback: status_callback("🎙️ CARGANDO IA DE VOZ PARA TRADUCCIÓN...", "#FFD700")
        
        # 1. Transcribe original audio using Whisper locally (No API quota)
        try:
            import whisper
        except ImportError:
            print("Whisper not installed, skipping auto translation.")
            if status_callback: status_callback("⚠️ NO SE ENCONTRÓ WHISPER LOCAL PARA TRADUCIR", "orange")
            return
            
        # Load the base model (cached locally)
        model = whisper.load_model("base")
        if status_callback: status_callback("🗣️ TRANSCRIBIENDO AUDIO BASE EN ESPAÑOL...", "#FFD700")
        
        result = model.transcribe(audio_path, language="es")
        transcription = result.get("text", "").strip()
        if not transcription:
            print("No transcription found, skipping auto translation.")
            return
            
        # 2. Translate and generate speech for each target language
        # Language -> (Code, Voice)
        languages = {
            "Francés (Francia)": ("fr", "fr-FR-HenriNeural"),
            "Italiano (Italia)": ("it", "it-IT-DiegoNeural"),
            "Alemán (Alemania)": ("de", "de-DE-ConradNeural")
        }
        
        try:
            from deep_translator import GoogleTranslator
            import edge_tts
            import asyncio
        except ImportError:
            print("deep_translator or edge_tts not installed, skipping translation.")
            if status_callback: status_callback("⚠️ FALTAN LIBRERÍAS DE TRADUCCIÓN (deep-translator/edge-tts)", "orange")
            return
            
        # Get original audio duration
        orig_dur = get_video_duration(audio_path)

        # Create output subfolder for translations to avoid cluttering
        if project_dir:
            dubs_folder = os.path.join(project_dir, "dubs")
        else:
            dubs_folder = os.path.join(os.getcwd(), "projects", safe_title)
        os.makedirs(dubs_folder, exist_ok=True)
        
        for lang_name, (lang_code, voice) in languages.items():
            if status_callback: status_callback(f"🌐 TRADUCIENDO AUDIO A {lang_name.upper()}...", "#FFD700")
            try:
                # Translate
                translated_text = GoogleTranslator(source='es', target=lang_code).translate(transcription)
                
                # Synthesize text to temporary wav file using Edge-TTS
                temp_translated_wav = os.path.join(dubs_folder, f"temp_voice_{lang_code}.wav")
                
                # Edge-TTS is async, run it in a sync context
                async def run_edge():
                    communicate = edge_tts.Communicate(translated_text, voice)
                    await communicate.save(temp_translated_wav)
                
                # Run async function
                asyncio.run(run_edge())
                
                # Speed adjust synthesized voice to match original duration exactly
                trans_dur = get_video_duration(temp_translated_wav)
                if orig_dur > 0 and trans_dur > 0:
                    tempo = trans_dur / orig_dur
                    tempo = max(0.5, min(2.0, tempo))  # Clamp to FFmpeg limits
                    
                    stretched_wav = os.path.join(dubs_folder, f"stretched_voice_{lang_code}.wav")
                    cmd_stretch = [
                        "ffmpeg", "-y", "-threads", "2",
                        "-i", temp_translated_wav,
                        "-filter_complex", f"[0:a]atempo={tempo:.4f}[a]",
                        "-map", "[a]", "-ac", "2", "-ar", "44100", stretched_wav
                    ]
                    sub_kwargs = {}
                    if os.name == 'nt':
                        sub_kwargs['creationflags'] = 0x00000040
                        
                    try:
                        subprocess.run(cmd_stretch, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                        if os.path.exists(stretched_wav):
                            if os.path.exists(temp_translated_wav):
                                try: os.remove(temp_translated_wav)
                                except: pass
                            os.rename(stretched_wav, temp_translated_wav)
                    except Exception as se:
                        print(f"Error stretching voice: {se}")
                
                # Translate title and description to target language
                try:
                    translated_title = ""
                    translated_desc = ""
                    if title:
                        translated_title = GoogleTranslator(source='es', target=lang_code).translate(title)
                    if description:
                        translated_desc = GoogleTranslator(source='es', target=lang_code).translate(description)
                    
                    if translated_title or translated_desc:
                        meta_txt_path = os.path.join(dubs_folder, f"{safe_title}_{lang_code}.txt")
                        with open(meta_txt_path, "w", encoding="utf-8") as f_meta:
                            f_meta.write(f"TÍTULO:\n{translated_title}\n\nDESCRIPCIÓN:\n{translated_desc}")
                        print(f"Saved translated metadata to: {meta_txt_path}")
                except Exception as t_err:
                    print(f"Error translating/saving metadata for {lang_code}: {t_err}")

                # 3. Mix with background music (if provided)
                output_dub_path = os.path.join(dubs_folder, f"{safe_title}_{lang_code}.wav")
                
                if music_path and os.path.exists(music_path):
                    if status_callback: status_callback(f"🎛️ MEZCLANDO MÚSICA PARA {lang_name.upper()}...", "#FFD700")
                    # Calculate volume multipliers
                    vol_voice_mult = vol_voice / 100.0
                    vol_music_mult = 0.4 * (vol_music / 100.0) # Apply the same 0.4 factor as render_mix
                    
                    # Construct FFmpeg command to mix voice + music and save as wav
                    # We loop the music to cover the voice length and fade out at the end of the voice track
                    # We use inputs=2:duration=first to automatically cut the mixed file when the voice ends!
                    cmd_mix = [
                        "ffmpeg", "-y", "-threads", "2",
                        "-i", temp_translated_wav,
                        "-stream_loop", "-1", "-i", os.path.abspath(music_path),
                        "-filter_complex", f"[0:a]volume={vol_voice_mult:.2f}[v];[1:a]silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,volume={vol_music_mult:.2f}[m];[v][m]amix=inputs=2:duration=first:normalize=0[a]",
                        "-map", "[a]", "-ac", "2", "-ar", "44100", output_dub_path
                    ]
                    
                    sub_kwargs = {}
                    if os.name == 'nt':
                        sub_kwargs['creationflags'] = 0x00000040
                        
                    subprocess.run(cmd_mix, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
                    # Remove temp voice file
                    if os.path.exists(temp_translated_wav):
                        try: os.remove(temp_translated_wav)
                        except: pass
                else:
                    if music_path:
                        print(f"Music file not found or path empty: {music_path}")
                        if status_callback: status_callback(f"⚠️ MÚSICA NO ENCONTRADA: {os.path.basename(music_path)}", "orange")
                    # No music, just rename the temp file to the final output name
                    if os.path.exists(output_dub_path):
                        try: os.remove(output_dub_path)
                        except: pass
                    os.rename(temp_translated_wav, output_dub_path)
                    
                print(f"Generated auto dub for {lang_code}: {output_dub_path}")
            except Exception as le:
                print(f"Error generating dub for {lang_code}: {le}")
                
        if status_callback: status_callback("✅ RENDER Y DOBLAJES COMPLETADOS CON ÉXITO", "#00FF66")
    except Exception as e:
        print(f"Error in auto_generate_translated_dubs: {e}")
