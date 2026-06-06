import os
import random
import subprocess
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from modules.render_utils import (
    detect_hardware_encoder, 
    safe_remove, 
    get_video_duration,
    transcribe_with_groq
)

_WHISPER_MODEL = None

def convert_to_phrase_ass(json_path, ass_path, aspect_ratio="16:9", time_shift=0.0):
    """
    Toma la transcripción de Whisper del audio del capítulo y agrupa las palabras en
    frases coherentes (de 3 a 6 palabras) basándose en las pausas de tiempo y puntuaciones.
    Genera un archivo .ass con tipografía legible y fade in/out suave.
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        all_words = []
        for segment in data.get("segments", []):
            words_data = segment.get("words", [])
            if words_data:
                for w in words_data:
                    all_words.append({
                        "word": w["word"],
                        "start": w["start"],
                        "end": w["end"]
                    })
            else:
                text = segment.get("text", "").strip()
                if not text:
                    continue
                words = text.split()
                seg_start = segment.get("start", 0.0)
                seg_end = segment.get("end", 0.0)
                dur_per_word = (seg_end - seg_start) / max(1, len(words))
                for i, w in enumerate(words):
                    all_words.append({
                        "word": w,
                        "start": seg_start + (i * dur_per_word),
                        "end": seg_start + ((i + 1) * dur_per_word)
                    })
                    
        # Agrupar en frases de 3 a 6 palabras
        phrases = []
        current_phrase = []
        
        for i, w in enumerate(all_words):
            current_phrase.append(w)
            
            should_split = False
            if len(current_phrase) >= 5:  # Límite ideal de 5 palabras para lectura fluida
                should_split = True
            elif i < len(all_words) - 1:
                next_w = all_words[i+1]
                gap = next_w["start"] - w["end"]
                if gap > 0.35:  # Pausa significativa
                    should_split = True
            
            # Comprobar puntuación fuerte
            clean_word = w["word"].strip()
            if clean_word and clean_word[-1] in [".", "?", "!", ";", ","]:
                should_split = True
                
            if should_split or i == len(all_words) - 1:
                p_text = " ".join([word_item["word"].strip() for word_item in current_phrase])
                p_start = current_phrase[0]["start"]
                p_end = current_phrase[-1]["end"]
                
                # Evitar palabras huérfanas al final acoplándolas a la frase anterior si es posible
                if len(phrases) > 0 and len(current_phrase) == 1 and (p_end - p_start) < 0.4:
                    prev_words = phrases[-1]["text"].split()
                    if len(prev_words) < 6:
                        phrases[-1]["text"] += " " + p_text
                        phrases[-1]["end"] = p_end
                        if "words" in phrases[-1]:
                            phrases[-1]["words"].extend(current_phrase)
                        current_phrase = []
                        continue
                
                phrases.append({
                    "text": p_text,
                    "start": p_start,
                    "end": p_end,
                    "words": list(current_phrase)
                })
                current_phrase = []

        # Formato de tiempo ASS helper
        def format_timestamp(seconds):
            hs = int(seconds // 3600)
            ms = int((seconds % 3600) // 60)
            ss = int(seconds % 60)
            cs = int((seconds - int(seconds)) * 100)
            return f"{hs}:{ms:02}:{ss:02}.{cs:02}"

        # Configuración de resolución y estilo (Alineado al Centro de la Pantalla)
        if aspect_ratio == "16:9":
            play_res_x, play_res_y = 1920, 1080
            font_size = 68
        else:
            play_res_x, play_res_y = 1080, 1920
            font_size = 90

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {play_res_x}\nPlayResY: {play_res_y}\n\n")
            f.write("[V4+ Styles]\n")
            f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            # Estilo Impactante: Arial Black, blanco, borde negro grueso (4px), alineado al centro medio (5) para alta retención
            f.write(f"Style: LongForm,Arial Black,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,5,50,50,0,1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            
            # Palabras clave de terror para mostrar el subtítulo siempre y pintar en rojo sangre
            horror_keywords = [
                "terror", "miedo", "sangre", "muerte", "sombra", "oscuridad", 
                "grito", "espejo", "dolor", "fantasma", "rostro", "monstruo",
                "silencio", "detrás", "atrás", "peligro", "morir", "asesino",
                "cuerpo", "cadáver", "tumba", "cementerio", "alma", "espíritu",
                "sangriento", "oscura", "gritos", "fantasmas", "monstruos",
                "silencioso", "peligroso", "muerto", "muerta", "muertos"
            ]
            
            last_shown_idx = -5
            
            for idx_p, p in enumerate(phrases):
                phrase_text = p["text"].lower()
                is_viral = any(kw in phrase_text for kw in horror_keywords)
                
                # Decidir si mostrar el subtítulo:
                # 1. Contiene palabra de suspenso/terror -> Mostrar siempre
                # 2. Heurística intermitente (gaps de 3-4 frases y 35% de probabilidad)
                should_show = False
                if is_viral:
                    should_show = True
                elif (idx_p - last_shown_idx) >= 3 and random.random() < 0.35:
                    should_show = True
                elif (idx_p - last_shown_idx) >= 5: # Forzar máximo cada 5 para que no pase demasiado tiempo
                    should_show = True
                    
                if should_show:
                    last_shown_idx = idx_p
                    
                    # Asegurar que existan palabras en la frase (si es de fallback)
                    if "words" not in p or not p["words"]:
                        words_list = p["text"].split()
                        dur_per_word = (p["end"] - p["start"]) / max(1, len(words_list))
                        p["words"] = []
                        for w_idx, w_str in enumerate(words_list):
                            p["words"].append({
                                "word": w_str,
                                "start": p["start"] + (w_idx * dur_per_word),
                                "end": p["start"] + ((w_idx + 1) * dur_per_word)
                            })
                    
                    # Escribir palabra por palabra con animación pop y rotación alternada (estilo TikTok)
                    for w_idx, w_item in enumerate(p["words"]):
                        w_text = w_item["word"].strip().replace('"', '')
                        w_clean = "".join([c for c in w_text if c.isalnum()]).lower()
                        
                        # Si es palabra de terror, colorear en rojo sangre, si no blanco
                        if w_clean in horror_keywords:
                            w_formatted = f"{{\\c&H0000FF&}}{w_text}{{\\c&HFFFFFF&}}"
                        else:
                            w_formatted = w_text
                            
                        # Alternar rotaciones (\frz3 y \frz-3) y efecto pop/escala para estilo TikTok
                        tilt = 3 if w_idx % 2 == 0 else -3
                        effect = f"{{\\frz{tilt}\\fscx80\\fscy80\\t(0,80,0.5,\\fscx100\\fscy100)}}"
                        
                        start_w = format_timestamp(w_item["start"] + time_shift)
                        end_w = format_timestamp(w_item["end"] + time_shift)
                        
                        f.write(f"Dialogue: 0,{start_w},{end_w},LongForm,,0,0,0,,{effect}{w_formatted}\n")
                
        return phrases
    except Exception as e:
        print(f"Error generando ASS de frases: {e}")
        traceback.print_exc()
        return []

def render_chapter(chapter_index, chapter_data, output_mp4, enc_params, sub_kwargs, status_callback=None, groq_key=None, aspect_ratio="16:9", project_name="TempProject", lut_name=None):
    """
    Renderiza un único capítulo. Toma el guion de texto, el audio de voz, las imágenes/videos asignadas y
    genera los subtítulos.
    - Alinea los cortes visuales a los tiempos de las frases de forma automática.
    - Aplica Ken Burns dinámico sutil (zoom y paneo) en alta resolución y comprime con prioridad IDLE.
    """
    safe_title = "".join([c for c in project_name if c.isalnum() or c==' ']).rstrip().replace(" ", "_") or "Video_Largo_Render"
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
    

    voice_audio = chapter_data.get("voice_audio", "")
    media_paths = chapter_data.get("media", [])
    guion = chapter_data.get("guion", "")
    title = chapter_data.get("title", "").strip()
    has_title_card = (chapter_index > 0) and (len(title) > 0)

    if not voice_audio or not os.path.exists(voice_audio):
        if status_callback:
            status_callback(f"⚠️ Cap {chapter_index+1}: Falta archivo de audio de voz. Omitiendo render.", "orange")
        return False

    audio_dur = get_video_duration(voice_audio)
    if audio_dur <= 0:
        audio_dur = 5.0 # Fallback básico

    # Pausa de silencio entre capítulos (en segundos) para el intermedio dramático
    pause_dur = 2.0

    # Transcripción del audio del capítulo
    json_path = os.path.join(cache_json, f"cap_{chapter_index}_whisper.json")
    ass_path = os.path.join(cache_ass, f"cap_{chapter_index}_subs.ass")
    whisper_cache_file = os.path.join(cache_json, f"cap_{chapter_index}_whisper_cache.json")
    
    use_cache = False
    voice_mtime = os.path.getmtime(voice_audio) if os.path.exists(voice_audio) else 0
    voice_size = os.path.getsize(voice_audio) if os.path.exists(voice_audio) else 0
    
    if os.path.exists(whisper_cache_file) and os.path.exists(json_path) and os.path.exists(ass_path) and os.path.getsize(ass_path) > 0:
        try:
            with open(whisper_cache_file, "r") as f:
                cache_data = json.load(f)
            if (cache_data.get("original_audio_path") == os.path.abspath(voice_audio) and
                cache_data.get("original_mtime") == voice_mtime and
                cache_data.get("original_size") == voice_size):
                use_cache = True
        except Exception as e:
            print(f"Error leyendo caché de whisper de capítulo: {e}")

    phrases = []
    if use_cache:
        if status_callback:
            status_callback(f"♻️ Cap {chapter_index+1}: Usando transcripción en caché.", "#00E676")
        try:
            phrases = convert_to_phrase_ass(json_path, ass_path, aspect_ratio=aspect_ratio, time_shift=7.0 if has_title_card else 0.0)
        except Exception as e:
            print(f"Error cargando transcripción desde caché: {e}")
            use_cache = False

    if not use_cache:
        if status_callback:
            status_callback(f"🎙️ Cap {chapter_index+1}: Transcribiendo audio de voz...", "#FFD700")

        try:
            if groq_key:
                result = transcribe_with_groq(voice_audio, groq_key, language="es")
            else:
                global _WHISPER_MODEL
                import whisper
                if _WHISPER_MODEL is None:
                    _WHISPER_MODEL = whisper.load_model("tiny")
                result = _WHISPER_MODEL.transcribe(voice_audio, word_timestamps=True, language="es")
            
            if result:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f)
                phrases = convert_to_phrase_ass(json_path, ass_path, aspect_ratio=aspect_ratio, time_shift=7.0 if has_title_card else 0.0)
                
                # Guardar info de caché
                with open(whisper_cache_file, "w") as f:
                    json.dump({
                        "original_audio_path": os.path.abspath(voice_audio),
                        "original_mtime": voice_mtime,
                        "original_size": voice_size
                    }, f)
        except Exception as w_err:
            print(f"Error transcribiendo capítulo {chapter_index}: {w_err}")
            if status_callback:
                status_callback(f"⚠️ Cap {chapter_index+1}: Fallo transcripción ({str(w_err)[:20]}). Usando fallback sin subs.", "orange")
            
    # Si no hay frases de whisper o falló, armamos frases ficticias equitativas basadas en el guion o cantidad de imágenes
    if not phrases:
        lines = [line.strip() for line in guion.split("\n") if line.strip()]
        if not lines:
            lines = ["Presentando este fragmento..."]
        
        chunk_dur = audio_dur / len(lines)
        phrases = []
        for idx, line in enumerate(lines):
            phrases.append({
                "text": line,
                "start": idx * chunk_dur,
                "end": (idx + 1) * chunk_dur
            })

    # Si no hay recursos asignados, usamos un fallback de color negro
    if not media_paths:
        media_paths = ["color_black"]
    num_clips = len(media_paths)

    # --- CONSTRUCCIÓN DEL COMANDO FFMEG ---
    if status_callback:
        status_callback(f"🎬 Cap {chapter_index+1}: Renderizando clip con Ken Burns...", "#FF9100")

    cmd = ["ffmpeg", "-y", "-threads", "2"]
    # Input 0: El audio de la voz
    cmd.extend(["-i", voice_audio])

    # Resoluciones
    if aspect_ratio == "16:9":
        target_w, target_h = 1920, 1080
        scale_w, scale_h = 2200, 1238
        dar_str = "16/9"
    else:
        target_w, target_h = 1080, 1920
        scale_w, scale_h = 1238, 2200
        dar_str = "9/16"

    filter_clauses = []

    if has_title_card:
        # Input 1: Title card video source
        cmd.extend(["-f", "lavfi", "-t", "7.0", "-i", f"color=c=black:s={target_w}x{target_h}:r=30"])
        # Input 2: Title card noise source (estática)
        cmd.extend(["-f", "lavfi", "-t", "7.0", "-i", "anoisesrc=d=7.0:c=pink:r=44100:a=0.08"])
        # Input 3: Title card sine source (hum tétrico)
        cmd.extend(["-f", "lavfi", "-t", "7.0", "-i", "sine=f=55:d=7.0"])
        
        # Procesar audio de la pantalla de título (fade in de 2.0s y fade out de 2.5s al final de los 7s)
        filter_clauses.append("[2:a][3:a]amix=inputs=2:normalize=0,afade=t=in:st=0:d=2.0,afade=t=out:st=4.5:d=2.5[a_title_scary]")
        
        # Procesar video de la pantalla de título (letras rojas, estática)
        escaped_title = title.upper().replace(":", "\\:").replace("'", "'\\''").replace(",", "\\,")
        char_limit = 12 if aspect_ratio != "16:9" else 20
        font_size = 55 if len(title) > char_limit else 75
        filter_clauses.append(f"[1:v]noise=alls=18:allf=t,drawtext=fontfile='arial':text='{escaped_title}':fontcolor=red:fontsize={font_size}:x=(w-text_w)/2:y=(h-text_h)/2,format=yuv420p,fps=30,setsar=1/1,setdar={dar_str}[v_title_card]")

    base_input_idx = 4 if has_title_card else 1
    
    # Calcular duraciones distribuidas uniformemente para cada recurso
    chapter_visual_dur = audio_dur + pause_dur
    clip_durations = []
    for idx in range(num_clips):
        if idx == num_clips - 1:
            clip_dur = max(0.1, chapter_visual_dur - sum(clip_durations))
        else:
            clip_dur = max(0.1, chapter_visual_dur / num_clips)
        clip_durations.append(clip_dur)

    # Añadir los inputs de imágenes/videos para cada recurso multimedia
    for idx, media_path in enumerate(media_paths):
        d_i = clip_durations[idx]
        
        if media_path == "color_black":
            # Input de color negro por lavfi
            cmd.extend(["-f", "lavfi", "-t", f"{d_i:.3f}", "-i", f"color=c=black:s={target_w}x{target_h}:r=30"])
            # El filtro para color negro solo necesita formato y etiqueta
            input_idx = idx + base_input_idx
            filter_clauses.append(f"[{input_idx}:v]format=yuv420p,fps=30,setsar=1/1,setdar={dar_str}[v{idx}]")
        else:
            ext = os.path.splitext(media_path)[1].lower()
            is_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']
            
            if is_video:
                cmd.extend(["-stream_loop", "-1", "-ss", "0", "-t", f"{d_i:.3f}", "-i", media_path])
            else:
                cmd.extend(["-loop", "1", "-t", f"{d_i:.3f}", "-i", media_path])
                
            input_idx = idx + base_input_idx
            
            # Alternar movimientos Ken Burns usando índice del clip para dinamismo
            mov_type = idx % 6
            if mov_type == 0:
                # Pan Derecha
                x_expr = f"(iw-ow)*(0.1+0.8*(t/{d_i:.3f}))"
                y_expr = f"(ih-oh)*0.5"
            elif mov_type == 1:
                # Pan Izquierda
                x_expr = f"(iw-ow)*(0.9-0.8*(t/{d_i:.3f}))"
                y_expr = f"(ih-oh)*0.5"
            elif mov_type == 2:
                # Tilt Arriba
                x_expr = f"(iw-ow)*0.5"
                y_expr = f"(ih-oh)*(0.9-0.8*(t/{d_i:.3f}))"
            elif mov_type == 3:
                # Tilt Abajo
                x_expr = f"(iw-ow)*0.5"
                y_expr = f"(ih-oh)*(0.1+0.8*(t/{d_i:.3f}))"
            elif mov_type == 4:
                # Diagonal Arriba-Derecha
                x_expr = f"(iw-ow)*(0.1+0.8*(t/{d_i:.3f}))"
                y_expr = f"(ih-oh)*(0.9-0.8*(t/{d_i:.3f}))"
            else:
                # Diagonal Abajo-Izquierda
                x_expr = f"(iw-ow)*(0.9-0.8*(t/{d_i:.3f}))"
                y_expr = f"(ih-oh)*(0.1+0.8*(t/{d_i:.3f}))"
 
            clause = (
                f"[{input_idx}:v]scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,crop={scale_w}:{scale_h},"
                f"crop=w={target_w}:h={target_h}:x='{x_expr}':y='{y_expr}',"
                f"format=yuv420p,fps=30,setsar=1/1,setdar={dar_str}{lut_filter}[v{idx}]"
            )
            filter_clauses.append(clause)

    # Concatenar todos los clips de video procesados
    if has_title_card:
        concat_inputs = "[v_title_card]" + "".join([f"[v{i}]" for i in range(num_clips)])
        concat_clause = f"{concat_inputs}concat=n={num_clips+1}:v=1:a=0[v_cat]"
    else:
        if num_clips == 1:
            concat_clause = "[v0]null[v_cat]"
        else:
            concat_inputs = "".join([f"[v{i}]" for i in range(num_clips)])
            concat_clause = f"{concat_inputs}concat=n={num_clips}:v=1:a=0[v_cat]"
    filter_clauses.append(concat_clause)

    # Subtitulado final
    v_output = "v_cat"
    if os.path.exists(ass_path) and phrases:
        abs_ass = os.path.abspath(ass_path).replace('\\', '/').replace(':', '\\:')
        filter_clauses.append(f"[v_cat]subtitles=filename='{abs_ass}'[v_sub]")
        v_output = "v_sub"

    # Pausa dramática intermedia: Fade in al inicio y Fade out a negro al final
    total_dur = (7.0 if has_title_card else 0.0) + audio_dur + pause_dur
    fade_out_start = max(0.0, total_dur - 1.5)
    fade_out_dur = min(1.2, total_dur - fade_out_start)
    filter_clauses.append(f"[{v_output}]fade=t=in:st=0:d=0.5:color=black,fade=t=out:st={fade_out_start:.3f}:d={fade_out_dur:.3f}:color=black[v_faded]")
    v_output = "v_faded"

    # Pista de audio de voz con el padding de silencio al final de cada capítulo y opcionalmente el título scary
    if has_title_card:
        filter_clauses.append(f"[0:a]apad=pad_dur={pause_dur:.3f}[a_voice_padded]")
        filter_clauses.append("[a_title_scary][a_voice_padded]concat=n=2:v=0:a=1[a_padded]")
    else:
        filter_clauses.append(f"[0:a]apad=pad_dur={pause_dur:.3f}[a_padded]")

    filter_complex_str = ";".join(filter_clauses)
    cmd.extend(["-filter_complex", filter_complex_str])

    # Parámetros del codificador
    cmd.extend([
        "-map", f"[{v_output}]",
        "-map", "[a_padded]"
    ] + enc_params + [
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total_dur:.3f}",
        output_mp4
    ])

    try:
        # Ejecutar FFmpeg con la prioridad IDLE configurada en sub_kwargs
        res = subprocess.run(cmd, check=True, capture_output=True, text=True, errors='replace', **sub_kwargs)
        # Limpieza de temporales del capítulo (se conservan los subs para caché)
        # safe_remove(json_path)
        # safe_remove(ass_path)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFMPEG ERROR CAP {chapter_index}:\n{e.stderr}")
        if status_callback:
            status_callback(f"❌ Error en Cap {chapter_index+1}: {str(e.stderr)[:60]}", "red")
        return False

def render_long_video_project(project_state, output_final_mp4, status_callback=None, groq_key=None, aspect_ratio="16:9", lut_name=None):
    """
    Motor principal para renderizar videos largos en Silencio Rojo Core.
    1. Renderiza los capítulos (chunks) de forma secuencial (max_workers=1) para no ahogar la máquina.
    2. Concatena de forma instantánea sin codificación adicional.
    3. Mezcla el diseño sonoro completo (BGM de capítulos cruzándose en 1.5s + auto-ducking sidechain).
    """
    sub_kwargs = {}
    if os.name == 'nt':
        # IDLE_PRIORITY_CLASS
        sub_kwargs['creationflags'] = 0x00000040

    project_name = project_state.get("project_name", "TempProject")
    safe_title = "".join([c for c in project_name if c.isalnum() or c==' ']).rstrip().replace(" ", "_") or "Video_Largo_Render"

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
    

    try:
        # Obtener codificador
        if status_callback:
            status_callback("⚙️ VERIFICANDO ACELERACIÓN DE HARDWARE...", "#00E5FF")
        enc_params = detect_hardware_encoder(temp_dir)

        chapters = project_state.get("chapters", [])
        if not chapters:
            raise Exception("No hay capítulos en el proyecto de video largo.")

        # Asegurar directorio de chunks del proyecto
        project_name = project_state.get("project_name", "TempProject")
        project_chunks_dir = os.path.join(os.getcwd(), "projects", "videos_largos", project_name, "chunks")
        if not os.path.exists(project_chunks_dir):
            os.makedirs(project_chunks_dir)

        chunk_files = []
        
        # Renderizar capítulos secuencialmente (max_workers = 1 por defecto para dual-cores)
        # Esto previene el estrangulamiento térmico y los bloqueos del sistema.
        for idx, cap_data in enumerate(chapters):
            chunk_output = os.path.join(project_chunks_dir, f"chapter_{idx}.mp4")
            meta_output = os.path.join(project_chunks_dir, f"chapter_{idx}_meta.json")
            
            # Recopilar metadatos actuales del capítulo
            voice_audio = cap_data.get("voice_audio", "")
            media_paths = cap_data.get("media", [])
            guion = cap_data.get("guion", "")
            title = cap_data.get("title", "").strip()
            
            current_meta = {
                "guion": guion,
                "title": title,
                "voice_audio": {
                    "path": voice_audio,
                    "mtime": os.path.getmtime(voice_audio) if os.path.exists(voice_audio) else 0,
                    "size": os.path.getsize(voice_audio) if os.path.exists(voice_audio) else 0
                },
                "media": [
                    {
                        "path": m,
                        "mtime": os.path.getmtime(m) if os.path.exists(m) else 0,
                        "size": os.path.getsize(m) if os.path.exists(m) else 0
                    } for m in media_paths
                ],
                "aspect_ratio": aspect_ratio,
                "cache_version": 8
            }
            
            # Verificar si ya existe el chunk y el usuario quiere reutilizarlo (Caché a nivel de capítulo)
            is_valid_cache = False
            if os.path.exists(chunk_output) and os.path.getsize(chunk_output) > 0 and os.path.exists(meta_output):
                try:
                    with open(meta_output, "r", encoding="utf-8") as f:
                        cached_meta = json.load(f)
                    if cached_meta == current_meta:
                        is_valid_cache = True
                except Exception as e:
                    print(f"Error leyendo metadatos de cache para cap {idx}: {e}")
                
            if is_valid_cache:
                if status_callback:
                    status_callback(f"♻️ Cap {idx+1} de {len(chapters)}: Reutilizando chunk pre-renderizado.", "#00E676")
                chunk_files.append(chunk_output)
            else:
                if status_callback:
                    status_callback(f"🎬 Cap {idx+1} de {len(chapters)}: Renderizando nuevo chunk...", "#FF9100")
                success = render_chapter(
                    chapter_index=idx,
                    chapter_data=cap_data,
                    output_mp4=chunk_output,
                    enc_params=enc_params,
                    sub_kwargs=sub_kwargs,
                    status_callback=status_callback,
                    groq_key=groq_key,
                    aspect_ratio=aspect_ratio,
                    project_name=project_name,
                    lut_name=lut_name
                )
                if not success:
                    raise Exception(f"Fallo al renderizar el capítulo {idx+1}")
                
                # Guardar el metadato del nuevo renderizado
                try:
                    with open(meta_output, "w", encoding="utf-8") as f:
                        json.dump(current_meta, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    print(f"Error guardando metadatos de cache para cap {idx}: {e}")
                    
                chunk_files.append(chunk_output)

        # PASO 2: CONCATENACIÓN INSTANTÁNEA (SOLO VIDEO)
        if status_callback:
            status_callback("🔗 CONCATENANDO CLIPS DE VIDEO (MÉTODO SIN PÉRDIDAS)...", "#FFD700")
            
        concat_txt_path = os.path.join(cache_chunks, "concat_list.txt")
        with open(concat_txt_path, "w", encoding="utf-8") as f:
            for chunk in chunk_files:
                f.write(f"file '{chunk.replace('\\', '/')}'\n")

        temp_concat_video = os.path.join(cache_chunks, "temp_concat_video.mp4")
        safe_remove(temp_concat_video)
        
        # Concatena de forma instantánea copiando streams de video (-an para mezclar audio después)
        cmd_concat = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt_path, "-c:v", "copy", "-an", temp_concat_video]
        subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
        safe_remove(concat_txt_path)

        # PASO 3: DISEÑO SONORO AVANZADO (MEZCLA Y CROSSFADES DE BGM + DUCKING)
        if status_callback:
            status_callback("🎚️ MEZCLANDO AUDIO Y APLICANDO SIDECHAIN COMPRESSION...", "#00E5FF")

        # 3.1 Calcular tiempos y acumulados de capítulos (basándose en la duración real de los chunks, que ya tienen la pausa de 1.5s)
        cap_durations = []
        for idx, cap in enumerate(chapters):
            dur = get_video_duration(chunk_files[idx]) or 5.0
            cap_durations.append(dur)

        total_duration = sum(cap_durations)
        
        # Array de marcas de tiempo de inicio
        t_starts = [0.0]
        for dur in cap_durations[:-1]:
            t_starts.append(t_starts[-1] + dur)

        # Construir comandos y filtros para audio
        # Mapeamos:
        # Inputs 1 a N: Chunks (para extraer su audio de voz ya sincronizado y pausado)
        # Inputs N+1 a 2N: Audios de BGM de cada capítulo (si están activos)
        in_cmd = ["-i", temp_concat_video]
        
        # Audios de voz (desde los chunks)
        for chunk in chunk_files:
            in_cmd.extend(["-i", chunk])
            
        num_caps = len(chapters)
        
        # Audios de música de fondo (BGM)
        music_enabled = project_state.get("music_enabled", True)
        bgm_inputs_added = 0
        bgm_info = [] # (input_index, chapter_index)
        
        if music_enabled:
            for idx, cap in enumerate(chapters):
                bgm_path = cap.get("music_path", "")
                if bgm_path and os.path.exists(bgm_path):
                    # -stream_loop -1 para evitar que la música termine antes que el capítulo
                    in_cmd.extend(["-stream_loop", "-1", "-i", bgm_path])
                    bgm_info.append((1 + num_caps + bgm_inputs_added, idx))
                    bgm_inputs_added += 1
                else:
                    bgm_info.append((None, idx)) # Sin música en este capítulo

        # filter_complex de audio
        audio_filter_clauses = []
        
        # A) Concatenar la pista de narración (voz limpia)
        if num_caps == 1:
            audio_filter_clauses.append("[1:a]anull[voice_clean_temp]")
        else:
            voice_inputs = "".join([f"[{i+1}:a]" for i in range(num_caps)])
            audio_filter_clauses.append(f"{voice_inputs}concat=n={num_caps}:v=0:a=1[voice_clean_temp]")

        if music_enabled and bgm_inputs_added > 0:
            audio_filter_clauses.append("[voice_clean_temp]asplit=2[voice_clean][voice_sidechain]")
        else:
            audio_filter_clauses.append("[voice_clean_temp]anull[voice_clean]")
        
        # B) Mezclar pistas de música aplicando crossfades dinámicos en los bordes
        if music_enabled and bgm_inputs_added > 0:
            bgm_processed_labels = []
            for index, (in_idx, cap_idx) in enumerate(bgm_info):
                if in_idx is None:
                    continue # Omitir capítulos sin música
                
                d_curr = cap_durations[cap_idx]
                t_start = t_starts[cap_idx]
                
                cap_data = chapters[cap_idx]
                title = cap_data.get("title", "").strip()
                has_title_card = (cap_idx > 0) and (len(title) > 0)
                
                music_start_offset = 7.0 if has_title_card else 0.0
                play_start = t_start + music_start_offset
                d_curr_eff = d_curr - music_start_offset
                
                # Para el fade de entrada
                xf_in = 1.5
                fade_in_time = play_start
                
                # Para el fade de salida
                xf_out = 1.5
                fade_out_time = max(play_start, play_start + d_curr_eff - xf_out)
                
                delay_ms = int(play_start * 1000)
                
                bgm_label = f"[bgm_cap_{cap_idx}]"
                filter_str = f"[{in_idx}:a]silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,volume=0.25,adelay={delay_ms}|{delay_ms}"
                
                # Aplicar Fades
                if xf_in > 0:
                    filter_str += f",afade=t=in:st={fade_in_time:.3f}:d={xf_in:.3f}"
                if xf_out > 0:
                    filter_str += f",afade=t=out:st={fade_out_time:.3f}:d={xf_out:.3f}"
                    
                filter_str += bgm_label
                audio_filter_clauses.append(filter_str)
                bgm_processed_labels.append(bgm_label)
                
            # Mezclar todas las pistas de música procesadas
            bgm_mix_inputs = "".join(bgm_processed_labels)
            audio_filter_clauses.append(f"{bgm_mix_inputs}amix=inputs={len(bgm_processed_labels)}:duration=longest:normalize=0[music_mixed]")
            
            # C) Sidechain Compression (Ducking) automático de música con respecto a la voz
            # La música baja un 70% cuando el narrador habla
            audio_filter_clauses.append("[music_mixed][voice_sidechain]sidechaincompress=threshold=0.04:ratio=6:attack=2:release=150[music_ducked]")
            
            # D) Mezcla final de voz limpia + música ducked
            audio_filter_clauses.append("[voice_clean][music_ducked]amix=inputs=2:duration=first:normalize=0[audio_final]")
            
            map_audio = "[audio_final]"
        else:
            # Si no hay música o está desactivada, el audio final es solo la voz concatenada
            map_audio = "[voice_clean]"

        # Fusionar filter complex de audio
        full_audio_filter = ";".join(audio_filter_clauses)
        
        # Determinar si hay cover (Portada)
        cover_path = project_state.get("cover_path", "")
        
        # Salida final con control de sobreescritura
        safe_title = "".join([c for c in project_name if c.isalnum() or c==' ']).rstrip().replace(" ", "_") or "Video_Largo_Render"
        v_final_output = os.path.join(project_state.get("output_folder", os.path.expanduser("~")), f"{safe_title}.mp4")
        
        counter = 1
        base_output = v_final_output
        while True:
            try:
                if os.path.exists(v_final_output):
                    os.remove(v_final_output)
                break
            except:
                v_final_output = base_output.replace(".mp4", f"_({counter}).mp4")
                counter += 1
                if counter > 10:
                    break

        # Ejecutar mezcla de audio final con el video concatenado
        cmd_mix = [
            "ffmpeg", "-y", "-threads", "2"
        ] + in_cmd + [
            "-filter_complex", full_audio_filter,
            "-map", "0:v",
            "-map", map_audio
        ] + enc_params + [
            "-c:a", "aac", "-b:a", "192k",
            "-ac", "2", "-ar", "44100",
            "-t", f"{total_duration:.3f}",
            v_final_output
        ]
        
        if status_callback:
            status_callback("📦 COMPILANDO PIEZA AUDIOVISUAL FINAL...", "#FF9100")
            
        subprocess.run(cmd_mix, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
        
        # Limpieza
        safe_remove(temp_concat_video)
        if status_callback:
            status_callback(f"✅ RENDER COMPLETADO EXITOSAMENTE!", "#00FF66")
            
        return v_final_output

    except Exception as e:
        print("Error en render_long_video_project:")
        traceback.print_exc()
        if status_callback:
            status_callback(f"🛑 Error en Render: {str(e)[:50]}", "red")
        return False
