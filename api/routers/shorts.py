import os
import glob
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from sse_starlette.sse import EventSourceResponse

from api.deps import (
    get_settings, get_groq_api_key, get_gemini_api_key, log_progress, PROGRESS_QUEUES,
    GenerateRequest, ScriptGenerationRequest, SynthesizeVoiceRequest, TitleDescriptionRequest
)
from modules.groq_client import generate_content as generate_groq_content
from modules.voice_generator import generate_voice
from modules.gameplay_sourcing import download_youtube_gameplay
from modules.video_render import render_final_video

import re

def calculate_render_percentage(msg: str) -> int:
    msg_lower = msg.lower()
    if "iniciando modo mix" in msg_lower:
        return 76
    elif "recortando silencio" in msg_lower:
        return 77
    elif "subtítulos" in msg_lower or "subtitulos" in msg_lower:
        return 78
    elif "verificando aceleración" in msg_lower or "verificando aceleracion" in msg_lower:
        return 79
    elif "buscando b-roll" in msg_lower:
        return 80
    elif "descargando b-roll" in msg_lower:
        return 81
    elif "paso 1/2" in msg_lower or "componiendo video" in msg_lower:
        return 96
    elif "paso 2/2" in msg_lower or "mezclando y sincronizando" in msg_lower:
        return 98
    elif "guardando render" in msg_lower:
        return 99
    elif "completados con éxito" in msg_lower or "completados con exito" in msg_lower or "compilado con éxito" in msg_lower:
        return 100
    
    # Try parsing patterns like "3 de 10" or "3/10"
    match = re.search(r"(\d+)\s*(?:de|/)\s*(\d+)", msg)
    if match:
        try:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                fraction = current / total
                return int(82 + fraction * 13)
        except:
            pass
            
    return 75

router = APIRouter(prefix="/api/shorts", tags=["shorts"])


def generate_viral_script(prompt_template: str, custom_instructions: str = "", api_key: str = "", provider: str = "groq"):
    full_prompt = f"{prompt_template}\n\nInstrucciones adicionales: {custom_instructions}" if custom_instructions else prompt_template
    if provider == "gemini":
        from modules.gemini_client import generate_content as generate_gemini_content
        return generate_gemini_content(full_prompt, api_key, model_name="gemini-2.5-flash")
    else:
        return generate_groq_content(full_prompt, api_key, model_name="llama-3.3-70b-versatile")



def generate_voice_narration(script_text: str, output_path: str, voice_name: str = "Fritz-PlayAI", api_key: str = ""):
    voice_inst = os.path.join("config", "prompts", "voice", "voice_instructions.txt")
    if not os.path.exists(voice_inst):
        voice_inst = None
    return generate_voice(script_text, api_key, voice_inst, output_path, voice_name=voice_name)



# --- STREAMING SSE DE PROGRESO ---
@router.get("/progress/{channel_name}")
async def sse_progress(channel_name: str):
    if channel_name not in PROGRESS_QUEUES:
        PROGRESS_QUEUES[channel_name] = []
        
    queue = asyncio.Queue()
    PROGRESS_QUEUES[channel_name].append(queue)
    
    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield {"data": data}
        except asyncio.CancelledError:
            pass
        finally:
            if channel_name in PROGRESS_QUEUES and queue in PROGRESS_QUEUES[channel_name]:
                PROGRESS_QUEUES[channel_name].remove(queue)

    return EventSourceResponse(event_generator())


# --- GENERACIÓN DE GUION CON IA ---
@router.post("/generate-script")
def api_generate_script(req: ScriptGenerationRequest):
    master_prompt = ""
    if req.prompt_title:
        story_path = os.path.join("config", "prompts", "story", req.channel_name, f"{req.prompt_title}.txt")
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
                
    if not master_prompt:
        raise HTTPException(status_code=404, detail="Prompt Master no encontrado.")
        
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
        
    try:
        script = generate_viral_script(
            prompt_template=master_prompt,
            custom_instructions=req.custom_instructions or "",
            api_key=api_key,
            provider=provider
        )
        return {"status": "success", "script": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando guion con IA: {e}")


# --- PROCESO COMPLETO EN SEGUNDO PLANO ---
def bg_generate_short_process(req: GenerateRequest):
    channel_name = req.channel_name
    log_progress(channel_name, "🚀 Iniciando pipeline de generación automatizada de Short...", "#e50914", 5)
    
    try:
        groq_key = get_groq_api_key()
        if not groq_key:
            log_progress(channel_name, "❌ Error: API Key de Groq no configurada (requerida para síntesis de voz).", "#ff4444", 0)
            return

        settings = get_settings()
        channel_info = next((c for c in settings.get("channels", []) if c["name"] == channel_name), None)
        theme = channel_info.get("theme", "Terror Analógico") if channel_info else "Terror Analógico"

        # 1. Selección o Generación del Guion
        script_text = req.custom_prompt or ""
        if not script_text:
            provider = "gemini" if req.ai_engine and "gemini" in req.ai_engine.lower() else "groq"
            log_progress(channel_name, f"✍️ Generando guion viral con {provider.upper()}...", "#ff007f", 15)
            
            if provider == "gemini":
                api_key = get_gemini_api_key()
                if not api_key:
                    log_progress(channel_name, "❌ Error: API Key de Gemini no configurada.", "#ff4444", 0)
                    return
            else:
                api_key = groq_key

            master_prompt = ""
            if req.prompt_title:
                story_path = os.path.join("config", "prompts", "story", channel_name, f"{req.prompt_title}.txt")
                if not os.path.exists(story_path):
                    # Compatibilidad si no tenía .txt en el nombre del request o si está en la raíz
                    story_path_root = os.path.join("config", "prompts", "story", f"{req.prompt_title}.txt")
                    if os.path.exists(story_path_root):
                        story_path = story_path_root
                
                if os.path.exists(story_path):
                    with open(story_path, "r", encoding="utf-8") as f:
                        master_prompt = f.read()

            if not master_prompt:
                story_dir = os.path.join("config", "prompts", "story", channel_name)
                if os.path.exists(story_dir) and os.listdir(story_dir):
                    first_file = os.path.join(story_dir, os.listdir(story_dir)[0])
                    with open(first_file, "r", encoding="utf-8") as f:
                        master_prompt = f.read()

            if not master_prompt:
                master_prompt = "Escribe una historia inquietante de terror para un Short."

            script_text = generate_viral_script(prompt_template=master_prompt, api_key=api_key, provider=provider)

        audio_output_dir = settings.get("audio_folder_path") or os.path.join("cache", "audio")
        
        # Check if pre-selected narration file is used
        if req.narration_file:
            resolved_audio_path = os.path.join(audio_output_dir, req.narration_file)
            if os.path.exists(resolved_audio_path):
                log_progress(channel_name, f"🎙️ Usando narración pre-seleccionada del servidor: {req.narration_file}", "#00d2ff", 35)
                audio_output_path = resolved_audio_path
            else:
                log_progress(channel_name, f"⚠️ Audio seleccionado '{req.narration_file}' no encontrado. Generando nueva voz...", "#ffae00", 30)
                os.makedirs(audio_output_dir, exist_ok=True)
                audio_output_path = os.path.join(audio_output_dir, f"narracion_{channel_name}.mp3")
                voice_name = req.voice_name or "Fritz-PlayAI"
                generate_voice_narration(script_text, audio_output_path, voice_name=voice_name, api_key=groq_key)
        else:
            log_progress(channel_name, "🎙️ Sintetizando voz...", "#00d2ff", 35)
            os.makedirs(audio_output_dir, exist_ok=True)
            audio_output_path = os.path.join(audio_output_dir, f"narracion_{channel_name}.mp3")
            voice_name = req.voice_name or "Fritz-PlayAI"
            generate_voice_narration(script_text, audio_output_path, voice_name=voice_name, api_key=groq_key)

        # 2. Obtención de Fondo (Videos, GIFs e Imágenes integrados en el Timeline)
        log_progress(channel_name, "🎮 Buscando clips y recursos en el timeline...", "#ffae00", 55)
        
        custom_videos_dir = settings.get("videos_folder_path")
        custom_images_dir = settings.get("images_folder_path")
        
        existing_assets = []
        
        # Cargar videos y GIFs del timeline
        if custom_videos_dir and os.path.exists(custom_videos_dir):
            for ext in ('*.mp4', '*.mov', '*.avi', '*.mkv', '*.webm', '*.gif'):
                existing_assets += glob.glob(os.path.join(custom_videos_dir, ext))
                existing_assets += glob.glob(os.path.join(custom_videos_dir, "*", ext))
                
        # Cargar imágenes del timeline
        if custom_images_dir and os.path.exists(custom_images_dir):
            for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp'):
                existing_assets += glob.glob(os.path.join(custom_images_dir, ext))
                existing_assets += glob.glob(os.path.join(custom_images_dir, "*", ext))
                
        # Ordenar cronológicamente (ctime) para respetar la secuencia que el usuario ve en la UI (más viejo primero)
        existing_assets.sort(key=lambda x: os.path.getctime(x) if os.path.exists(x) else 0)

        # Si no hay recursos en el timeline, buscar en la caché temporal de gameplays
        if not existing_assets:
            gameplay_dir = os.path.join("cache", "gameplays")
            if os.path.exists(gameplay_dir):
                existing_assets = glob.glob(os.path.join(gameplay_dir, "*.mp4")) + glob.glob(os.path.join(gameplay_dir, "*", "*.mp4"))

        mixed_media = []
        if existing_assets:
            # Filtrar por palabra clave si se especifica bg_source
            if req.bg_source:
                bg_keywords = [w.lower() for w in req.bg_source.split() if len(w) > 2]
                if not bg_keywords:
                    bg_keywords = [req.bg_source.lower()]
                
                matching_clips = []
                for g in existing_assets:
                    path_lower = g.lower()
                    if any(kw in path_lower for kw in bg_keywords):
                        matching_clips.append(g)
                
                if matching_clips:
                    for g in matching_clips[:25]:
                        ext = os.path.splitext(g)[1].lower()
                        is_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif']
                        mixed_media.append({
                            "path": g,
                            "type": "video" if is_video else "image",
                            "has_audio": is_video
                        })
            
            # Fallback si no hay coincidencias de palabra clave o no se especificó bg_source
            if not mixed_media:
                for g in existing_assets[:25]:
                    ext = os.path.splitext(g)[1].lower()
                    is_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif']
                    mixed_media.append({
                        "path": g,
                        "type": "video" if is_video else "image",
                        "has_audio": is_video
                    })
        else:
            # Si no hay absolutamente nada descargado, usar downloader de Youtube
            gameplay_dir = settings.get("downloader_folder_path") or os.path.join("cache", "gameplays")
            os.makedirs(gameplay_dir, exist_ok=True)
            query = f"{req.bg_source or 'roblox parkour'} gameplay 4k no commentary"
            try:
                gp_path = download_youtube_gameplay(query, gameplay_dir, status_callback=lambda msg, color: log_progress(channel_name, msg, color, 65))
                mixed_media = [{"path": gp_path, "type": "video", "has_audio": False}]
            except Exception as e:
                log_progress(channel_name, f"⚠️ Aviso en gameplay, usando fallback: {e}", "#ffae00", 65)

        # 3. Música de fondo
        music_path = None
        if req.music_name and req.music_name != "Ninguno":
            music_dir = settings.get("music_folder_path") or os.path.join("assets", "music")
            possible_music = os.path.join(music_dir, req.music_name)
            if os.path.exists(possible_music):
                music_path = possible_music

        # 4. Renderizado Final
        log_progress(channel_name, "🎞️ Ensamblando vídeo 9:16, subtítulos dinámicos y audio...", "#9d00ff", 75)
        output_dir = settings.get("renders_folder_path") or os.path.join("projects", "renders")
        os.makedirs(output_dir, exist_ok=True)

        selected_lut = "Horror_Cool" if "Terror" in theme else "Vibrant_Punch"

        final_video_path = render_final_video(
            audio_path=audio_output_path,
            images_paths=mixed_media,
            cover_path=None,
            output_folder=output_dir,
            title=req.video_title or req.prompt_title or channel_name or "Short_NexusStudio",
            description="Short autogenerado por ShortNexus Studio Core",
            vhs_enabled=True,
            music_path=music_path,
            media_mode="mix",
            status_callback=lambda msg, *a: log_progress(
                channel_name=channel_name,
                message=msg,
                color=a[0] if a else "#ffffff",
                percentage=calculate_render_percentage(msg)
            ),
            groq_key=groq_key,
            aspect_ratio="9:16",
            lut_name=selected_lut,
            sub_style=req.sub_style,
            reddit_card_title="Pregunta intrigante de Reddit..." if req.sub_style == "Reddit History" else None,
            pacing="Dinámico [2.0s]",
            vol_voice=100.0,
            vol_music=35.0,
            vol_sfx=25.0,
            render_quality=req.render_quality,
            enable_brolls=True,
            enable_subtitles=req.enable_subtitles
        )
        log_progress(
            channel_name=channel_name,
            message=f"🎉 Short compilado con éxito: {os.path.basename(final_video_path)}",
            color="#00ff88",
            percentage=100,
            output_path=final_video_path
        )
        
        # --- Guardar Metadatos de Generación ---
        try:
            from modules.render_utils import get_media_duration
            from modules.analytics_client import load_generation_metadata, save_generation_metadata
            import re
            
            gen_meta = load_generation_metadata()
            
            # El titulo usado para guardar el video (safe_title)
            raw_title = req.video_title or req.prompt_title or channel_name or "Short_NexusStudio"
            safe_title = "".join([c for c in raw_title if c.isalnum() or c==' ']).rstrip().replace(" ", "_") or "Video_Render_Mix"
            
            duracion_narracion = get_media_duration(audio_output_path)
            
            gen_meta[safe_title] = {
                "prompt_master": req.prompt_title or "Ninguno",
                "trama": script_text,
                "duracion_narracion": duracion_narracion,
                "cantidad_clips": len(mixed_media),
                "intercalar_gameplay": any(m.get("type") == "video" for m in mixed_media),
                "cancion": req.music_name or "Ninguno",
                "volumen_cancion": 35.0,
                "volumen_narracion": 100.0,
                "tipo_subtitulos": req.sub_style,
                "calidad": req.render_quality,
                "titulo": req.video_title or req.prompt_title or "Video Autogenerado",
                "descripcion": "Short autogenerado por ShortNexus Studio Core",
                "timestamp": datetime.datetime.now().isoformat()
            }
            save_generation_metadata(gen_meta)
        except Exception as e_meta:
            print(f"Error guardando metadatos de generación: {e_meta}")
            


    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        log_progress(channel_name, f"❌ Error fatal en generación: {e}", "#ff1a1a", 0)
        print(f"ERROR EN RENDER: {err_msg}")


@router.post("/generate")
def api_generate_short(req: GenerateRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(bg_generate_short_process, req)
    return {"status": "success", "message": "Proceso de generación encolado en segundo plano de forma asíncrona."}


@router.post("/synthesize-voice")
def api_synthesize_voice(req: SynthesizeVoiceRequest):
    groq_key = get_groq_api_key()
    if not groq_key:
        raise HTTPException(status_code=400, detail="API Key de Groq no configurada (requerida para síntesis de voz).")
    
    settings = get_settings()
    audio_dir = settings.get("audio_folder_path") or os.path.join("cache", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    import datetime
    now_str = datetime.datetime.now().strftime("%B %d, %Y - %I_%M%p")
    filename = f"Generated Audio {now_str}.wav"
    output_path = os.path.join(audio_dir, filename)
    
    try:
        from modules.voice_generator import generate_voice as generate_voice_narration
        generate_voice_narration(req.script_text, output_path, voice_name=req.voice_name, api_key=groq_key)
        return {"status": "success", "filename": filename, "path": output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en síntesis de voz: {e}")


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
        
    prompt = template.replace("{STORY}", story_text).replace("{story}", story_text)
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
        import re
        if provider == "gemini":
            from modules.gemini_client import generate_content as generate_gemini_content
            raw_text = generate_gemini_content(prompt, api_key, model_name="gemini-2.5-flash")
        else:
            from modules.groq_client import generate_content as generate_groq_content
            raw_text = generate_groq_content(prompt, api_key, model_name="llama-3.3-70b-versatile")
            
        # Parse output
        title_section_match = re.search(r"---T[ÍI]TULOS.*?---(.*?)(?=---DESCRIPCI[OÓ]N|$)", raw_text, re.DOTALL | re.IGNORECASE)
        desc_section_match = re.search(r"---DESCRIPCI[OÓ]N.*?---(.*)", raw_text, re.DOTALL | re.IGNORECASE)
        
        titles = []
        description = ""
        
        if title_section_match:
            lines = title_section_match.group(1).strip().split('\n')
            for line in lines:
                line_clean = re.sub(r"^\d+[\.\-\s]+", "", line.strip()).strip()
                line_clean = line_clean.strip("[] ")
                if line_clean:
                    titles.append(line_clean)
                    
        if desc_section_match:
            description = desc_section_match.group(1).strip()
            
        if not titles:
            for line in raw_text.split('\n'):
                line = line.strip()
                if line.startswith("1.") or line.startswith("2.") or line.startswith("3."):
                    titles.append(re.sub(r"^\d+[\.\-\s]+", "", line).strip("[] "))
                    
        if not titles:
            titles = ["Misterio Inexplicable 💀"]
        if not description:
            description = raw_text.strip()
            
        return {
            "status": "success",
            "titles": titles,
            "title": titles[0] if titles else "Misterio Inexplicable 💀",
            "description": description
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error llamando a la IA: {e}")


@router.get("/last-render")
def api_get_last_render(channel_name: Optional[str] = None):
    settings = get_settings()
    output_dir = settings.get("renders_folder_path") or os.path.join("projects", "renders")
    if not os.path.exists(output_dir):
        return {"status": "error", "message": "El directorio de renders no existe."}
    
    import glob
    mp4_files = glob.glob(os.path.join(output_dir, "*.mp4"))
    if not mp4_files:
        return {"status": "error", "message": "No hay videos renderizados."}
    
    # Ordenar por fecha de modificación (el más nuevo primero)
    mp4_files.sort(key=os.path.getmtime, reverse=True)
    
    # Si especifican channel_name, intentamos buscar el más reciente que contenga el nombre del canal
    if channel_name:
        channel_lower = channel_name.lower()
        for f in mp4_files:
            if channel_lower in os.path.basename(f).lower():
                return {
                    "status": "success",
                    "path": f,
                    "filename": os.path.basename(f)
                }
    
    # Si no hay ninguno con el nombre del canal o no se especificó, devolvemos el más reciente de todos
    latest_video = mp4_files[0]
    return {
        "status": "success",
        "path": latest_video,
        "filename": os.path.basename(latest_video)
    }

from pydantic import BaseModel
class ScriptGenerateTramaRequest(BaseModel):
    script: str

@router.post("/generate-trama-from-script")
def api_generate_trama_from_script(req: ScriptGenerateTramaRequest):
    if not req.script.strip():
        raise HTTPException(status_code=400, detail="El guion está vacío.")
    
    groq_key = get_groq_api_key()
    if not groq_key:
        raise HTTPException(status_code=400, detail="API Key de Groq no configurada.")
        
    prompt = f"""
Eres un asistente experto en videos cortos (TikTok/Shorts).
Tengo el siguiente guion de narración. Extrae la trama o idea principal en un máximo de 10 palabras (conciso). No incluyas nada más en tu respuesta.

GUION:
{req.script[:1500]}
"""
    try:
        trama = generate_groq_content(prompt, groq_key, model_name="llama-3.3-70b-versatile")
        return {"status": "success", "trama": trama.strip().replace('"', '')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar trama: {e}")
