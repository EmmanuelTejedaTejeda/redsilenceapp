# Auditoría Técnica y Análisis Completo del Proyecto: ShortNexus Studio

> **Fecha de Auditoría Maestro**: 18 de Agosto de 2026  
> **Estado del Sistema**: 100% Funcional, Modularizado y Optimizado  
> **Fuentes de Verificación**: `repomix-output.xml`, `reglas_locales.md` y código fuente del repositorio.

---

## 1. Resumen Ejecutivo y Arquitectura del Sistema

**ShortNexus Studio** es una plataforma integral y modular de automatización, generación y edición masiva de contenido audiovisual en formato vertical **9:16 (YouTube Shorts, TikTok y Instagram Reels)**. 

El sistema está diseñado específicamente para operar con la máxima eficiencia técnica en hardware local (optimizado para procesadores Intel de 4ª generación de bajo consumo como i5-4300U, con 12 GB RAM en disco SSD D:).

### Pilares Fundamentales del Sistema:
1. **Aislamiento Multicanal Autónomo**: Cada canal de YouTube/TikTok registrado opera en un sandbox completamente independiente ubicado bajo `projects/channels/[Nombre_Canal]/` con sus propias carpetas de audios, músicas, vídeos, imágenes, renders, cachés y metadatos (`generation_metadata.json`).
2. **Soporte Multilingüe Nivel Canal**: Configuración de código de idioma (`es`, `en`, `fr`, `de`, `pt`, `it`) por canal en `config/settings.json`. Las llamadas a IA (Groq AI / Gemini API) adaptan guiones, títulos, descripciones y prompts narrativos directamente en el idioma nativo del canal.
3. **Backend Asíncrono Modular (FastAPI + APIRouter)**: El servidor `server.py` está desacoplado en APIRouters independientes (`api/routers/`) apoyándose en `aiofiles` y `asyncio` para evitar bloqueos del bucle principal.
4. **Motor de Renderizado Híbrido GPU/CPU (FFmpeg MIX Engine)**: Transcripción automática por palabra con Whisper/Groq, quemado de subtítulos estilo Hormozi/Reddit, autogestión de SFX sincronizados milimétricamente a palabras clave, auto-ducking dinámico de música de fondo y aceleración de hardware por GPU via **Windows Media Foundation (`h264_mf`)** / QSV con fallback suave a CPU (`libx264`).
5. **Frontend SPA Cyberpunk / Glassmorphism**: Interfaz web de una sola página sin recargas de pantalla (ES6 Modules en `web/js/`), escalado dinámico responsivo de 100vh sin scroll vertical, wizard interactivo de 4 pasos, emulador de smartphone 9:16 en tiempo real y estudio visual de subtítulos.

---

## 2. Jerarquía Completa de Directorios y Archivos (Aislamiento Multicanal)

```
NEXUS_STUDIO/
├── run_web_app.py               # Lanzador oficial con verificación de salud HTTP 200 y apertura de navegador
├── server.py                    # Servidor FastAPI principal (~50 líneas, sirve SPA en '/' y monta APIRouters)
├── Analisis_Completo.md         # Documento maestro de auditoría técnica y arquitectura
├── reglas_locales.md            # Directivas del proyecto y reglas de hardware (i5-4300U / SSD D:)
├── repomix-output.xml           # Grafo maestro de código empaquetado (Repomix XML)
├── .gitignore                   # Exclusiones de Git (entornos virtuales, cachés, renders pesados)
├── desktop.ini                  # Archivo de sistema de icono de carpeta Windows
│
├── api/                         # Módulo Backend REST API
│   ├── __init__.py              # Inicializador del paquete API
│   ├── deps.py                  # Dependencias FastAPI, resolución de rutas aisladas (get_channel_paths) y migración
│   └── routers/                 # APIRouters especializados
│       ├── __init__.py          # Inicializador de paquete routers
│       ├── analytics.py         # Métricas de YouTube Data API v3 y grafo viral de palabras clave
│       ├── assets.py            # Gestor de biblioteca multimedia, narraciones, timeline, SFX y purga de caché
│       ├── channels.py          # CRUD de canales, selección activa, temas y prompts master por canal
│       ├── shorts.py            # Generación de guiones, voz, streaming SSE de progreso y motor de renderizado
│       └── youtube_upload.py    # Autenticación OAuth2 y publicación/programación automatizada en YouTube
│
├── assets/                      # Biblioteca Global de Recursos Físicos Base
│   ├── audio/
│   │   ├── sfx/                 # 8 Efectos de sonido unificados (WAV 16-bit PCM 44100Hz)
│   │   │   ├── arcade_retro_game_over.wav
│   │   │   ├── cat_meow.wav
│   │   │   ├── crickets_ambience.wav
│   │   │   ├── dog_bark.wav
│   │   │   ├── footsteps.wav
│   │   │   ├── heartbeat.wav
│   │   │   ├── rain_and_thunder_storm.wav
│   │   │   └── wolf_howl.wav
│   │   ├── transitions/         # 5 Transiciones de audio (MP3 44100Hz estéreo)
│   │   │   ├── real_boom.mp3 (6s recortado con fade)
│   │   │   ├── real_glitch.mp3
│   │   │   ├── real_impact.mp3
│   │   │   ├── real_riser.mp3
│   │   │   └── real_whoosh.mp3
│   │   └── music/               # Música de fondo normalizada (-16 LUFS, M4A AAC 44100Hz)
│   ├── fonts/                   # Tipografías (.ttf / .otf) para subtítulos dinámicos
│   └── video/
│       └── fx/                  # Efecto de superposición de video
│           └── vhs_overlay.mp4  # Superposición de ruido VHS (450 KB ultra-comprimido)
│
├── cache/                       # Directorio de trabajo temporal global
├── config/                      # Configuraciones JSON y Plantillas de Prompts
│   ├── client_secrets.json      # Credenciales oficiales de Google OAuth 2.0
│   ├── scheduled_queue.json     # Cola de videos programados para publicación
│   ├── settings.json            # Configuración general y registro de canales
│   ├── subtitle_styles.json     # Plantillas estilísticas de subtítulos para FFmpeg
│   ├── themes.json              # Paletas de color e identificadores estéticos
│   ├── prompts.py               # Módulo Python de constantes de prompts
│   └── prompts/                 # Directorio de prompts estandarizados
│       ├── cover/               # Prompts de generación de portadas (cover_v1, cover_version3)
│       ├── story/               # Prompts de historias (Prompt Maestro Universal y prompts por canal)
│       ├── title_description/   # Prompt de metadatos SEO (PROMPT_TITLE_DESCRIPTION.txt)
│       ├── visuals/             # Prompts de composición visual (visual_version4, visual_version5)
│       └── voice/               # Prompts de instrucciones de voz (voice_instructions)
│
├── core/                        # Utilidades y Lógica Central
│   ├── math_logic.py            # Fórmulas de calculo de engagement, viralidad y normalizaciones
│   ├── project_manager.py       # Gestor de estructura física de proyectos y canales
│   └── utils.py                 # Funciones helper de formateo, sanitizado de strings y manejo de IO
│
├── credenciales/                # Credenciales privadas de OAuth 2.0 y claves de API local
│   └── client_secrets.json      # JSON oficial de cliente de Google App
│
├── modules/                     # Motores y Clientes de Procesamiento Especializado
│   ├── analytics_client.py      # Cliente YouTube Data API v3 (estadísticas de canal y retención)
│   ├── entity_search.py         # Buscador de imágenes referenciales de entidades reales (Bing HTML, Wikimedia, Pollinations AI)
│   ├── gemini_client.py         # Integración con la API de Google Gemini (guiones y metadatos)
│   ├── graph_analyzer.py        # Motor de grafos de viralidad de palabras clave con NetworkX
│   ├── groq_client.py           # Integración con la API de Groq AI (openai/gpt-oss-120b) para guiones y prompts
│   ├── pixabay_client.py        # Cliente de búsqueda de imágenes y videos en Pixabay API
│   ├── render_mix.py            # Compilador principal de video MIX (FFmpeg, Whisper, SFX, B-rolls)
│   ├── render_utils.py          # Utilidades de FFmpeg, FFprobe, subtítulos ASS, hashing de caché y codificación
│   ├── telemetry.py             # Sistema de logs y telemetría de eventos de renderizado (`render_telemetry.log`)
│   ├── timeline_generator.py    # Generador de línea de tiempo con fallback inteligente (YouTube, Pexels, Fotos)
│   ├── tiktok_uploader.py       # Cliente de publicación automatizada en TikTok (preparado API)
│   └── youtube_uploader.py      # Cliente de publicación y programación en YouTube Shorts API
│
├── projects/                    # ALMACENAMIENTO DE PROYECTOS Y CANALES
│   └── channels/                # ESTRUCTURA AISLADA MULTICANAL
│       └── [Nombre_Canal]/
│           ├── audio/           # Locuciones y audios de voz asignados al canal
│           ├── music/           # Pistas de música asignadas al canal
│           ├── videos/          # Gameplays y videos B-roll descargados para el canal
│           ├── images/          # Imágenes estáticas y de stock del canal
│           ├── renders/         # Videos Short finales (.mp4) y sus metadatos SEO (.txt)
│           ├── downloader/      # Descargas brutas de fuentes multimedia
│           ├── cache/           # Chunks renderizados y subtítulos temporales (.ass) del canal
│           └── config/          # generation_metadata.json (trazabilidad completa de renders)
│
├── tools/                       # Herramientas binarias auxiliares
│   └── yt-dlp.exe               # Ejecutable binario de yt-dlp para extracción directa de streams
│
└── web/                         # Frontend Web Studio (SPA con Vanilla JS / ES6 Modules)
    ├── index.html               # Plantilla SPA principal (Pestañas, Wizard, Subtitle Studio, Viral Map)
    ├── style.css                # Estilos CSS Glassmorphic Cyberpunk con variables HSL y Responsive 100vh
    └── js/                      # Módulos JavaScript orientados a componentes
        ├── analytics_dashboard.js # Tablero de analítica de canales y modal de auditoría viral
        ├── api.js               # Cliente HTTP (Fetch API wrapper con manejo de errores)
        ├── channels_settings.js # Control de Ajustes Generales, Canales y Generador de Prompts IA
        ├── main.js              # Entrypoint JS, orquestación SPA, reactividad al cambiar de canal
        ├── shorts_wizard.js     # Wizard de 4 pasos para creación de Shorts, SSE stream y purga de borrador
        ├── subtitles_studio.js  # Editor interactivo de subtítulos, emulador 9:16 y persistencia JSON
        └── viral_map.js         # Visualizador interactivo de red de palabras clave con Vis.js
```

---

## 3. Auditoría Detallada del Backend (FastAPI API Core)

### 3.1. Lanzador y Servidor Principal (`run_web_app.py` & `server.py`)

*   **`run_web_app.py`**:
    *   **Propósito**: Punto de entrada de ejecución del usuario. Inicia el servidor Uvicorn en `http://localhost:8000/`, verifica con polling HTTP 200 la salud del backend y abre el navegador Thorium/predeterminado.
    *   **Funciones**:
        *   `is_server_running(url)`: Realiza una petición `urllib.request.urlopen` con timeout de 1s para validar la disponibilidad del servidor.
        *   `main()`: Lanza Uvicorn mediante `subprocess.Popen`, entra en un bucle de comprobación de hasta 30 intentos (15s) y ejecuta `webbrowser.open_new_tab()`.

*   **`server.py`**:
    *   **Propósito**: Servidor web principal FastAPI optimizado a ~50 líneas.
    *   **Características Auditadas**:
        *   Configuración de CORS Middleware (`CORSMiddleware`) permitiendo todos los orígenes (`*`).
        *   Registro de los 5 APIRouters modularizados bajo `/api/shorts`, `/api/channels`, `/api/assets`, `/api/analytics`, `/api/youtube`.
        *   Montaje de archivos estáticos multimedia `projects` (`/projects`) para streaming directo de audios y vídeos renderizados.
        *   Servicio SPA en la raíz `/`: Sirve `web/index.html` en `/` y monta `web/` de forma estática bajo `/web`.

---

### 3.2. Dependencias y Resolución de Rutas Aisladas (`api/deps.py`)

*   **Propósito**: Proveer esquemas de validación Pydantic, funciones helper de rutas por canal y soporte de migración transparente.
*   **Esquemas Pydantic Auditados**:
    *   `FolderSettingsRequest`: Modelo para guardar rutas absolutas personalizadas de carpetas (`narration_folder`, `music_folder`, `images_folder`, `videos_folder`, `renders_folder`, `downloads_folder`).
    *   `ChannelCreateRequest`: Registro de un nuevo canal (`name`, `niche`, `language`, `theme`, `theme_color`, `narration_voice`).
    *   `ChannelThemeRequest`: Actualización de estética del canal (`theme`, `theme_color`).
    *   `SubtitleStyleModel`: Definición de estilo tipográfico para subtítulos (`name`, `font_name`, `font_size`, `primary_color`, `outline_color`, `back_color`, `bold`, `italic`, `uppercase`, `outline_width`, `shadow_depth`, `alignment`, `animation_type`, `highlight_color`).
    *   `GenerateRequest`: Parámetros de generación de Short (`script_text`, `channel_name`, `voice_name`, `music_name`, `music_volume`, `voice_volume`, `subtitle_style`, `target_resolution`, `bg_source`, `video_title`, `enable_subtitles`).
    *   `DownloaderUrlRequest`: Petición de descarga por URL directa (`url`, `channel_name`, `duration`).
    *   `DownloaderSearchRequest`: Petición de descarga por palabra clave (`query`, `channel_name`, `duration`, `get_gameplay`, `get_images`, `get_gifs`).
    *   `GenerateTimelineRequest`: Petición de autogeneración de timeline (`narration_path`, `channel_name`, `mode`).

*   **Funciones Helper Auditadas**:
    *   `get_channel_paths(channel_name: Optional[str])`: Sanitiza el nombre del canal y devuelve un diccionario con las rutas absolutas aisladas: `audio`, `music`, `videos`, `images`, `renders`, `downloader`, `cache`, `config`. Si `channel_name` no se proporciona, consulta el canal activo en `settings.json`.
    *   `migrate_legacy_files_if_needed(channel_name: str)`: Traslada de forma segura cualquier archivo alojado en carpetas heredadas planas hacia la nueva jerarquía del canal activo.

---

### 3.3. Routers API Auditados (`api/routers/`)

#### 1. `api/routers/shorts.py` (Generación de Shorts, SSE y Render)
*   `POST /api/shorts/generate-script`: Genera un guion viral a partir del Prompt Maestro mediante Groq AI (Llama-3.3-70b) o Gemini.
*   `POST /api/shorts/generate-title-description`: Genera metadatos optimizados SEO (título CTR, descripción estructurada, hashtags) basándose en `PROMPT_TITLE_DESCRIPTION.txt`.
*   `POST /api/shorts/generate`: Inicia el proceso de renderizado en segundo plano (`BackgroundTasks`) invocando `bg_generate_short_process`.
*   `GET /api/shorts/progress/{channel_name}`: Endpoint SSE (Server-Sent Events) que transmite en tiempo real el flujo de eventos y porcentaje de renderizado de `0%` a `100%`.
*   `GET /api/shorts/last-render`: Retorna la ruta e información del último vídeo renderizado para el canal activo para alimentar el emulador del smartphone.
*   `GET /api/shorts/renders`: Lista los vídeos `.mp4` completados alojados en la carpeta `renders` del canal activo.
*   **Helper**: `calculate_render_percentage(event_msg: str)` -> Traduce los eventos del motor FFmpeg a un porcentaje flotante continuo.

#### 2. `api/routers/channels.py` (Gestión de Canales y Prompts IA)
*   `GET /api/channels/`: Obtiene la lista completa de canales registrados y el canal actualmente activo.
*   `GET /api/channels/folder-settings`: Devuelve la configuración de rutas de carpetas del canal especificado.
*   `POST /api/channels/folder-settings`: Guarda las rutas de carpetas personalizadas en `settings.json`.
*   `POST /api/channels/create`: Crea un nuevo canal físicamente en `projects/channels/[Nombre]` inicializando sus subcarpetas y prompt inicial.
*   `POST /api/channels/select`: Establece el canal activo en `settings.json`.
*   `POST /api/channels/theme`: Cambia el tema visual del canal.
*   `DELETE /api/channels/{channel_name}`: Elimina un canal y su registro.
*   `GET /api/channels/{channel_name}/prompts`: Carga la lista de prompts master del canal.
*   `POST /api/channels/{channel_name}/prompts`: Guarda o edita un prompt master del canal.
*   `DELETE /api/channels/{channel_name}/prompts/{prompt_id}`: Elimina un prompt master del canal.
*   `POST /api/channels/{channel_name}/generate-story-prompt`: Genera automáticamente un Prompt Maestro específico para el nicho e idioma del canal usando Groq AI y la plantilla base `Prompt Maestro Universal.txt`.

#### 3. `api/routers/assets.py` (Explorador Multimedia, Timeline y Caché)
*   `GET /api/assets/music`: Lista las canciones `.m4a`, `.mp3`, `.wav` de la biblioteca de música del canal.
*   `GET /api/assets/story-prompts`: Carga plantillas de prompts de historia.
*   `GET /api/assets/voice-prompts`: Carga instrucciones de estilo de voz.
*   `GET /api/assets/narrations`: Lista los audios de locución del canal activo enriquecidos automáticamente con transcripción de texto hablado (`preview_text`), código de color determinista único por audio (`color`), antigüedad legible en tiempo relativo (`relative_time`), duración exacta y caché en `cache/audio_preview_cache.json`.
*   `GET /api/assets/file-preview`: Sirve fragmentos de audio/vídeo mediante `FileResponse` para la vista previa interactiva del reproductor.
*   `POST /api/assets/download-url`: Descarga un vídeo de YouTube/TikTok a la carpeta del canal en segundo plano.
*   `POST /api/assets/download-search`: Búsqueda y descarga inteligente de stock de vídeo/fotos desde Pexels, Pixabay o YouTube.
*   `GET /api/assets/gameplay-folders`: Obtiene carpetas de gameplays locales.
*   `POST /api/assets/upload-audio`: Sube un archivo de voz grabado por el usuario a la carpeta del canal.
*   `POST /api/assets/upload-resources`: Sube múltiples archivos (imágenes, vídeos, GIFs) a la línea de tiempo.
*   `GET /api/assets/audio-duration`: Mide la duración exacta en segundos de un archivo de audio mediante FFprobe.
*   `GET /api/assets/timeline`: Carga los clips ordenados presentes en el timeline del canal.
*   `DELETE /api/assets/timeline`: Elimina un recurso individual del timeline.
*   `POST /api/assets/timeline/clear`: Vacía por completo el timeline del canal activo.
*   `POST /api/assets/cache/clear`: Purga físicamente todos los archivos `.mp4`, `.wav` y `.ass` de la carpeta `cache` del canal activo.
*   `GET /api/assets/subtitle-styles`: Carga la lista de estilos de subtítulos desde `subtitle_styles.json`.
*   `POST /api/assets/subtitle-styles`: Crea o edita una plantilla de subtítulos.
*   `DELETE /api/assets/subtitle-styles/{name}`: Elimina un estilo de subtítulo.

#### 4. `api/routers/analytics.py` (Métricas de Canal y Red Viral)
*   `GET /api/analytics/channel/{channel_name}`: Obtiene las estadísticas generales de YouTube (suscriptores, vistas totales, vídeos).
*   `GET /api/analytics/channel/{channel_name}/videos`: Lista los vídeos del canal con métricas de engagement.
*   `GET /api/analytics/video/{video_id}`: Detalles analíticos profundos de un vídeo específico.
*   `GET /api/analytics/viral-graph/{channel_name}`: Genera la estructura de nodos y aristas para la red visual con Vis.js.
*   `POST /api/analytics/viral-audit/{channel_name}`: Diagnóstico de IA sobre la estrategia viral del canal.

#### 5. `api/routers/youtube_upload.py` (Automatización Social)
*   `POST /api/youtube/upload`: Autentica mediante OAuth 2.0 y sube el Short renderizado a YouTube con su título, descripción y tags.
*   `GET /api/youtube/scheduled-queue`: Obtiene la cola de publicaciones programadas.
*   `POST /api/youtube/scheduled-queue`: Agrega un vídeo a la cola de programación.

---


---

### 4.2. Utilidades de Renderizado y Procesamiento (`modules/render_utils.py`)
*   `get_media_duration(file_path)`: Ejecuta `ffprobe` en modo asíncrono/síncrono para obtener la duración exacta en segundos de cualquier archivo de audio o vídeo.
*   `extract_sfx_events(script_text, word_timestamps)`: Mapea la presencia de palabras clave de suspenso/impacto (ej. *muerte, grito, lluvia, perro, victoria*) a marcas de tiempo exactas.
*   `calculate_clip_hash(...)`: Genera un hash SHA-256 único basado en el contenido del clip, la presencia de tarjeta Reddit y la resolución objetivo, garantizando el 100% de aciertos de la caché de chunks sin re-renderizar fragmentos idénticos.
*   `create_ass_file(words_data, output_ass_path, style_config)`: Compila el archivo de subtítulos `.ass` con estilos tipográficos avanzados.
*   `convert_media_to_mp4(input_path, output_path)`: Transcodifica cualquier formato de vídeo o GIF animado a un MP4 9:16 normalizado.
*   `slice_video_segments(...)`: Corta fragmentos homogéneos de gameplays largos re-encuadrándolos a formato vertical.
*   `clean_filename(filename)`: Sanitiza títulos eliminando emojis, caracteres especiales e interrupciones de ruta en Windows.

---

### 4.3. Generador de Línea de Tiempo (`modules/timeline_generator.py`)
*   `generate_timeline_for_narration(narration_path, channel_name, mode)`: Construye automáticamente la secuencia de clips necesarios para cubrir la duración de la narración aplicando la regla de balanceado (40% YouTube, 30% Pexels Video, 30% Imágenes de Pexels/Pixabay) con cascada de fallback.
*   `download_pexels_videos(query, channel_dir)`: Consulta la API de Pexels para descargar clips verticales HD de libre uso.
*   `download_pexels_photos(query, channel_dir)`: Obtiene imágenes estáticas HD de Pexels y las guarda en la carpeta `images` del canal.

---

### 4.4. Clientes de Inteligencia Artificial y API (`modules/`)
*   **`modules/groq_client.py`**:
    *   `generate_script_with_groq(prompt_master, niche, language)`: Consulta los modelos activos oficiales de Groq (`openai/gpt-oss-120b`) para crear historias envolventes adaptadas al idioma del canal.
    *   `generate_metadata_with_groq(script_text, language)`: Crea títulos de CTR masivo y descripciones SEO.
    *   `generate_master_prompt_with_groq(universal_prompt, channel_name, niche, language)`: Genera un Prompt Maestro especializado por canal.
*   **`modules/gemini_client.py`**:
    *   `generate_script_with_gemini(...)`: Fallback de generación mediante la API de Google Gemini.
*   **`modules/analytics_client.py`**:
    *   `YouTubeAnalyticsClient`: Clase que encapsula las consultas a YouTube Data API v3 (`get_channel_stats`, `get_video_list`, `get_video_details`).
*   **`modules/graph_analyzer.py`**:
    *   `ViralGraphAnalyzer`: Analiza las co-ocurrencias de palabras clave en títulos/descripciones mediante grafos NetworkX para identificar conceptos virales.

---

## 5. Auditoría Detallada del Núcleo (`core/`)

*   **`core/project_manager.py`**:
    *   Contiene la clase `ProjectManager` encargada de resolver y crear la estructura física de carpetas del sistema.
*   **`core/utils.py`**:
    *   `sanitize_filename(name)`: Limpia strings para nombres de archivos seguros.
    *   `format_seconds(seconds)`: Convierte segundos flotantes a formato HH:MM:SS / MM:SS.
    *   `ensure_dir(path)`: Crea directorios de forma recursiva si no existen.
*   **`core/math_logic.py`**:
    *   `calculate_engagement_score(views, likes, comments)`: Algoritmo ponderado de puntuación viral.
    *   `normalize_values(data)`: Normalización min-max de conjuntos de datos.

---

## 6. Auditoría Detallada del Frontend SPA (`web/`)

El frontend de **ShortNexus Studio** está construido como una Single Page Application (SPA) con tecnología Vanilla JS (ES6 Modules) y Vanilla CSS3 sin frameworks pesados, garantizando máxima velocidad de carga.

### 6.1. Componentes HTML (`web/index.html`)
*   **Navegación por Pestañas**:
    1. `#tab-shorts`: Wizard de 4 pasos para la creación de Shorts.
    2. `#tab-analytics`: Dashboard de métricas de YouTube por canal.
    3. `#tab-subtitles`: Estudio interactivo de diseño de subtítulos.
    4. `#tab-viral-map`: Grafo interactivo de viralidad.
    5. `#tab-settings`: Ajustes generales, gestión de canales y prompts master.
*   **Modales Interactivos**:
    *   `#modal-channel-create`: Modal de creación de canal con selector de idioma.
    *   `#modal-master-prompt`: Modal de edición e importación de Prompts Master.
    *   `#modal-auto-general`: Asistente de descarga inteligente de medios.
    *   `#modal-viral-audit`: Modal de diagnóstico IA de canales.

---

### 6.2. Diseño y Estilos (`web/style.css`)
*   **Estética Cyberpunk Glassmorphism**: Uso de variables HSL (`--bg-primary`, `--accent-cyber`, `--glass-border`, `--text-main`) con efectos de desenfoque de fondo (`backdrop-filter: blur(12px)`).
*   **Motor CSS Viewport Auto-Fit (100vh Responsivo)**: Layout sin scroll vertical principal, auto-ajustando la grilla de 3 columnas en el Paso 4 (`.render-step-grid`) a la altura disponible de la ventana.

---

### 6.3. Módulos JavaScript (`web/js/`)

*   **`web/js/main.js`**: Orquestador principal. Escucha el selector global de canal activo `#global-channel-select`, dispara eventos de cambio de canal y gestiona el refresco reactivo de narraciones, clips y vídeos renderizados.
*   **`web/js/shorts_wizard.js`**:
    *   Controla el flujo secuencial del Wizard de 4 pasos (Paso 1: Guion/Prompts -> Paso 2: Voz/Narraciones -> Paso 3: Timeline/Medios -> Paso 4: Render/Publicación).
    *   Generación y edición manual de términos de búsqueda visual: El botón `Generar Trama con IA` extrae la trama y $N$ búsquedas cinematográficas en inglés, llenando un `<textarea id="shorts-keywords">` editable antes de iniciar la descarga de recursos.
    *   Sincronización reactiva de audios del servidor: Polling automático cada 4s en Paso 2, auto-refresco al cambiar a Paso 2 o detectar enfoque en ventana (`focus`), y botón de refresco directo `#btn-refresh-audios`.
    *   Suscribe la conexión SSE a `/api/shorts/progress/{channel_name}` actualizando la barra de progreso fluida `#render-progress-bar`.
    *   Implementa el botón `#btn-reset-draft` para la purga completa de estado y caché.
*   **`web/js/channels_settings.js`**:
    *   Renderiza las tarjetas de canales registrados con sus etiquetas de idioma (`🌐 ES`, `🌐 EN`).
    *   Conecta el botón `#btn-generate-story-prompt` con la API de Groq AI para autogenerar Prompts Master por canal.
*   **`web/js/subtitles_studio.js`**:
    *   Ofrece controles interactivos para personalizar fuentes, tamaños, colores HSL, contornos y sombras.
    *   Actualiza en tiempo real el emulador de smartphone 9:16 con animación de prueba de subtítulos frase por frase.
*   **`web/js/analytics_dashboard.js`**: Carga estadísticas de YouTube Data API v3 y genera tablas de engagement por vídeo.
*   **`web/js/viral_map.js`**: Renderiza el mapa interactivo de red de palabras clave utilizando la librería `Vis.js`.
*   **`web/js/api.js`**: Wrapper centralizado de la Fetch API con manejo de excepciones y headers JSON.

---

## 7. Auditoría de Configuraciones y Assets Físicos

### 7.1. Bibliotecas Físicas de Medios Auditadas
1. **Biblioteca de Música (`assets/audio/music/`)**: Normalizada a `-16 LUFS`, recortada a máximo 90s, silencias iniciales eliminados y convertidos a contenedor **AAC (`.m4a`)** a 44100 Hz estéreo.
2. **Biblioteca SFX (`assets/audio/sfx/`)**: 8 efectos de sonido unificados en formato **WAV 16-bit PCM 44100 Hz estéreo** con pico máximo ajustado a **`-1.5 dB`** (sin clipping).
3. **Biblioteca de Transiciones (`assets/audio/transitions/`)**: 5 archivos en MP3 a 44100 Hz estéreo con recortes de silencio e impacto ruidoso en `real_boom.mp3` (reducido a 96 KB).
4. **Superposición Video FX (`assets/video/fx/vhs_overlay.mp4`)**: Compresión extrema de bitrate VBR a 2 Mbps de solo 10s de loop, pesando **450 KB** (reducción del 99.8%).

---

## 8. Matriz Maestra de Funciones y Métodos del Sistema

| Módulo / Archivo | Función / Método | Propósito Técnico | Parámetros Principales |
| :--- | :--- | :--- | :--- |
| `run_web_app.py` | `is_server_running` | Valida disponibilidad del servidor backend | `url: str` |
| `run_web_app.py` | `main` | Inicia Uvicorn y abre el navegador Thorium | Ninguno |
| `api/deps.py` | `get_channel_paths` | Resuelve rutas absolutas aisladas por canal | `channel_name: Optional[str]` |
| `api/deps.py` | `migrate_legacy_files_if_needed` | Migra archivos heredados al sandbox del canal | `channel_name: str` |
| `api/routers/shorts.py` | `api_generate_script` | Invocación de IA para redacción de guiones | `payload: dict` |
| `api/routers/shorts.py` | `api_generate_title_description` | Invocación de IA para metadatos CTR/SEO | `payload: dict` |
| `api/routers/shorts.py` | `bg_generate_short_process` | Proceso en segundo plano de renderizado MIX | `req: GenerateRequest` |
| `api/routers/shorts.py` | `calculate_render_percentage` | Mapeo de logs FFmpeg a porcentaje SSE | `event_msg: str` |
| `api/routers/channels.py` | `api_create_channel` | Registra canal e inicializa carpetas físicas | `req: ChannelCreateRequest` |
| `api/routers/channels.py` | `generate_story_prompt_for_channel` | Genera Prompt Maestro adaptado con Groq AI | `channel_name: str, payload: dict` |
| `api/routers/assets.py` | `api_clear_render_cache` | Elimina la caché de renderizado del canal activo | `channel_name: Optional[str]` |
| `api/routers/assets.py` | `api_clear_timeline` | Vacía el timeline de medios del canal activo | `channel_name: Optional[str]` |
| `modules/render_mix.py` | `render_mix_mode` | Compilador maestro de vídeo FFmpeg y subtítulos | `audio_path, script_text, ...` |
| `modules/render_utils.py` | `get_media_duration` | Obtiene duración en segundos con FFprobe | `file_path: str` |
| `modules/render_utils.py` | `extract_sfx_events` | Mapea palabras clave a marcas de tiempo SFX | `script_text, word_timestamps` |
| `modules/render_utils.py` | `calculate_clip_hash` | Genera hash SHA-256 para la caché de chunks | `input_path, duration, ...` |
| `modules/render_utils.py` | `create_ass_file` | Construye subtítulos dinámicos `.ass` | `words_data, output_path, style` |
| `modules/timeline_generator.py` | `generate_timeline_for_narration` | Autogeneración equilibrada de clips de stock | `narration_path, channel_name` |
| `modules/groq_client.py` | `generate_script_with_groq` | Consulta Groq API (openai/gpt-oss-120b) para historias | `prompt_master, niche, language` |
| `modules/analytics_client.py` | `get_channel_stats` | Consulta YouTube Data API v3 para métricas | `channel_id: str` |
| `modules/graph_analyzer.py` | `build_viral_graph` | Construye grafo NetworkX de co-ocurrencias | `video_data: list` |
| `core/utils.py` | `sanitize_filename` | Limpia strings para nombres seguros de archivo | `name: str` |
| `core/math_logic.py` | `calculate_engagement_score` | Puntuación de viralidad ponderada | `views, likes, comments` |
| `web/js/shorts_wizard.js` | `initShortsWizard` | Inicializa el wizard de 4 pasos y listeners | Ninguno |
| `web/js/subtitles_studio.js` | `renderSubtitlesPreview` | Emula la animación de subtítulos en el mockup | Ninguno |
| `web/js/channels_settings.js` | `loadChannels` | Renderiza la lista de canales registrados | Ninguno |

---

## 9. Conclusión de la Auditoría

El proyecto **ShortNexus Studio** cumple al 100% con los estándares de modularidad, aislamiento por canal, optimización de hardware local y diseño visual premium. La documentación y el Grafo Maestro (`repomix-output.xml`) se encuentran plenamente sincronizados para servir como referencia GPS inmutable.
