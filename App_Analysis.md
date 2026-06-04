# SilencioRojoApp Codebase Analysis

### `d:\Descargas\SilencioRojoApp\analyze_app.py`

**Imports:** os, ast, json

**Functions:**
- **`analyze_python_file`**
- **`analyze_json_file`**
- **`main`**

---

### `d:\Descargas\SilencioRojoApp\main.pyw`

**Imports:** ui.main_window (from)

---

### `d:\Descargas\SilencioRojoApp\cache\json\data_mix.json`

**JSON Object with keys:** segments

---

### `d:\Descargas\SilencioRojoApp\cache\json\srt_cache_mix.json`

**JSON Object with keys:** original_audio_path, original_duration, audio_path, duration

---

### `d:\Descargas\SilencioRojoApp\config\client_secrets.json`

**JSON Object with keys:** installed

---

### `d:\Descargas\SilencioRojoApp\config\narrative_vars.json`

**JSON Object with keys:** ganchos, monstruos, atmosfera, cierres

---

### `d:\Descargas\SilencioRojoApp\config\prompts.py`

**Imports:** os, core.utils (from), json, json

**Functions:**
- **`list_prompts`**
  - *Doc:* Retorna una lista de archivos .txt en la carpeta de la categoría.
- **`load_settings_for_prompts`**
- **`update_paths_from_settings`**
- **`load_template`**
- **`save_narrative_vars`**
- **`load_narrative_vars`**

---

### `d:\Descargas\SilencioRojoApp\config\settings.json`

**JSON Object with keys:** google_api_key, audio_folder_path, images_folder_path, videos_folder_path, story_template, visual_template, cover_template, voice_template, groq_api_key, llm_provider

---

### `d:\Descargas\SilencioRojoApp\core\math_logic.py`

**Imports:** math

**Functions:**
- **`calculate_visual_segments`**
  - *Doc:* Regla de los 3 segundos:

---

### `d:\Descargas\SilencioRojoApp\core\project_manager.py`

**Imports:** json, os, time, datetime (from)

**Classes:**
- **`ProjectManager`**
  - *Methods:* __init__, create_project, save_project, load_project, list_projects, get_latest_project

---

### `d:\Descargas\SilencioRojoApp\core\utils.py`

**Imports:** os, sys

**Functions:**
- **`get_resource_path`**
  - *Doc:* Get absolute path to resource, works for dev and for PyInstaller 
- **`copy_to_clipboard_persistent`**
  - *Doc:* Copies text to the system clipboard in a persistent way (survives app exit).
- **`force_focus`**
  - *Doc:* Punch-through focus strategy:

---

### `d:\Descargas\SilencioRojoApp\modules\gemini_client.py`

**Imports:** google.generativeai, os

**Functions:**
- **`validate_api_key`**
  - *Doc:* Verifica si la API Key tiene el formato correcto (básico).
- **`generate_content`**
  - *Doc:* Envía el prompt a Google Gemini y retorna la respuesta de texto.

---

### `d:\Descargas\SilencioRojoApp\modules\groq_client.py`

**Imports:** os, groq (from)

**Functions:**
- **`validate_api_key`**
  - *Doc:* Verifica si la API Key tiene un formato básico válido.
- **`generate_content`**
  - *Doc:* Envía el prompt a Groq y retorna la respuesta de texto.

---

### `d:\Descargas\SilencioRojoApp\modules\render_long.py`

**Imports:** os, random, subprocess, json, time, traceback, concurrent.futures (from), modules.render_utils (from)

**Functions:**
- **`convert_to_phrase_ass`**
  - *Doc:* Toma la transcripción de Whisper del audio del capítulo y agrupa las palabras en
- **`render_chapter`**
  - *Doc:* Renderiza un único capítulo. Toma el guion de texto, el audio de voz, las imágenes/videos asignadas y
- **`render_long_video_project`**
  - *Doc:* Motor principal para renderizar videos largos en Silencio Rojo Core.

---

### `d:\Descargas\SilencioRojoApp\modules\render_mix.py`

**Imports:** os, subprocess, random, time, json, traceback, datetime (from), concurrent.futures (from), modules.render_utils (from)

**Functions:**
- **`apply_audio_speed_ramping`**
  - *Doc:* Aplica Speed Ramping al audio de narración basándose en las palabras
- **`render_mix_mode`**

---

### `d:\Descargas\SilencioRojoApp\modules\render_utils.py`

**Imports:** os, subprocess, json, time, groq (from)

**Functions:**
- **`detect_hardware_encoder`**
  - *Doc:* Detecta el mejor codificador de hardware disponible (QSV o software).
- **`transcribe_with_groq`**
  - *Doc:* Usa Groq Whisper-large-v3 para transcribir con timestamps.
- **`convert_to_word_by_word_srt`**
  - *Doc:* Convierte el JSON de Whisper a formato ASS (Advanced SubStation Alpha) con estilo Viral Pro.
- **`safe_remove`**
  - *Doc:* Elimina un archivo de forma segura manejando bloqueos de Windows.
- **`extract_sfx_events`**
  - *Doc:* Analiza el JSON de Whisper y retorna una lista de tuplas (sfx_path, start_time_sec)
- **`get_video_duration`**
  - *Doc:* Obtiene la duración de un archivo multimedia usando ffprobe.

---

### `d:\Descargas\SilencioRojoApp\modules\video_compositor.py`

**Imports:** cv2, numpy, os, logging, imageio

**Classes:**
- **`VideoCompositor`**
  - *Methods:* compose, compose_robust

---

### `d:\Descargas\SilencioRojoApp\modules\video_render.py`

**Imports:** os, modules.render_mix (from)

**Functions:**
- **`render_final_video`**
  - *Doc:* Enrutador unificado: Ahora todas las peticiones utilizan el motor de MIX,

---

### `d:\Descargas\SilencioRojoApp\modules\voice_generator.py`

**Imports:** os, wave, traceback

**Functions:**
- **`generate_voice`**
  - *Doc:* Genera audio a partir de texto utilizando Gemini (voz Charon)

---

### `d:\Descargas\SilencioRojoApp\modules\youtube_uploader.py`

**Imports:** os, pickle, socket, google_auth_oauthlib.flow (from), google.auth.transport.requests (from), googleapiclient.discovery (from), googleapiclient.http (from), googleapiclient.errors (from)

**Functions:**
- **`get_authenticated_service`**
  - *Doc:* Autentica al usuario y retorna el servicio de la API de YouTube.
- **`upload_video`**
  - *Doc:* Sube un video a YouTube con:

---

### `d:\Descargas\SilencioRojoApp\projects\20260212_184812_NewSession.json`

**JSON Object with keys:** concept, visual, cover, media, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\20260501_151600_AutoSave.json`

**JSON Object with keys:** concept, visual, cover, media, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\20260501_151911_AutoSave.json`

**JSON Object with keys:** concept, visual, cover, media, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\20260501_173537_AutoSave.json`

**JSON Object with keys:** concept, visual, cover, media, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\20260501_174842_AutoSave.json`

**JSON Object with keys:** concept, visual, cover, media, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\20260501_181257_AutoSave.json`

**JSON Object with keys:** concept, visual, cover, media, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\20260501_181437_AutoSave.json`

**JSON Object with keys:** concept, visual, cover, media, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\20260504_210333_AutoSave.json`

**JSON Object with keys:** concept, visual, cover, voice, media, long_form, _last_modified, _version

---

### `d:\Descargas\SilencioRojoApp\projects\videos_largos\nueva prueba\chunks\chapter_0_meta.json`

**JSON Object with keys:** guion, title, voice_audio, media, aspect_ratio, cache_version

---

### `d:\Descargas\SilencioRojoApp\projects\videos_largos\nueva prueba\chunks\chapter_1_meta.json`

**JSON Object with keys:** guion, title, voice_audio, media, aspect_ratio, cache_version

---

### `d:\Descargas\SilencioRojoApp\projects\videos_largos\nueva prueba\chunks\chapter_2_meta.json`

**JSON Object with keys:** guion, title, voice_audio, media, aspect_ratio, cache_version

---

### `d:\Descargas\SilencioRojoApp\projects\videos_largos\nueva prueba\chunks\chapter_3_meta.json`

**JSON Object with keys:** guion, title, voice_audio, media, aspect_ratio, cache_version

---

### `d:\Descargas\SilencioRojoApp\projects\videos_largos\nueva prueba\chunks\chapter_4_meta.json`

**JSON Object with keys:** guion, title, voice_audio, media, aspect_ratio, cache_version

---

### `d:\Descargas\SilencioRojoApp\projects\videos_largos\nueva prueba\chunks\chapter_5_meta.json`

**JSON Object with keys:** guion, title, voice_audio, media, aspect_ratio, cache_version

---

### `d:\Descargas\SilencioRojoApp\ui\config_editor.py`

**Imports:** customtkinter, os, webbrowser, config.prompts, core.utils (from)

**Classes:**
- **`ConfigEditor`**
  - *Methods:* __init__, setup_ui, create_nav_btn, show_tab, init_api_ui, get_template_files, init_prompts_ui, on_story_template_change, on_visual_template_change, on_cover_template_change, on_voice_template_change, init_paths_ui, browse_folder, create_editor, highlight_syntax, load_current_values, read_file_safe, save_all

---

### `d:\Descargas\SilencioRojoApp\ui\image_converter.py`

**Imports:** os, re, customtkinter, tkinter (from), PIL (from)

**Classes:**
- **`ImageConverter`**
  - *Methods:* __init__, init_ui, select_files, update_list, convert_files

---

### `d:\Descargas\SilencioRojoApp\ui\main_window.py`

**Imports:** os, random, threading, subprocess, webbrowser, json, customtkinter, tkinter (from), config.prompts, modules.video_render (from), modules (from), ui.narrative_editor (from), ui.tabs.media_tab (from), ui.components.sidebar (from), ui.tabs.concept_tab (from), ui.tabs.visual_tab (from), ui.tabs.long_tab (from), ui.tabs.voice_tab (from), core.project_manager (from), ui.tabs.cover_tab (from), ui.config_editor (from), ui.image_converter (from), core.utils (from), core.math_logic (from)

**Classes:**
- **`MainWindow`**
  - *Methods:* __init__, run_startup_sequence, preload_all_views, load_settings, save_settings_to_file, auto_load_session, auto_save_loop, on_close, save_current_state, restore_state, init_sidebar, init_main_area, animate_entrance, animate_status_pulse, show_view, animate_view_entrance, create_dashboard_view, create_interactive_card, action_new_story, action_open_dir, on_model_change, action_verify_paths, load_project_by_id, setup_brain_ui, setup_painter_ui, setup_cover_ui, setup_media_ui, open_config_editor, open_image_converter, open_narrative_editor, reset_ui, update_status, check_prompt_file

---

### `d:\Descargas\SilencioRojoApp\ui\narrative_editor.py`

**Imports:** customtkinter, itertools, config.prompts

**Classes:**
- **`NarrativeEditor`**
  - *Methods:* __init__, init_sidebar, init_content_area, load_data_to_editors, highlight_list_items, select_category, save_all

---

### `d:\Descargas\SilencioRojoApp\ui\visual_prompt_viewer.py`

**Imports:** customtkinter

**Classes:**
- **`VisualPromptViewer`**
  - *Methods:* __init__, setup_ui, parse_prompts, populate_list, _add_next_chunk, create_prompt_card, copy_text, copy_all

---

### `d:\Descargas\SilencioRojoApp\ui\components\sidebar.py`

**Imports:** customtkinter, webbrowser

**Classes:**
- **`Sidebar`**
  - *Methods:* __init__, check_real_width, setup_ui, create_nav_btn, create_util_btn, on_nav_click

---

### `d:\Descargas\SilencioRojoApp\ui\tabs\concept_tab.py`

**Imports:** customtkinter, threading, random, modules (from), config.prompts, core (from)

**Classes:**
- **`ConceptTab`**
  - *Methods:* __init__, setup_ui, run_generation_thread, run_generation, handle_generation_error, show_result, update_status, copy_output, copy_voice_instructions, get_state, restore_state

---

### `d:\Descargas\SilencioRojoApp\ui\tabs\cover_tab.py`

**Imports:** customtkinter, threading, modules (from), config.prompts

**Classes:**
- **`CoverTab`**
  - *Methods:* __init__, setup_ui, run_generation_thread, run_generation, on_success, update_status, copy_prompt, focus_set

---

### `d:\Descargas\SilencioRojoApp\ui\tabs\long_tab.py`

**Imports:** os, threading, json, random, re, customtkinter, tkinter (from), config.prompts, core (from), modules (from), modules.render_long (from)

**Classes:**
- **`LongTab`**
  - *Methods:* __init__, setup_ui, browse_output_folder, toggle_music_option, add_manual_chapter, clear_all_chapters, run_segmentation_thread, clean_json_string, segment_guion, on_segmentation_success, on_segmentation_error, rebuild_chapters_ui, delete_chapter, clear_chapter_cache, clear_project_cache, update_chapter_text, select_chapter_voice, add_chapter_media, clear_chapter_media, update_chapter_music, roll_chapter_music, refresh_music_dropdowns, run_render_thread, render_project_bg, update_render_status, update_status, on_render_success, on_render_error, get_state, restore_state, focus_set, update_chapter_title, open_voice_generator_dialog, center_toplevel

---

### `d:\Descargas\SilencioRojoApp\ui\tabs\media_tab.py`

**Imports:** customtkinter, os, threading, subprocess, random, tkinter (from), PIL (from), queue

**Classes:**
- **`MediaTab`**
  - *Methods:* __init__, check_layout_health, setup_ui, create_card, setup_left_panel, setup_right_panel, on_format_change, refresh_grid, process_thumbnails_async, process_thumbnail_queue, apply_thumbnail, select_audio, select_cover, on_media_type_change, select_media, clear_media, get_active_media, move_media, remove_media_item, sort_media, check_ready_state, animate_pulse_render, toggle_hook_options, refresh_hooks_list, refresh_music_list, on_music_manual_select, reroll_music, stop_preview, play_preview, get_active_media, on_render_click, run_render, update_render_status, on_upload_click, run_upload, get_state, restore_state, focus_set

---

### `d:\Descargas\SilencioRojoApp\ui\tabs\visual_tab.py`

**Imports:** customtkinter, threading, modules (from), config.prompts, core.math_logic (from), ui.visual_prompt_viewer (from)

**Classes:**
- **`VisualTab`**
  - *Methods:* __init__, setup_ui, update_segment_hint, run_generation_thread, run_generation, on_success, update_status, open_visual_editor, focus_set

---

### `d:\Descargas\SilencioRojoApp\ui\tabs\voice_tab.py`

**Imports:** os, threading, subprocess, customtkinter, tkinter.messagebox, modules (from)

**Classes:**
- **`VoiceTab`**
  - *Methods:* __init__, setup_ui, paste_from_clipboard, get_audio_folder, run_generation_thread, on_generation_success, on_generation_error, play_audio, open_audio_folder, get_state, restore_state, focus_set

---

