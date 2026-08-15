import os
import subprocess
import json
import time
from PIL import Image, ImageDraw, ImageFont
from groq import Groq

_DETECTED_ENCODER = None
def calculate_file_hash(file_path: str) -> str:
    """Calculate a deterministic hash based on file path, modification time and size.
    Returns a SHA256 hex string.
    """
    import hashlib, os
    if not os.path.exists(file_path):
        return hashlib.sha256(file_path.encode('utf-8')).hexdigest()
    stat = os.stat(file_path)
    hash_input = f"{file_path}:{stat.st_mtime}:{stat.st_size}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def detect_hardware_encoder(output_folder):
    """
    Detecta el mejor codificador de hardware disponible (QSV o software).
    Retorna una lista de argumentos para FFmpeg.
    """
    global _DETECTED_ENCODER
    if _DETECTED_ENCODER is not None:
        return _DETECTED_ENCODER

    # Buscar caché en disco
    project_root = os.getcwd()
    cache_dir = os.path.join(project_root, "cache")
    cache_file_path = os.path.join(cache_dir, "detected_encoder.json")
    
    if os.path.exists(cache_file_path):
        try:
            with open(cache_file_path, "r", encoding="utf-8") as f:
                cached_params = json.load(f)
            if isinstance(cached_params, list) and len(cached_params) > 0:
                _DETECTED_ENCODER = cached_params
                return cached_params
        except Exception as ce:
            print(f"Error leyendo caché de encoder: {ce}")

    test_file = os.path.join(output_folder, "hw_test.mp4")
    
    options = [
        ("NVENC", ["-c:v", "h264_nvenc", "-preset", "fast", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high"]),
        ("AMF", ["-c:v", "h264_amf", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high"]),
        ("QSV", ["-c:v", "h264_qsv", "-preset", "faster", "-look_ahead", "0", "-b:v", "2200k", "-pix_fmt", "nv12", "-g", "90", "-bf", "3", "-profile:v", "high"]),
        ("MediaFoundation", ["-c:v", "h264_mf", "-rate_control", "quality", "-quality", "85", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90"]),
        ("CPU", ["-c:v", "libx264", "-preset", "ultrafast", "-b:v", "2200k", "-pix_fmt", "yuv420p", "-g", "90", "-bf", "3", "-profile:v", "high"])
    ]

    sub_kwargs = {}
    if os.name == 'nt':
        sub_kwargs['creationflags'] = 0x00000040

    for name, params in options:
        if name == "CPU":
            _DETECTED_ENCODER = params
            break
        # Test encoder using ffmpeg with lavfi color source
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=100x100", "-t", "0.1", "-r", "30"] + params + [test_file]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **sub_kwargs)
            if os.path.exists(test_file):
                os.remove(test_file)
                _DETECTED_ENCODER = params
                print(f"Hardware encoder detected: {name}")
                break
        except Exception:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception:
                    pass

    if _DETECTED_ENCODER is None:
        _DETECTED_ENCODER = options[-1][1] # Fallback to CPU

    # Guardar en caché
    os.makedirs(cache_dir, exist_ok=True)
    try:
        with open(cache_file_path, "w", encoding="utf-8") as f:
            json.dump(_DETECTED_ENCODER, f)
    except Exception as ce:
        print(f"Error escribiendo caché de encoder: {ce}")

    return _DETECTED_ENCODER
def normalize_audio(input_audio_path, cache_dir):
    """Normalize audio loudness using FFmpeg loudnorm filter and cache the result.
    Returns path to normalized audio file.
    """
    import os, subprocess
    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)
    # Use deterministic hash based on file path, mtime and size
    hash_name = calculate_file_hash(input_audio_path)
    output_path = os.path.join(cache_dir, f"norm_{hash_name}.wav")
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return output_path
    cmd = ["ffmpeg", "-y", "-i", input_audio_path, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", output_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except Exception as e:
        print(f"Error normalizing audio {input_audio_path}: {e}")
        return input_audio_path

def convert_to_word_by_word_srt(json_path, srt_path, status_callback=None, aspect_ratio="9:16", sub_style="Reddit History"):
    """
    Convierte el JSON de Whisper a formato ASS (Advanced SubStation Alpha) con estilo Viral Pro
    (TikTok/Hormozi con inclinación y emojis, o Reddit History centrado-inferior sin emojis y con rebote).
    """
    try:
        # Formato de tiempo ASS helper (h:mm:ss.cs)
        def format_timestamp(seconds):
            hs = int(seconds // 3600)
            ms = int((seconds % 3600) // 60)
            ss = int(seconds % 60)
            cs = int((seconds - int(seconds)) * 100)
            return f"{hs}:{ms:02}:{ss:02}.{cs:02}"

        # 1. Cargar transcripción
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. Extraer todas las palabras con sus tiempos
        all_words = []
        for segment in data.get("segments", []):
            words_data = segment.get("words", [])
            if words_data:
                for w in words_data:
                    all_words.append({
                        "word": w["word"].strip(),
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

        if not all_words:
            print("No words found in transcription JSON.")
            return False

        # 3. Palabras clave de terror y misterio para resaltar
        horror_keywords = [
            "terror", "miedo", "sangre", "muerte", "sombra", "oscuridad",
            "grito", "espejo", "dolor", "fantasma", "rostro", "monstruo",
            "silencio", "detrás", "atrás", "peligro", "morir", "asesino",
            "cuerpo", "cadáver", "tumba", "cementerio", "alma", "espíritu",
            "sangriento", "oscura", "gritos", "fantasmas", "monstruos",
            "silencioso", "peligroso", "muerto", "muerta", "muertos"
        ]

        # Cargar estilos personalizados dinámicos
        custom_style_data = None
        styles_path = os.path.join("config", "subtitle_styles.json")
        if os.path.exists(styles_path):
            try:
                with open(styles_path, "r", encoding="utf-8") as f:
                    custom_styles = json.load(f)
                    if sub_style in custom_styles:
                        custom_style_data = custom_styles[sub_style]
            except Exception as e:
                print(f"Error cargando estilos dinámicos en render: {e}")

        if custom_style_data:
            # --- MODO ESTILO PERSONALIZADO ---
            font_name = custom_style_data.get("font_name", "Arial Black")
            font_size = custom_style_data.get("font_size_9_16", 90) if aspect_ratio == "9:16" else custom_style_data.get("font_size_16_9", 68)
            primary_color = custom_style_data.get("primary_color", "&H00FFFFFF")
            outline_color = custom_style_data.get("outline_color", "&H00000000")
            back_color = custom_style_data.get("back_color", "&H80000000")
            bold = custom_style_data.get("bold", -1)
            italic = custom_style_data.get("italic", 0)
            outline = custom_style_data.get("outline", 4)
            shadow = custom_style_data.get("shadow", 0)
            alignment = custom_style_data.get("alignment", 2)
            margin_v = custom_style_data.get("margin_v_9_16", 450) if aspect_ratio == "9:16" else custom_style_data.get("margin_v_16_9", 120)
            animation_type = custom_style_data.get("animation_type", "TikTok")
            text_case = custom_style_data.get("text_case", "uppercase")
            highlight_color = custom_style_data.get("highlight_color", "&H00FFFF00&")
            emojis_enabled = custom_style_data.get("emojis_enabled", True)
            
            # Emojis virales
            viral_emojis = {
                "terror": "😱", "miedo": "😰", "sangre": "🩸", "muerte": "💀", 
                "sombra": "👤", "oscuridad": "🌑", "grito": "😱", "espejo": "🪞",
                "dolor": "😭", "fantasma": "👻", "rostro": "👤", "monstruo": "👹",
                "silencio": "🤫", "atrás": "👀", "detrás": "👀", "peligro": "⚠️",
                "morir": "☠️", "asesino": "🔪", "tumba": "🪦", "cementerio": "🪦",
                "alma": "👻", "espíritu": "👻", "cadáver": "☠️", "cadaver": "☠️",
                "muerto": "💀", "muerta": "💀", "muertos": "💀", "oscura": "🌑", 
                "oscuro": "🌑", "cuerpo": "🧟", "susto": "🙀", "horror": "🧟", 
                "creepy": "👹", "gritos": "😱", "sangriento": "🩸", "peligroso": "⚠️", 
                "casa": "🏠", "noche": "🌃", "bosque": "🌲", "puerta": "🚪", 
                "ventana": "🪟", "reloj": "⏰", "teléfono": "☎️", "telefono": "☎️", 
                "llave": "🔑", "gato": "🐱", "perro": "🐶", "hijo": "👦", 
                "madre": "👩", "padre": "👨", "amigo": "🧑", "escuchar": "👂", 
                "mirar": "👁️", "ver": "👁️", "correr": "🏃", "llamar": "📞", 
                "hablar": "🗣️"
            }

            play_res_x = 1080 if aspect_ratio == "9:16" else 1920
            play_res_y = 1920 if aspect_ratio == "9:16" else 1080

            with open(srt_path, "w", encoding="utf-8") as f_sub:
                f_sub.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {play_res_x}\nPlayResY: {play_res_y}\n\n")
                f_sub.write("[V4+ Styles]\n")
                f_sub.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                f_sub.write(f"Style: CustomStyle,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},{bold},{italic},0,0,100,100,0,0,1,{outline},{shadow},{alignment},50,50,{margin_v},1\n\n")
                
                f_sub.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
                
                for idx, w in enumerate(all_words):
                    start = format_timestamp(w["start"])
                    end = format_timestamp(w["end"])
                    raw_w = w["word"].strip().replace('"', '')
                    
                    if text_case == "uppercase":
                        w_text = raw_w.upper()
                    elif text_case == "lowercase":
                        w_text = raw_w.lower()
                    else:
                        w_text = raw_w
                        
                    clean_w = "".join([c for c in w_text if c.isalnum()]).lower()
                    
                    color_tag = ""
                    emoji = ""
                    
                    if emojis_enabled:
                        for kw, emj in viral_emojis.items():
                            if kw in clean_w:
                                emoji = " " + emj
                                break
                    
                    is_horror = clean_w in horror_keywords
                    if is_horror:
                        color_tag = f"{{\\c{highlight_color}}}"
                    elif animation_type == "TikTok" and idx % 4 == 0:
                        color_tag = f"{{\\c&H00FFFF00&}}"
                        
                    anim_tag = ""
                    if animation_type == "TikTok":
                        tilt = 4 if idx % 2 == 0 else -4
                        anim_tag = f"{{\\frz{tilt}\\fscx80\\fscy80\\t(0,100,0.5,\\fscx100\\fscy100)}}"
                    elif animation_type == "Reddit":
                        anim_tag = r"{\fscx125\fscy125\t(0,150,\fscx100\fscy100)}"
                    elif animation_type == "Roblox":
                        anim_tag = r"{\fscx120\fscy120\t(0,120,\fscx100\fscy100)}"
                        
                    primary_color_restore = f"{{\\c{primary_color}}}"
                    if color_tag:
                        full_text = f"{anim_tag}{color_tag}{w_text}{primary_color_restore}{emoji}"
                    else:
                        full_text = f"{anim_tag}{w_text}{emoji}"
                        
                    f_sub.write(f"Dialogue: 0,{start},{end},CustomStyle,,0,0,0,,{full_text}\n")
                    
            return True

        elif sub_style == "Reddit History":
            # --- MODO REDDIT HISTORY (DOPAMINÉRGICO WORD-BY-WORD DE ALTA RETENCIÓN) ---
            if aspect_ratio == "16:9":
                play_res_x, play_res_y = 1920, 1080
                margin_v = 120
                font_size = 65
            else:
                play_res_x, play_res_y = 1080, 1920
                margin_v = 700  # Centrado-inferior seguro para Shorts
                font_size = 100

            # Colores dopaminérgicos para resaltar (BGR): Amarillo Neón y Verde Neón
            reddit_highlights = {
                "atras": "&H0000FFFF&", "atrás": "&H0000FFFF&",
                "calor": "&H0000FF00&", "mundo": "&H0000FF00&",
                "agua": "&H0000FF00&", "grifo": "&H0000FF00&",
                "dolor": "&H0000FFFF&", "espejo": "&H0000FF00&",
                "rostro": "&H0000FF00&", "mareado": "&H0000FF00&",
                "sed": "&H0000FF00&", "alguien": "&H0000FF00&",
                "rie": "&H0000FFFF&", "ríe": "&H0000FFFF&",
                "oscuridad": "&H0000FFFF&", "sangre": "&H0000FFFF&",
                "muerte": "&H0000FFFF&", "fantasma": "&H0000FF00&",
                "miedo": "&H0000FFFF&", "terror": "&H0000FFFF&",
                "corazon": "&H0000FFFF&", "corazón": "&H0000FFFF&"
            }

            with open(srt_path, "w", encoding="utf-8") as f_sub:
                f_sub.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {play_res_x}\nPlayResY: {play_res_y}\n\n")
                f_sub.write("[V4+ Styles]\n")
                f_sub.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                # Estilo Reddit: Arial Black gigante, blanco con contorno negro ultra-grueso (Outline=10), sombra (Shadow=6)
                f_sub.write(f"Style: Reddit,Arial Black,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,10,6,2,50,50,{margin_v},1\n\n")
                
                f_sub.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
                
                for idx, w in enumerate(all_words):
                    start = format_timestamp(w["start"])
                    end = format_timestamp(w["end"])
                    w_text = w["word"].strip().replace('"', '').upper()
                    
                    clean_w = "".join([c for c in w_text if c.isalnum()]).lower()
                    
                    color_tag = ""
                    if clean_w in reddit_highlights:
                        color_tag = f"{{\\c{reddit_highlights[clean_w]}}}"
                    elif clean_w in horror_keywords:
                        color_tag = f"{{\\c&H0000FF00&}}" # Verde Neón
                        
                    # Animación bounce pop-in: escala de 125% a 100% en 150ms. Sin tilts ni emojis
                    anim_tag = r"{\fscx125\fscy125\t(0,150,\fscx100\fscy100)}"
                    
                    if color_tag:
                        full_text = f"{anim_tag}{color_tag}{w_text}{{\\c&HFFFFFF&}}"
                    else:
                        full_text = f"{anim_tag}{w_text}"
                        
                    f_sub.write(f"Dialogue: 0,{start},{end},Reddit,,0,0,0,,{full_text}\n")
                    
            return True

        elif sub_style == "TikTok / Hormozi":
            # --- MODO TIKTOK / HORMOZI (CON ROTACIONES Y HIGHLIGHTS VIRALES Y EMOJIS) ---
            if aspect_ratio == "16:9":
                play_res_x, play_res_y = 1920, 1080
                margin_v = 120
                font_size = 68
                alignment = 2
            else:
                play_res_x, play_res_y = 1080, 1920
                margin_v = 450
                font_size = 90
                alignment = 2

            # Emojis virales
            viral_emojis = {
                "terror": "😱", "miedo": "😰", "sangre": "🩸", "muerte": "💀", 
                "sombra": "👤", "oscuridad": "🌑", "grito": "😱", "espejo": "🪞",
                "dolor": "😭", "fantasma": "👻", "rostro": "👤", "monstruo": "👹",
                "silencio": "🤫", "atrás": "👀", "detrás": "👀", "peligro": "⚠️",
                "morir": "☠️", "asesino": "🔪", "tumba": "🪦", "cementerio": "🪦",
                "alma": "👻", "espíritu": "👻",
                "cadáver": "☠️", "cadaver": "☠️", "muerto": "💀", "muerta": "💀",
                "muertos": "💀", "oscura": "🌑", "oscuro": "🌑", "cuerpo": "🧟",
                "susto": "🙀", "horror": "🧟", "creepy": "👹", "gritos": "😱",
                "sangriento": "🩸", "peligroso": "⚠️", "casa": "🏠", "noche": "🌃",
                "bosque": "🌲", "puerta": "🚪", "ventana": "🪟", "reloj": "⏰",
                "teléfono": "☎️", "telefono": "☎️", "llave": "🔑", "gato": "🐱",
                "perro": "🐶", "hijo": "👦", "madre": "👩", "padre": "👨",
                "amigo": "🧑", "escuchar": "👂", "mirar": "👁️", "ver": "👁️",
                "correr": "🏃", "llamar": "📞", "hablar": "🗣️"
            }

            with open(srt_path, "w", encoding="utf-8") as f_sub:
                f_sub.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {play_res_x}\nPlayResY: {play_res_y}\n\n")
                f_sub.write("[V4+ Styles]\n")
                f_sub.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                f_sub.write(f"Style: TikTok,Arial Black,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,{alignment},50,50,{margin_v},1\n\n")
                
                f_sub.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
                
                for idx, w in enumerate(all_words):
                    start = format_timestamp(w["start"])
                    end = format_timestamp(w["end"])
                    w_text = w["word"].strip().replace('"', '').upper()
                    
                    clean_w = "".join([c for c in w_text if c.isalnum()]).lower()
                    
                    color_tag = ""
                    emoji = ""
                    
                    # Buscar si hay un emoji correspondiente para esta palabra
                    for kw, emj in viral_emojis.items():
                        if kw in clean_w:
                            emoji = " " + emj
                            break

                    if clean_w in horror_keywords:
                        color_tag = f"{{\\c&H003300FF&}}" # Rojo brillante (#FF0033)
                    elif idx % 4 == 0:
                        color_tag = f"{{\\c&H00FFFF00&}}" # Cian
                        
                    # Rotación alternada y pop-in
                    tilt = 4 if idx % 2 == 0 else -4
                    effect = f"{{\\frz{tilt}\\fscx80\\fscy80\\t(0,100,0.5,\\fscx100\\fscy100)}}"
                    
                    if color_tag:
                        full_text = f"{effect}{color_tag}{w_text}{{\\c&HFFFFFF&}}{emoji}"
                    else:
                        full_text = f"{effect}{w_text}{emoji}"
                        
                    f_sub.write(f"Dialogue: 0,{start},{end},TikTok,,0,0,0,,{full_text}\n")
                    
            return True

        elif sub_style == "Roblox Gaming":
            # --- MODO ROBLOX GAMING: Estilo gaming limpio, sin parpadeo, con pop-in suave ---
            if aspect_ratio == "16:9":
                play_res_x, play_res_y = 1920, 1080
                margin_v = 120
                font_size = 75
                alignment = 2
            else:
                play_res_x, play_res_y = 1080, 1920
                margin_v = 450
                font_size = 95
                alignment = 2

            # Palabras clave gaming-Roblox para resaltar en naranja neón (BGR: &H0040FFFF es naranja)
            roblox_highlights = {
                # Terror / misterio (cian neón)
                "terror": "&H00FFFF00&", "miedo": "&H00FFFF00&", "sangre": "&H00FFFF00&",
                "muerte": "&H00FFFF00&", "muerto": "&H00FFFF00&", "muerta": "&H00FFFF00&",
                "fantasma": "&H00FFFF00&", "asesino": "&H00FFFF00&", "peligro": "&H00FFFF00&",
                "sombra": "&H00FFFF00&", "oscuridad": "&H00FFFF00&", "silencio": "&H00FFFF00&",
                # Impacto positivo / acción (naranja neón)
                "nunca": "&H0040C8FF&", "jamás": "&H0040C8FF&", "nadie": "&H0040C8FF&",
                "todo": "&H0040C8FF&", "todos": "&H0040C8FF&", "siempre": "&H0040C8FF&",
                "gratis": "&H0040C8FF&", "secreto": "&H0040C8FF&", "viral": "&H0040C8FF&",
                "increíble": "&H0040C8FF&", "increible": "&H0040C8FF&", "imposible": "&H0040C8FF&"
            }

            with open(srt_path, "w", encoding="utf-8") as f_sub:
                f_sub.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {play_res_x}\nPlayResY: {play_res_y}\n\n")
                f_sub.write("[V4+ Styles]\n")
                f_sub.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                # Roblox Gaming: Arial Black bold, blanco, contorno negro grueso (Outline=8), sombra leve (Shadow=4)
                # BackColour semitransparente negro para mayor legibilidad gaming
                f_sub.write(f"Style: Roblox,Arial Black,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,105,2,0,1,8,4,{alignment},50,50,{margin_v},1\n\n")
                
                f_sub.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
                
                for idx, w in enumerate(all_words):
                    start = format_timestamp(w["start"])
                    end = format_timestamp(w["end"])
                    w_text = w["word"].strip().replace('"', '').upper()
                    
                    clean_w = "".join([c for c in w_text if c.isalnum()]).lower()
                    
                    color_tag = ""
                    if clean_w in roblox_highlights:
                        color_tag = f"{{\\c{roblox_highlights[clean_w]}}}"
                    elif clean_w in horror_keywords:
                        color_tag = f"{{\\c&H00FFFF00&}}"  # Cian neón para terror
                    
                    # Gaming pop-in: Scale 120% → 100% en 120ms, sin rotación, limpio
                    anim_tag = r"{\fscx120\fscy120\t(0,120,\fscx100\fscy100)}"
                    
                    if color_tag:
                        full_text = f"{anim_tag}{color_tag}{w_text}{{\\c&HFFFFFF&}}"
                    else:
                        full_text = f"{anim_tag}{w_text}"
                        
                    f_sub.write(f"Dialogue: 0,{start},{end},Roblox,,0,0,0,,{full_text}\n")
                    
            return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        if status_callback:
            status_callback(f"🛑 Error Subtítulos: {str(e)[:50]}", "red")
        return False


def safe_remove(file_path):
    """
    Intenta eliminar un archivo de forma segura con reintentos para manejar bloqueos en Windows.
    """
    if not file_path:
        return
    import os
    import time
    file_path = os.path.abspath(file_path)
    for _ in range(5):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            break
        except Exception:
            time.sleep(0.1)


def get_video_duration(file_path):
    """
    Obtiene la duración de un archivo multimedia mediante ffprobe.
    """
    import subprocess
    import json
    import os
    
    if not os.path.exists(file_path):
        return 0.0
        
    cmd = [
        "ffprobe", "-v", "quiet", 
        "-print_format", "json", 
        "-show_format", "-show_streams", 
        file_path
    ]
    sub_kwargs = {}
    if os.name == 'nt':
        sub_kwargs['creationflags'] = 0x00000040
        
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True, errors='replace', **sub_kwargs)
        data = json.loads(res.stdout)
        duration = float(data.get("format", {}).get("duration", 0.0))
        if duration > 0:
            return duration
        # Fallback a los flujos
        for stream in data.get("streams", []):
            dur = float(stream.get("duration", 0.0))
            if dur > 0:
                return dur
    except Exception as e:
        print(f"Error obteniendo duración ffprobe para {file_path}: {e}")
        
    return 0.0


def transcribe_with_groq(audio_path, api_key, language="es"):
    """
    Transcribe audio usando la API de Groq Whisper y retorna verbose_json con palabras.
    """
    import os
    from groq import Groq
    
    if not os.path.exists(audio_path):
        return None
        
    try:
        client = Groq(api_key=api_key)
        with open(audio_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), file),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=language
            )
        if hasattr(transcription, "model_dump"):
            return transcription.model_dump()
        elif hasattr(transcription, "dict"):
            return transcription.dict()
        else:
            return dict(transcription)
    except Exception as e:
        print(f"Error transcribiendo con Groq: {e}")
        return None


def extract_sfx_events(json_path):
    """
    Escanea la transcripción para asociar palabras de suspenso con efectos de sonido (SFX).
    """
    import json
    import os
    
    events = []
    if not os.path.exists(json_path):
        return events
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error cargando JSON para extraer SFX: {e}")
        return events
        
    sfx_dir = os.path.abspath(os.path.join("assets", "audio", "sfx"))
    sfx_map = {
        "pasos": os.path.join(sfx_dir, "footsteps.wav"),
        "caminar": os.path.join(sfx_dir, "footsteps.wav"),
        "corazón": os.path.join(sfx_dir, "heartbeat.wav"),
        "corazon": os.path.join(sfx_dir, "heartbeat.wav"),
        "latido": os.path.join(sfx_dir, "heartbeat.wav"),
        "lluvia": os.path.join(sfx_dir, "rain_and_thunder_storm.wav"),
        "tormenta": os.path.join(sfx_dir, "rain_and_thunder_storm.wav"),
        "trueno": os.path.join(sfx_dir, "rain_and_thunder_storm.wav"),
        "perro": os.path.join(sfx_dir, "dog_bark.wav"),
        "ladrar": os.path.join(sfx_dir, "dog_bark.wav"),
        "ladrido": os.path.join(sfx_dir, "dog_bark.wav"),
        "perdiste": os.path.join(sfx_dir, "arcade_retro_game_over.wav"),
        "retro": os.path.join(sfx_dir, "arcade_retro_game_over.wav"),
        "notificación": os.path.join(sfx_dir, "retro_game_notification.wav"),
        "notificacion": os.path.join(sfx_dir, "retro_game_notification.wav"),
        "grillo": os.path.join(sfx_dir, "crickets_ambience.wav"),
        "grillos": os.path.join(sfx_dir, "crickets_ambience.wav"),
        "vacío": os.path.join(sfx_dir, "air_zoom_vacuum.wav"),
        "vacio": os.path.join(sfx_dir, "air_zoom_vacuum.wav")
    }
    
    # Clasificación de tipos (Pilar 1)
    sfx_types = {
        "footsteps.wav": "ambient",
        "heartbeat.wav": "impact",
        "rain_and_thunder_storm.wav": "ambient",
        "dog_bark.wav": "impact",
        "arcade_retro_game_over.wav": "impact",
        "retro_game_notification.wav": "impact",
        "crickets_ambience.wav": "ambient",
        "air_zoom_vacuum.wav": "impact"
    }

    last_impact_time = -999.0

    for segment in data.get("segments", []):
        text = segment.get("text", "").lower()
        seg_start = segment.get("start", 0.0)
        seg_end = segment.get("end", 0.0)
        seg_dur = seg_end - seg_start
        
        # Pilar 2: Timestamps por palabra (Word-Level)
        words = segment.get("words", [])
        
        for kw, sfx_path in sfx_map.items():
            if kw in text and os.path.exists(sfx_path):
                filename = os.path.basename(sfx_path)
                sfx_type = sfx_types.get(filename, "impact")
                
                # Encontrar tiempo de inyección óptimo
                sfx_start = seg_start
                if words:
                    # Buscar la palabra específica que contiene la palabra clave
                    for w in words:
                        w_text = w.get("word", "").lower().strip(".,?!;:-_\"'")
                        if kw in w_text:
                            sfx_start = w.get("start", seg_start)
                            break
                else:
                    # Fallback proporcional si no hay marcas por palabra
                    clean_words = text.split()
                    for idx_w, w in enumerate(clean_words):
                        if kw in w.strip(".,?!;:-_\"'"):
                            fraction = (idx_w + 0.5) / len(clean_words)
                            sfx_start = seg_start + (seg_dur * fraction)
                            break

                # Pilar 3: Regla de prioridad para impactos (one-shot)
                if sfx_type == "impact":
                    if sfx_start - last_impact_time < 3.0:
                        continue # Evitar saturaciones
                    last_impact_time = sfx_start
                
                events.append({
                    "path": sfx_path,
                    "start": sfx_start,
                    "type": sfx_type,
                    "keyword": kw
                })
                break # Un solo sfx por segmento para no saturar

    return events


def generate_reddit_card(title, output_path, aspect_ratio="9:16"):
    """
    Genera una tarjeta flotante oscura de Reddit (AskReddit style) para el gancho visual.
    Usa PIL para renderizar de manera limpia y profesional con esquinas redondeadas.
    """
    # 1. Definir dimensiones de la tarjeta (ancho expandido a 1000px)
    card_width = 1000
    
    # 2. Configurar fuentes tipográficas (Arial Bold para el título, Arial para el resto)
    font_bold_path = "C:\\Windows\\Fonts\\arialbd.ttf"
    font_regular_path = "C:\\Windows\\Fonts\\arial.ttf"
    
    if not os.path.exists(font_bold_path):
        font_bold_path = "arial"
    if not os.path.exists(font_regular_path):
        font_regular_path = "arial"
        
    try:
        if font_bold_path != "arial":
            font_title = ImageFont.truetype(font_bold_path, 48)
            font_meta = ImageFont.truetype(font_regular_path, 28)
            font_sub = ImageFont.truetype(font_bold_path, 28)
        else:
            font_title = ImageFont.load_default()
            font_meta = ImageFont.load_default()
            font_sub = ImageFont.load_default()
    except Exception:
        font_title = ImageFont.load_default()
        font_meta = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # 3. Wrapping del texto del título (max_width = 920 px)
    max_text_width = 920
    words = title.split(' ')
    lines = []
    current_line = ''
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        try:
            bbox = font_title.getbbox(test_line)
            line_w = bbox[2] - bbox[0]
        except Exception:
            line_w = len(test_line) * 25
            
        if line_w <= max_text_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    # 4. Calcular la altura dinámica del título y de la tarjeta
    line_spacing = 10
    title_height = 0
    for line in lines:
        try:
            bbox = font_title.getbbox(line)
            h = bbox[3] - bbox[1]
        except Exception:
            h = 50
        title_height += h + line_spacing

    header_height = 90
    footer_height = 80
    card_height = header_height + title_height + footer_height

    # 5. Crear lienzo transparente (RGBA) y dibujar la tarjeta
    img = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Fondo gris oscuro Reddit (#1A1A1B) con esquinas redondeadas
    draw.rounded_rectangle((0, 0, card_width, card_height), radius=28, fill="#1A1A1B")

    # 6. Dibujar cabecera: Logo de Reddit, r/pregúntaleareddit y metadatos
    # Círculo naranja Reddit (#FF4500) - diámetro 36px
    draw.ellipse((40, 24, 76, 60), fill="#FF4500")
    # Letra "r" pequeña en blanco centrada en el círculo
    draw.text((52, 26), "r", font=font_meta, fill="white")
    
    # Subreddit name
    draw.text((88, 28), "r/pregúntaleareddit", font=font_sub, fill="#D7DADC")
    
    try:
        sub_w = font_sub.getbbox("r/pregúntaleareddit")[2] - font_sub.getbbox("r/pregúntaleareddit")[0]
    except Exception:
        sub_w = 260
        
    # Poster info
    draw.text((88 + sub_w + 12, 28), "• u/SilencioRojo • Hace 12h", font=font_meta, fill="#818384")

    # 7. Dibujar el título envuelto
    curr_y = header_height
    for line in lines:
        draw.text((40, curr_y), line, font=font_title, fill="#D7DADC")
        try:
            bbox = font_title.getbbox(line)
            h = bbox[3] - bbox[1]
        except Exception:
            h = 50
        curr_y += h + line_spacing

    # 8. Dibujar el pie de página (Votos y Comentarios en píldoras #272729)
    footer_y = curr_y + 12
    
    # Píldora de Upvotes
    draw.rounded_rectangle((40, footer_y, 220, footer_y + 44), radius=22, fill="#272729")
    draw.text((60, footer_y + 6), "▲ 4.2k ▼", font=font_meta, fill="#D7DADC")
    
    # Píldora de Comentarios
    draw.rounded_rectangle((240, footer_y, 390, footer_y + 44), radius=22, fill="#272729")
    draw.text((260, footer_y + 6), "💬 218", font=font_meta, fill="#D7DADC")

    # 9. Guardar la imagen generada
    img.save(output_path, "PNG")
    return True


def generate_default_luts():
    """
    Genera los archivos LUT por defecto en assets/video/luts si no existen.
    """
    project_root = os.getcwd()
    luts_dir = os.path.join(project_root, "assets", "video", "luts")
    os.makedirs(luts_dir, exist_ok=True)
    
    # 1. Gore Rojo
    gore_red_path = os.path.join(luts_dir, "gore_red.cube")
    if not os.path.exists(gore_red_path):
        write_lut(gore_red_path, lambda r, g, b: (min(1.0, r * 1.4), g * 0.6, b * 0.6))
        
    # 2. Terror Frío
    cold_terror_path = os.path.join(luts_dir, "cold_terror.cube")
    if not os.path.exists(cold_terror_path):
        write_lut(cold_terror_path, lambda r, g, b: (r * 0.65, min(1.0, g * 1.05), min(1.0, b * 1.35)))
        
    # 3. Misterio Oscuro
    misterio_oscuro_path = os.path.join(luts_dir, "misterio_oscuro.cube")
    if not os.path.exists(misterio_oscuro_path):
        def s_curve(x): return x * x * (3.0 - 2.0 * x)
        write_lut(misterio_oscuro_path, lambda r, g, b: (s_curve(r) * 0.85, s_curve(g) * 0.85, s_curve(b) * 0.85))
        
    # 4. Vintage VHS
    vintage_vhs_path = os.path.join(luts_dir, "vintage_vhs.cube")
    if not os.path.exists(vintage_vhs_path):
        def sepia(r, g, b):
            rn = min(1.0, r * 0.393 + g * 0.769 + b * 0.189)
            gn = min(1.0, r * 0.349 + g * 0.686 + b * 0.168)
            bn = min(1.0, r * 0.272 + g * 0.534 + b * 0.131)
            return (0.05 + rn * 0.9, 0.05 + gn * 0.9, 0.05 + bn * 0.9)
        write_lut(vintage_vhs_path, sepia)


def write_lut(path, filter_func, size=16):
    """
    Escribe un archivo de LUT 3D (.cube) a partir de una función de filtrado.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Generated by SilencioRojo\n")
            f.write(f"LUT_3D_SIZE {size}\n")
            for r in range(size):
                rn = r / (size - 1)
                for g in range(size):
                    gn = g / (size - 1)
                    for b in range(size):
                        bn = b / (size - 1)
                        ro, go, bo = filter_func(rn, gn, bn)
                        f.write(f"{ro:.6f} {go:.6f} {bo:.6f}\n")
    except Exception as e:
        print(f"Error escribiendo LUT {path}: {e}")


# Auto-generación de LUTs al importar el módulo
try:
    generate_default_luts()
except Exception as e:
    print(f"Error en la auto-generación de LUTs al importar: {e}")
