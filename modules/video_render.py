import os
from modules.render_mix import render_mix_mode

def render_final_video(audio_path, images_paths, cover_path, output_folder, title, description, vhs_enabled, music_path=None, media_mode='mix', status_callback=None, groq_key=None, aspect_ratio='9:16', lut_name=None, sub_style='TikTok / Hormozi', reddit_card_title=None, pacing="Dinámico [2.0s]", vol_voice=100.0, vol_music=40.0, vol_sfx=100.0):
    """
    Enrutador unificado: Ahora todas las peticiones utilizan el motor de MIX,
    que es el más avanzado y soporta cualquier combinación de medios.
    """
    print(f">>> [ROUTER] Iniciando renderizado UNIFICADO (MIX) - Formato: {aspect_ratio} - Subtítulos: {sub_style}")
    
    # Independientemente del media_mode que llegue (por compatibilidad), usamos MIX
    return render_mix_mode(
        audio_path, images_paths, cover_path, output_folder, 
        title, description, vhs_enabled, music_path, status_callback, groq_key, aspect_ratio, lut_name, sub_style,
        reddit_card_title=reddit_card_title, pacing=pacing, vol_voice=vol_voice, vol_music=vol_music, vol_sfx=vol_sfx
    )
