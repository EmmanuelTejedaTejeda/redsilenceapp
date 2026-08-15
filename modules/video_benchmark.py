import os
import re
import subprocess
import json
import yt_dlp
from modules.render_utils import transcribe_with_groq

def clean_filename(name):
    return re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_').lower())

def download_youtube_audio(url, output_dir, status_callback=None):
    """
    Descarga únicamente el audio de una URL de YouTube usando yt-dlp.
    Retorna la ruta absoluta del archivo m4a/mp3 descargado.
    """
    os.makedirs(output_dir, exist_ok=True)
    clean_name = "audio_" + clean_filename(url[-11:]) # Usamos los últimos 11 caracteres del ID/URL como identificador
    
    # Buscar si ya existe algún archivo con ese nombre base en el directorio
    for f in os.listdir(output_dir):
        if f.startswith(clean_name) and os.path.isfile(os.path.join(output_dir, f)):
            existing_path = os.path.abspath(os.path.join(output_dir, f))
            if os.path.getsize(existing_path) > 0:
                if status_callback:
                    status_callback(f"♻️ Reutilizando audio ya descargado: {f}", "#00FF66")
                return existing_path

    if status_callback:
        status_callback("🌐 Conectando con YouTube y descargando audio...", "#FFD700")
    output_template = os.path.join(output_dir, f"{clean_name}.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            # Corregir extensión en caso de discrepancias
            if not os.path.exists(downloaded_file):
                ext = info.get('ext', 'm4a')
                downloaded_file = os.path.splitext(downloaded_file)[0] + f".{ext}"
                
            if os.path.exists(downloaded_file):
                if status_callback:
                    status_callback(f"📥 Descarga completada: {os.path.basename(downloaded_file)}", "#00FF66")
                return os.path.abspath(downloaded_file)
            else:
                raise Exception("El archivo de audio no se encontró después de la descarga.")
    except Exception as e:
        print(f"Error descargando audio de YouTube: {e}")
        if status_callback:
            status_callback(f"🛑 Error de descarga: {str(e)[:40]}", "red")
        raise e

def transcribe_audio_benchmark(audio_path, api_key=None, status_callback=None):
    """
    Transcribe el audio usando Groq Whisper (si hay API Key) o cae en Whisper local (gratuito).
    """
    if api_key:
        if status_callback:
            status_callback("🎙️ Transcribiendo audio mediante Groq Whisper API...", "#FFD700")
        try:
            result = transcribe_with_groq(audio_path, api_key, language="es")
            if result:
                return result
        except Exception as e:
            print(f"Error en Groq Whisper benchmark: {e}")
            if status_callback:
                status_callback("⚠️ Groq falló. Usando Whisper local...", "orange")
                
    if status_callback:
        status_callback("🎙️ Transcribiendo audio localmente con Whisper (100% gratis)...", "#FFD700")
        
    global _WHISPER_MODEL
    import whisper
    
    # Cargar el modelo tiny de Whisper para velocidad local
    model = whisper.load_model("tiny")
    result = model.transcribe(audio_path, word_timestamps=True, language="es")
    return result

def calculate_pacing_metrics(whisper_json):
    """
    Analiza la transcripción Whisper para medir velocidad (WPM) y pausas dramáticas.
    """
    segments = whisper_json.get("segments", [])
    if not segments:
        return {
            "total_words": 0,
            "total_duration": 0.0,
            "wpm": 0.0,
            "silence_count": 0,
            "avg_silence_dur": 0.0,
            "pacing_desc": "Sin datos"
        }
        
    all_words = []
    for seg in segments:
        words_data = seg.get("words", [])
        if words_data:
            for w in words_data:
                all_words.append(w)
        else:
            # Fallback si no hay word timestamps
            words = seg.get("text", "").split()
            seg_start = seg.get("start", 0.0)
            seg_end = seg.get("end", 0.0)
            dur_per_word = (seg_end - seg_start) / max(1, len(words))
            for i, w in enumerate(words):
                all_words.append({
                    "word": w,
                    "start": seg_start + (i * dur_per_word),
                    "end": seg_start + ((i + 1) * dur_per_word)
                })
                
    if not all_words:
        return {
            "total_words": 0,
            "total_duration": 0.0,
            "wpm": 0.0,
            "silence_count": 0,
            "avg_silence_dur": 0.0,
            "pacing_desc": "Sin palabras"
        }
        
    total_words = len(all_words)
    first_word_start = all_words[0]["start"]
    last_word_end = all_words[-1]["end"]
    total_duration = max(0.1, last_word_end - first_word_start)
    
    wpm = (total_words / total_duration) * 60
    
    # Calcular pausas/silencios dramáticos entre palabras consecutivas
    silences = []
    for i in range(len(all_words) - 1):
        gap = all_words[i+1]["start"] - all_words[i]["end"]
        if gap > 0.4:  # Pausas de silencio notables
            silences.append(gap)
            
    silence_count = len(silences)
    avg_silence_dur = sum(silences) / max(1, silence_count)
    
    # Clasificación de ritmo
    if wpm > 150:
        pacing_desc = "Rápido / Dinámico (Estilo Shorts/Retención alta)"
    elif wpm > 115:
        pacing_desc = "Estándar / Narrativo (Equilibrado)"
    else:
        pacing_desc = "Pausado / Tenebroso (Estilo Suspenso/Atmósfera)"
        
    return {
        "total_words": total_words,
        "total_duration": round(total_duration, 1),
        "wpm": round(wpm, 1),
        "silence_count": silence_count,
        "avg_silence_dur": round(avg_silence_dur, 2),
        "pacing_desc": pacing_desc
    }

def compare_narrative_ai(my_script, my_metrics, ref_script, ref_metrics, api_key, provider="gemini"):
    """
    Llama a Gemini o Groq para analizar comparativamente los guiones y métricas.
    """
    from modules import gemini_client, groq_client
    
    prompt = (
        "Actúa como un Consultor Experto en Estrategia de Contenido de YouTube y Viralización de Creepypastas/Historias de Terror.\n"
        "Tu tarea es analizar y comparar en detalle el guion y el ritmo de locución de dos videos largos:\n"
        "1. MI VIDEO (El video a mejorar).\n"
        "2. VIDEO DE REFERENCIA (El video del competidor exitoso, ej: Willyrex o similar).\n\n"
        "--- DATOS DE MI VIDEO ---\n"
        f"- Métricas de Ritmo: {json.dumps(my_metrics, indent=2)}\n"
        f"- Guion Hablado:\n{my_script}\n\n"
        "--- DATOS DEL VIDEO DE REFERENCIA ---\n"
        f"- Métricas de Ritmo: {json.dumps(ref_metrics, indent=2)}\n"
        f"- Guion Hablado:\n{ref_script}\n\n"
        "--- INSTRUCCIONES DE ANÁLISIS ---\n"
        "Por favor, genera un informe de auditoría detallado en formato Markdown, estructurado en las siguientes secciones:\n"
        "1. **Comparación del Gancho Inicial (Primeros 30s)**: Analiza cómo empieza cada uno, qué palabras o recursos narrativos usa el competidor para atrapar al espectador y qué le falta a mi video.\n"
        "2. **Análisis de Ritmo y Fluidez (Pacing)**: Compara las métricas de Palabras por Minuto (WPM) y los silencios/pausas dramáticas. Explica si el ritmo de mi video es adecuado o si resulta aburrido/acelerado comparado con el de referencia.\n"
        "3. **Estructura Narrativa y Vocabulario**: Analiza la construcción de la tensión, el vocabulario de horror utilizado y cómo se mantiene el interés a lo largo del guion.\n"
        "4. **Recomendaciones Clave para Hacer mi Video Viral**: Lista de 4 o 5 cambios accionables e inmediatos que debo realizar en la estructura de mis guiones y la edición del audio para lograr videos largos de alta retención.\n"
        "5. **Conclusión y Plan de Acción**: Resumen estratégico corto.\n\n"
        "Sé directo, analítico y profesional. Escribe la respuesta en español."
    )
    
    if provider == "groq" and api_key:
        return groq_client.generate_content(prompt, api_key)
    else:
        return gemini_client.generate_content(prompt, api_key)
