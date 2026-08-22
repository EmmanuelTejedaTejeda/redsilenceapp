import os
import glob
import asyncio
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.deps import (
    get_settings, get_groq_api_key, get_gemini_api_key, log_progress, PROGRESS_QUEUES,
    GenerateRequest, ScriptGenerationRequest, TitleDescriptionRequest,
    get_channel_paths
)
from modules.groq_client import generate_content as generate_groq_content
from modules.gameplay_sourcing import download_youtube_gameplay
from modules.video_render import render_final_video

router = APIRouter(prefix="/api/shorts", tags=["shorts"])


def calculate_render_percentage(msg: str) -> int:
    if not msg:
        return 0
    msg_lower = msg.lower()

    # 1. Mensajes de subida a YouTube (0% - 100%)
    if "subiendo" in msg_lower or "youtube" in msg_lower or "upload" in msg_lower:
        pct_match = re.search(r"(\d+)%", msg_lower)
        if pct_match:
            return min(100, max(0, int(pct_match.group(1))))
        if "iniciando subida" in msg_lower:
            return 5
        if "completado" in msg_lower or "éxito" in msg_lower or "exito" in msg_lower:
            return 100

    # 2. Transcripción y renderizado de clips individuales (76% - 95%)
    clip_match = re.search(r"clip\s+(\d+)(?:\s+(?:de|/)\s+|\s*/\s*)(\d+)", msg_lower)
    if clip_match:
        cur_clip = int(clip_match.group(1))
        tot_clips = int(clip_match.group(2))
        if tot_clips > 0:
            return min(95, 76 + int((cur_clip / tot_clips) * 19))

    # 3. Búsqueda y descarga de recursos del timeline (10% - 75%)
    res_match = re.search(r"recurso\s+(\d+)(?:\s+(?:de|/)\s+|\s*/\s*)(\d+)", msg_lower)
    if res_match:
        cur_res = int(res_match.group(1))
        tot_res = int(res_match.group(2))
        if tot_res > 0:
            return min(75, 10 + int((cur_res / tot_res) * 65))

    # 4. Hitos de pipeline fijos
    if "iniciando" in msg_lower or "calculando" in msg_lower:
        return 5
    elif "generando lista" in msg_lower or "recursos mixtos" in msg_lower:
        return 10
    elif "intercalando recursos" in msg_lower:
        return 72
    elif "timeline generado" in msg_lower:
        return 75
    elif "iniciando modo mix" in msg_lower or "iniciando renderizado" in msg_lower:
        return 76
    elif "recortando silencio" in msg_lower:
        return 77
    elif "subtítulos" in msg_lower or "subtitulos" in msg_lower:
        return 78
    elif "verificando aceleración" in msg_lower or "verificando aceleracion" in msg_lower:
        return 79
    elif "buscando b-roll" in msg_lower or "descargando b-roll" in msg_lower:
        return 80
    elif "paso 1/2" in msg_lower or "componiendo video" in msg_lower:
        return 96
    elif "paso 2/2" in msg_lower or "mezclando y sincronizando" in msg_lower:
        return 98
    elif "guardando render" in msg_lower:
        return 99
    elif "completados con éxito" in msg_lower or "completados con exito" in msg_lower or "compilado con éxito" in msg_lower or "short generado con éxito" in msg_lower:
        return 100

    return None


@router.get("/progress/{channel_name}")
async def api_shorts_progress(channel_name: str):
    async def event_generator():
        queue = asyncio.Queue()
        if channel_name not in PROGRESS_QUEUES:
            PROGRESS_QUEUES[channel_name] = []
        PROGRESS_QUEUES[channel_name].append(queue)
        
        try:
            while True:
                data = await queue.get()
                yield {"event": "message", "data": data}
        except asyncio.CancelledError:
            if channel_name in PROGRESS_QUEUES and queue in PROGRESS_QUEUES[channel_name]:
                PROGRESS_QUEUES[channel_name].remove(queue)
                if not PROGRESS_QUEUES[channel_name]:
                    del PROGRESS_QUEUES[channel_name]
                    
    return EventSourceResponse(event_generator())


def process_prompt_placeholders(prompt_template: str, user_trama: str = "", ch_lang: str = "es") -> str:
    clean_trama = user_trama.strip() if user_trama else ""
    
    placeholders = [
        "{TRAMA}", "{TEMA_O_TRAMA}", "{trama}", "{tema_o_trama}",
        "{Trama}", "{Tema_o_trama}", "{TRAMA_BASE}", "{trama_base}",
        "{TEMA}", "{tema}"
    ]
    
    prompt = prompt_template
    has_replaced = False
    
    if clean_trama:
        for ph in placeholders:
            if ph in prompt:
                prompt = prompt.replace(ph, clean_trama)
                has_replaced = True
        
        trama_header = f"TRAMA / TEMA PRINCIPAL OBLIGATORIO DE LA HISTORIA (ENTREGADO POR EL USUARIO): {clean_trama}\n(ESTÁ TERMINANTEMENTE PROHIBIDO OMITIR ESTA TRAMA O CREAR HISTORIAS SOBRE OTROS TEMAS NO RELACIONADOS)\n\n"
        prompt = trama_header + prompt
    else:
        empty_val = "[VACÍO: El usuario no especificó trama, investiga un tema de alto impacto para tu nicho]"
        for ph in placeholders:
            prompt = prompt.replace(ph, empty_val)

    prompt = prompt.replace("{GANCHO}", "un gancho directo e impactante")
    prompt = prompt.replace("{EVIDENCIA}", "evidencias inquietantes o registros reales")
    prompt = prompt.replace("{ATMOSFERA}", "una atmósfera opresiva y perturbadora")
    prompt = prompt.replace("{CIERRE}", "un cierre de suspense con loop perfecto")
    prompt = prompt.replace("{MONSTRUO}", "una presencia o entidad inquietante")
    prompt = prompt.replace("{ADN}", "detalles físicos perturbadores")
    prompt = prompt.replace("{INSERTA_PALABRAS_CLAVE_DE_TU_NICHO}", "palabras clave virales")
    prompt = prompt.replace("{INSERTA_TUS_RESTRICCIONES_AQUÍ}", "sin gore ni violencia explícita")

    anti_cliche_directive = (
        "\n\nDIRECTIVA CRÍTICA ANTI-CLICHÉ Y DEBATE OBLIGATORIO (MONETIZACIÓN YPP 2026/2027):\n"
        "1. QUEDA TERMINANTEMENTE PROHIBIDO usar frases vacías de IA desmonetizables como 'lo que descubrieron los dejó sin palabras', 'nada te preparará para lo que viene', 'lo que ocurrió a continuación cambió todo'.\n"
        "2. Aporta datos reales, nombres comprobables, fechas, registros o hechos documentados.\n"
        "3. CIERRE OBLIGATORIO CON PREGUNTA DE DEBATE COMUNITARIO: Las últimas 1-2 oraciones del guion DEBEN formular una pregunta de debate directa e inquisitiva para que la audiencia opine e interactúe en los comentarios."
    )
    prompt += anti_cliche_directive

    if ch_lang.lower() == "en":
        prompt += "\n\nCRITICAL LANGUAGE DIRECTIVE: The target language for this channel is ENGLISH ('en'). You MUST write 100% of the output script exclusively in natural, native English. ABSOLUTELY ZERO SPANISH WORDS, PHRASES, KEYWORDS, OR SYNTAX ARE ALLOWED."
    else:
        prompt += f"\n\nIDIOMA OBLIGATORIO: Genera todo el guion 100% en el idioma '{ch_lang}'."

    return prompt


def generate_viral_script(prompt_template: str, custom_instructions: str = "", api_key: str = "", provider: str = "groq", ch_lang: str = "es"):
    full_prompt = process_prompt_placeholders(prompt_template, custom_instructions, ch_lang)
    
    if provider == "gemini":
        from modules.gemini_client import generate_content as generate_gemini_content
        return generate_gemini_content(full_prompt, api_key, model_name="gemini-2.5-flash")
    else:
        return generate_groq_content(full_prompt, api_key)


# --- GENERACIÓN DE GUION CON IA ---
@router.post("/generate-script")
def api_generate_script(req: ScriptGenerationRequest):
    master_prompt = ""
    paths = get_channel_paths(req.channel_name)
    prompts_dir = paths["prompts"]

    if req.prompt_title:
        story_path = os.path.join(prompts_dir, f"{req.prompt_title}.txt")
        if not os.path.exists(story_path):
            story_path_root = os.path.join("config", "prompts", "story", f"{req.prompt_title}.txt")
            if os.path.exists(story_path_root):
                story_path = story_path_root
                
        if os.path.exists(story_path):
            try:
                with open(story_path, "r", encoding="utf-8") as f:
                    master_prompt = f.read()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error leyendo prompt físico: {e}")
                
    if not master_prompt and os.path.exists(prompts_dir) and os.listdir(prompts_dir):
        first_file = os.path.join(prompts_dir, os.listdir(prompts_dir)[0])
        with open(first_file, "r", encoding="utf-8") as f:
            master_prompt = f.read()

    if not master_prompt:
        master_prompt = "Escribe una historia viral para un Short."
        
    provider = "groq"
    if req.ai_engine and "gemini" in req.ai_engine.lower():
        provider = "gemini"

    if provider == "gemini":
        api_key = get_gemini_api_key()
        if not api_key:
            raise HTTPException(status_code=400, detail="Falta configurar la API Key de Gemini (google_api_key) en los Ajustes Generales.")
    else:
        api_key = get_groq_api_key()
        if not api_key:
            raise HTTPException(status_code=400, detail="Falta configurar la API Key de Groq.")

    settings = get_settings()
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c["name"].lower() == req.channel_name.lower()), None)
    ch_lang = ch_info.get("language", "es") if ch_info else "es"

    user_trama = req.custom_instructions or ""

    try:
        script = generate_viral_script(
            prompt_template=master_prompt,
            custom_instructions=user_trama,
            api_key=api_key,
            provider=provider,
            ch_lang=ch_lang
        )
        return {"status": "success", "script": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando guion con IA: {e}")


def resolve_narration_audio_file(req: GenerateRequest, channel_name: str, settings: dict) -> Optional[str]:
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c.get("name", "").lower() == (channel_name or "").lower()), None)
    paths = get_channel_paths(channel_name, settings)
    clean_ch = paths["clean_channel_name"]
    
    dirs_to_check = []
    
    if ch_info and isinstance(ch_info.get("folders"), dict):
        ch_audio = ch_info["folders"].get("audio_folder_path")
        if ch_audio and os.path.exists(ch_audio):
            dirs_to_check.append(ch_audio)
            sub = os.path.join(ch_audio, clean_ch)
            if os.path.exists(sub):
                dirs_to_check.append(sub)

    audio_output_dir = paths.get("audio")
    if audio_output_dir and os.path.exists(audio_output_dir) and audio_output_dir not in dirs_to_check:
        dirs_to_check.append(audio_output_dir)
        sub = os.path.join(audio_output_dir, clean_ch)
        if os.path.exists(sub) and sub not in dirs_to_check:
            dirs_to_check.append(sub)

    global_audio = settings.get("audio_folder_path")
    if global_audio and os.path.exists(global_audio):
        if global_audio not in dirs_to_check:
            dirs_to_check.append(global_audio)
        sub = os.path.join(global_audio, clean_ch)
        if os.path.exists(sub) and sub not in dirs_to_check:
            dirs_to_check.append(sub)

    default_ch_dir = os.path.join("projects", "channels", clean_ch, "audio")
    if os.path.exists(default_ch_dir) and default_ch_dir not in dirs_to_check:
        dirs_to_check.append(default_ch_dir)

    cache_audio = os.path.join("cache", "audio")
    if os.path.exists(cache_audio) and cache_audio not in dirs_to_check:
        dirs_to_check.append(cache_audio)

    if req.narration_file and str(req.narration_file).strip():
        n_file = str(req.narration_file).strip()
        if os.path.exists(n_file):
            return os.path.abspath(n_file)
            
        for d in dirs_to_check:
            target = os.path.join(d, n_file)
            if os.path.exists(target):
                return os.path.abspath(target)
                
            target_base = os.path.join(d, os.path.basename(n_file))
            if os.path.exists(target_base):
                return os.path.abspath(target_base)

    all_audio_files = []
    for d in dirs_to_check:
        try:
            for ext in ("*.wav", "*.mp3", "*.m4a", "*.ogg"):
                all_audio_files.extend(glob.glob(os.path.join(d, ext)))
        except Exception:
            continue

    if all_audio_files:
        all_audio_files.sort(key=os.path.getmtime, reverse=True)
        return os.path.abspath(all_audio_files[0])

    return None


# --- PROCESO COMPLETO EN SEGUNDO PLANO ---
def bg_generate_short_process(req: GenerateRequest):
    channel_name = req.channel_name
    log_progress(channel_name, "🚀 Iniciando pipeline de generación automatizada de Short...", "#e50914", 5)
    
    try:
        groq_key = get_groq_api_key()
        settings = get_settings()
        channel_info = next((c for c in settings.get("channels", []) if c["name"] == channel_name), None)
        theme = channel_info.get("theme", "General") if channel_info else "General"
        ch_lang = channel_info.get("language", "es") if channel_info else "es"

        paths = get_channel_paths(channel_name, settings)
        prompts_dir = paths["prompts"]

        script_text = req.custom_prompt or ""
        if not script_text:
            provider = "gemini" if req.ai_engine and "gemini" in req.ai_engine.lower() else "groq"
            log_progress(channel_name, f"✍️ Generando guion viral con {provider.upper()} ({ch_lang})...", "#ff007f", 15)
            
            if provider == "gemini":
                api_key = get_gemini_api_key()
                if not api_key:
                    log_progress(channel_name, "❌ Error: API Key de Gemini no configurada.", "#ff4444", 0)
                    return
            else:
                api_key = groq_key

            master_prompt = ""
            if req.prompt_title:
                file_by_title = os.path.join(prompts_dir, f"{req.prompt_title}.txt")
                if os.path.exists(file_by_title):
                    with open(file_by_title, "r", encoding="utf-8") as f:
                        master_prompt = f.read()

            if not master_prompt and os.path.exists(prompts_dir) and os.listdir(prompts_dir):
                first_file = os.path.join(prompts_dir, os.listdir(prompts_dir)[0])
                with open(first_file, "r", encoding="utf-8") as f:
                    master_prompt = f.read()

            if not master_prompt:
                master_prompt = "Escribe una historia viral para un Short."

            user_trama = req.custom_prompt or ""
            script_text = generate_viral_script(
                prompt_template=master_prompt,
                custom_instructions=user_trama,
                api_key=api_key,
                provider=provider,
                ch_lang=ch_lang
            )

        audio_output_dir = paths["audio"]
        os.makedirs(audio_output_dir, exist_ok=True)
        
        # 2. Selección de locución de narración
        audio_file = resolve_narration_audio_file(req, channel_name, settings)

        if not audio_file:
            log_progress(channel_name, "❌ Error: No se encontró ningún archivo de locución/audio en la carpeta del canal.", "#ff4444", 0)
            return

        # 3. Recopilación de Recursos del Timeline (videos e imágenes)
        v_dir = paths["videos"]
        i_dir = paths["images"]
        timeline_files = []
        if os.path.exists(v_dir):
            for f in os.listdir(v_dir):
                if f.lower().endswith(('.mp4', '.mkv', '.webm')):
                    timeline_files.append(os.path.abspath(os.path.join(v_dir, f)))
        if os.path.exists(i_dir):
            for f in os.listdir(i_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    timeline_files.append(os.path.abspath(os.path.join(i_dir, f)))
                    
        timeline_files.sort(key=lambda x: os.path.getctime(x))

        # Música de fondo
        music_path = None
        if req.music_name and req.music_name != "Ninguno":
            m_dir = paths["music"]
            if not os.path.exists(m_dir):
                m_dir = os.path.join("assets", "audio", "music")
            target_m = os.path.join(m_dir, req.music_name)
            if os.path.exists(target_m):
                music_path = os.path.abspath(target_m)

        # Directorio de salida para renders
        output_folder = paths["renders"]
        os.makedirs(output_folder, exist_ok=True)

        def render_progress_callback(msg, color=None):
            perc = calculate_render_percentage(msg)
            log_progress(channel_name, msg, color or "#00ffcc", percentage=perc)

        title_text = req.video_title or f"Short_{channel_name}"
        desc_text = script_text[:200] if script_text else ""

        log_progress(channel_name, "🎬 Iniciando renderizado del Short...", "#00ffcc", 75)
        
        enable_subs = req.enable_subtitles if req.enable_subtitles is not None else True

        final_video_path = render_final_video(
            audio_path=audio_file,
            images_paths=timeline_files,
            cover_path=None,
            output_folder=output_folder,
            title=title_text,
            description=desc_text,
            vhs_enabled=False,
            music_path=music_path,
            status_callback=render_progress_callback,
            groq_key=groq_key,
            aspect_ratio="9:16",
            sub_style=req.sub_style or "Reddit History",
            enable_subtitles=enable_subs,
            language=ch_lang
        )

        log_progress(channel_name, "🎉 ¡Short generado con éxito!", "#00ff00", 100, output_path=final_video_path)

    except Exception as e:
        print(f"Error fatal en bg_generate_short_process: {e}")
        log_progress(channel_name, f"❌ Error fatal en generación: {e}", "#ff1a1a", 0)


@router.post("/generate")
def api_generate_short(req: GenerateRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(bg_generate_short_process, req)
    return {"status": "success", "message": "Proceso de generación encolado en segundo plano."}


@router.post("/generate-title-description")
def api_generate_title_description(req: TitleDescriptionRequest):
    story_text = req.story.strip()
    if not story_text:
        raise HTTPException(status_code=400, detail="La historia/guion está vacía.")
    
    template_path = os.path.join("config", "prompts", "title_description", "PROMPT_TITLE_DESCRIPTION.txt")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail=f"No se encontró el archivo de prompt de metadatos en: {template_path}")
        
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo el archivo de prompt: {e}")
        
    settings = get_settings()
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c["name"].lower() == req.channel_name.lower()), None)
    ch_lang = ch_info.get("language", "es") if ch_info else "es"

    prompt = template.replace("{STORY}", story_text).replace("{story}", story_text)
    if ch_lang.lower() == "en":
        prompt += "\n\nCRITICAL LANGUAGE DIRECTIVE: Generate all titles, description, and hashtags 100% in natural, native ENGLISH ('en'). ABSOLUTELY ZERO SPANISH WORDS, PHRASES, OR SYNTAX ARE ALLOWED."
    else:
        prompt += f"\n\nIDIOMA OBLIGATORIO: Genera los títulos, descripción y hashtags 100% en el idioma '{ch_lang}'."

    provider = "gemini" if req.ai_engine and "gemini" in req.ai_engine.lower() else "groq"
    
    if provider == "gemini":
        api_key = get_gemini_api_key()
        if not api_key:
            raise HTTPException(status_code=400, detail="API Key de Gemini no configurada.")
    else:
        api_key = get_groq_api_key()
        if not api_key:
            raise HTTPException(status_code=400, detail="API Key de Groq no configurada.")
            
    try:
        if provider == "gemini":
            from modules.gemini_client import generate_content as generate_gemini_content
            raw_text = generate_gemini_content(prompt, api_key, model_name="gemini-2.5-flash")
        else:
            raw_text = generate_groq_content(prompt, api_key)
            
        title_section_match = re.search(r"(?:---|###|\*\*|\b)(?:T[ÍI]TULOS|TITLES).*?(?:---|###|\*\*|\n)(.*?)(?=(?:---|###|\*\*|\b)(?:DESCRIPCI[OÓ]N|DESCRIPTION)|$)", raw_text, re.DOTALL | re.IGNORECASE)
        desc_section_match = re.search(r"(?:---|###|\*\*|\b)(?:DESCRIPCI[OÓ]N|DESCRIPTION).*?(?:---|###|\*\*|\n)(.*)", raw_text, re.DOTALL | re.IGNORECASE)
        
        titles = []
        description = ""
        
        if title_section_match:
            lines = title_section_match.group(1).strip().split("\n")
            for line in lines:
                line_str = line.strip()
                cleaned = re.sub(r"^(?:\d+[\.\)]|[-*•])\s*", "", line_str).strip()
                cleaned = cleaned.strip('"\'`*#')
                if cleaned and len(cleaned) >= 5 and not cleaned.startswith("---") and not cleaned.lower().startswith("título") and not cleaned.lower().startswith("title"):
                    titles.append(cleaned)
                    
        if desc_section_match:
            description = desc_section_match.group(1).strip()
            description = re.sub(r"^(?:---|###|\*\*)\s*", "", description).strip()

        # Fallback 1: Buscar líneas numeradas si el regex de encabezado no coincidió
        if not titles:
            numbered_lines = re.findall(r"^\s*(?:\d+[\.\)]|[-*•])\s*(.+)$", raw_text, re.MULTILINE)
            for line in numbered_lines:
                cleaned = line.strip().strip('"\'`*#')
                if len(cleaned) >= 10 and not any(k in cleaned.lower() for k in ["hashtag", "descripción", "description", "http"]):
                    titles.append(cleaned)
                    if len(titles) >= 3:
                        break

        # Fallback 2: Extraer descripción si el regex de encabezado falló
        if not description:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            non_title_lines = [l for l in lines if not any(l == t for t in titles) and not l.startswith("---") and not l.startswith("###")]
            if non_title_lines:
                description = "\n\n".join(non_title_lines)

        # Fallback 3: Título por defecto de emergencia
        if not titles:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if lines:
                titles = [re.sub(r"^(?:\d+[\.\)]|[-*•])\s*", "", lines[0]).strip('"\'`*#')]
            else:
                titles = [f"Short - {req.channel_name}"]
            
        main_title = titles[0] if titles else f"Short - {req.channel_name}"
            
        return {
            "status": "success",
            "title": main_title,
            "titles": titles,
            "description": description,
            "raw": raw_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando título/descripción con IA: {e}")


@router.get("/last-render")
def api_get_last_render(channel_name: Optional[str] = None):
    settings = get_settings()
    mp4_files = []
    
    if channel_name:
        paths = get_channel_paths(channel_name, settings)
        ch_renders = paths["renders"]
        if os.path.exists(ch_renders):
            mp4_files.extend(glob.glob(os.path.join(ch_renders, "*.mp4")))
            
    if not mp4_files:
        renders_dir = settings.get("renders_folder_path") or os.path.join("projects", "renders")
        if os.path.exists(renders_dir):
            mp4_files.extend(glob.glob(os.path.join(renders_dir, "**", "*.mp4"), recursive=True))
            
    if not mp4_files:
        return {"status": "error", "message": "No hay videos renderizados."}
    
    mp4_files.sort(key=os.path.getmtime, reverse=True)
    
    if channel_name:
        channel_lower = channel_name.lower()
        for f in mp4_files:
            if channel_lower in os.path.basename(f).lower():
                return {
                    "status": "success",
                    "path": f,
                    "filename": os.path.basename(f)
                }
    
    latest_video = mp4_files[0]
    return {
        "status": "success",
        "path": latest_video,
        "filename": os.path.basename(latest_video)
    }


class ScriptGenerateTramaRequest(BaseModel):
    script: str
    channel_name: Optional[str] = None

@router.post("/generate-trama-from-script")
def api_generate_trama_from_script(req: ScriptGenerateTramaRequest):
    if not req.script.strip():
        raise HTTPException(status_code=400, detail="El guion está vacío.")
    
    groq_key = get_groq_api_key()
    if not groq_key:
        raise HTTPException(status_code=400, detail="API Key de Groq no configurada.")
        
    settings = get_settings()
    channel_name = req.channel_name or settings.get("active_channel")
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c.get("name", "").lower() == (channel_name or "").lower()), None)
    
    ch_theme = ch_info.get("theme", "General") if ch_info else "General"
    ch_lang = ch_info.get("language", "es") if ch_info else "es"

    prompt = f"""
Eres un asistente experto en producción visual de videos cortos (TikTok/Shorts).
Analiza el siguiente guion de un canal con temática '{ch_theme}' (idioma del canal: {ch_lang}).
Extrae la trama visual o idea principal para buscar recursos de video en un máximo de 10 palabras (conciso, descriptivo y directo), en el idioma '{ch_lang}'.
No incluyas nada más en tu respuesta.

GUION:
{req.script[:1500]}
"""
    try:
        trama = generate_groq_content(prompt, groq_key)
        return {"status": "success", "trama": trama.strip().replace('"', '')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar trama: {e}")
