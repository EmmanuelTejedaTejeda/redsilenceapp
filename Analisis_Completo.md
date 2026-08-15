# Análisis Completo del Proyecto: ShortNexus Studio

## 1. Resumen Ejecutivo
**ShortNexus Studio** es un sistema 100% enfocado en la **Aplicación Web Studio** para la automatización, generación y edición de contenido audiovisual en **YouTube Shorts** y **TikTok** de alto impacto viral a través de múltiples canales (historias de Reddit, terror analógico, terror psicológico, misterios y Roblox).

El proyecto ha sido completamente refactorizado y modularizado siguiendo las mejores prácticas de ingeniería de software:
- **Backend Modularizado (FastAPI APIRouter)**: [server.py](file:///d:/DESAROLLO/NEXUS_STUDIO/server.py) reducido a ~50 líneas, delegando responsabilidades a routers especializados en [api/routers/](file:///d:/DESAROLLO/NEXUS_STUDIO/api/routers) y sirviendo los archivos estáticos en la raíz (`/`) con soporte SPA.
- **Frontend Modularizado (ES6 Modules)**: `web/app.js` sustituido por módulos limpios en [web/js/](file:///d:/DESAROLLO/NEXUS_STUDIO/web/js).
- **Esquema Pydantic `FolderSettingsRequest` y Rutas Dinámicas**:
  1. Corregida la definición de `FolderSettingsRequest` en [api/deps.py](file:///d:/DESAROLLO/NEXUS_STUDIO/api/deps.py) eliminando los campos `theme` y `theme_color` que requerían erróneamente un atributo no relacionado al guardar carpetas.
  2. Guardado exitoso de rutas absolutas de narración, música, imágenes, vídeos, renders y descargas en `settings.json`.
  3. **Conexión de Rutas al Backend**: Se vincularon las rutas personalizadas de settings en los APIRouters de assets y shorts, permitiendo que la música, videos de fondo y renders finales utilicen las carpetas del usuario de forma nativa en lugar de directorios relativos hardcodeados.
- **Estudio de Subtítulos Avanzado (Subtitles Studio)**:
  1. **Editor de Estilo Completo**: Módulo visual interactivo (`#tab-subtitles`) para modificar tipografía (fuentes, tamaño 9:16 y 16:9, negrita/cursiva, casing), colores de texto, contorno (outline), sombra (back color), resaltado y animaciones pop-in.
  2. **Emulador de Smartphone 9:16**: Mockup telefónico detallado con notch y scanlines VHS que muestra los cambios estilográficos en tiempo real con fondos variables de gameplay y suspenso.
  3. **Transición Segmentada por Comas**: Caja de pruebas que permite simular la transición animada de los subtítulos frase por frase (separada por comas) con timers JavaScript en tiempo real.
  4. **Persistencia e Integración de Compilador**: Endpoints `/api/assets/subtitle-styles` para CRUD de plantillas personalizadas en `config/subtitle_styles.json` que el motor FFMPEG en `modules/render_utils.py` carga de forma dinámica para renderizar los videos físicos resultantes.
- **Integración y Estabilización del Wizard de Shorts**:
  1. Vinculación del botón de generación de guiones mediante IA con el endpoint `/api/shorts/generate-script`.
  2. Corrección en el mapeo de IDs del DOM en frontend (`shorts-master-prompt` and `shorts-script`) resolviendo el bloqueo del wizard.
  3. Adición de `voice_name` y `bg_source` al esquema `GenerateRequest` para solventar un error `NameError` de variable no definida en el renderizado en segundo plano y personalizar el fondo del video.
  4. Sincronización del streaming SSE de progreso con el nombre del canal activo `/api/shorts/progress/{channel_name}`.
  5. **Barra de Progreso Dinámica de Renderizado**: Se implementó una lógica de mapeo y estimación de porcentaje en la función `calculate_render_percentage` dentro de [api/routers/shorts.py](file:///d:/DESAROLLO/NEXUS_STUDIO/api/routers/shorts.py). El lambda callback captura los eventos internos del motor de renderizado MIX (como el recorte del audio, subtitulado, descargas de B-rolls, procesamiento secuencial de cada clip, mezclas y guardado final), traduciéndolos a porcentajes continuos en tiempo real (de `75%` a `100%`) que alimentan directamente a la barra de progreso de la UI, en lugar de pasar abruptamente de `0%` a `100%`.
  6. **Nombres Únicos de Render por Título SEO**: Se incorporó el campo `video_title` en `GenerateRequest` para transferir el título generado por IA (o editado manualmente) desde `#shorts-video-title` en el frontend al compilador. El motor de renderizado MIX limpia el título de caracteres especiales y emojis para guardar el archivo `.mp4` y su descripción `.txt` con un nombre representativo y único de su contenido en lugar de usar nombres de plantilla genéricos.
  6. **Audios del Servidor y Reproductor Premium**: Implementación de un endpoint `/api/assets/narrations` para listar audios de voz y `/api/assets/file-preview` para transmitirlos de forma segura. El Reproductor de Voz izquierdo se ha acoplado interactivamente con la selección activa, auto-cargándose (en estado pausado listo) al iniciar la app o cambiar de selección, mostrando animaciones de ondas sincronizadas.
  7. **Vista Previa de Video Persistente**: Creación del endpoint `/api/shorts/last-render` para obtener el video renderizado más reciente (filtrado por el canal activo o global) desde la ruta física configurada por el usuario, evitando pérdida de estado del smartphone tras reiniciar la app.
  8. **Subida y Programación en YouTube**: Vinculación y control interactivo del botón `btn-upload-youtube` con el endpoint del backend `POST /api/youtube/upload`, el cual se habilita automáticamente al renderizar o detectar un short persistido.
  9. **Activación Condicional de Subtítulos**: Se añadió el campo `enable_subtitles` en `GenerateRequest` controlado por un checkbox (`#shorts-enable-subtitles`) persistido en `localStorage` (por defecto desactivado). Cuando los subtítulos están desactivados, el motor de renderizado MIX omite por completo la transcripción por IA (Groq/Whisper) y la generación del archivo `.ass`, acelerando el renderizado de forma significativa al normalizar directamente el audio y omitir el quemado en FFmpeg.
  10. **Botón Nuevo Short (Limpiar Todo y Caches)**: Vinculado e implementado el botón `#btn-reset-draft` para realizar un reinicio general y purga de estado:
     *   **Frontend**: Borra el estado del wizard en `localStorage`, limpia variables globales y restablece los campos en pantalla (entradas de texto, selects, reproductor de audio, consola de compilación, previsualizador de video).
     *   **Downloader**: Limpia las URLs de descarga, la lista de videos encontrados, la consola de logs del descargador y oculta los paneles de progreso.
     *   **Backend**: Invoca `POST /api/assets/timeline/clear` para borrar del disco los recursos cargados en el timeline, actualizando su cuadrícula en pantalla de inmediato, e invoca `POST /api/assets/cache/clear` en [api/routers/assets.py](file:///d:/DESAROLLO/NEXUS_STUDIO/api/routers/assets.py) para purgar de forma física toda la caché de renderizado del servido- **Optimización Física de Biblioteca de Música (M4A / AAC Nativo)**:
  1. **Pre-procesamiento Físico**: Se normalizó la sonoridad de todas las canciones de fondo a `-16 LUFS` (filtro `loudnorm`) y se recortó el silencio inicial de cada pista (filtro `silenceremove=start_threshold=-45dB`). Además, se eliminó la estática/siseo residual mediante el filtro FFT De-noise (`afftdn=nr=18:nf=-45`) y se atenuó la ganancia en `-5 dB` para eliminar clipping digital y evitar saturar las voces.
  2. **Acotación Temporal**: Se limitó la duración máxima de cada pista a **90 segundos** exactos, reduciendo de forma significativa el peso de lectura del disco SSD D: (el archivo más pesado bajó de 45 MB a ~1.46 MB) y liberando RAM.
  3. **Códec y Canales Unificados**: Se convirtieron los archivos de MP3 a formato contenedor nativo **AAC (`.m4a`)** a **44100 Hz y 2 canales (Estéreo)**, eliminando la necesidad de resampleo en caliente por parte de FFmpeg y mejorando la velocidad del render final.
  4. **Modificación del Listador**: Se actualizó el endpoint `/api/assets/music` en [api/routers/assets.py](file:///D:/DESAROLLO/NEXUS_STUDIO/api/routers/assets.py) para que busque y liste de forma nativa archivos con extensión `.m4a` adicionalmente a `.mp3`, `.wav` y `.ogg`.
- **Optimización Física de Biblioteca de Transiciones de Audio (MP3 a 44100 Hz)**:
  1. **Alineación de Frecuencia**: Se re-codificaron las 5 transiciones físicas de audio (`real_boom.mp3`, `real_glitch.mp3`, `real_impact.mp3`, `real_riser.mp3` y `real_whoosh.mp3`) de su frecuencia original de 48000 Hz a **44100 Hz estéreo (2 canales)** de forma nativa. Esto elimina la necesidad de resampleo dinámico (`aresample`) por FFmpeg al inyectar transiciones en el Short final.
  2. **Recorte de Impacto Ruidoso**: Se limitó físicamente la duración de la pista pesada `real_boom.mp3` de **173 segundos (casi 3 minutos)** a solo **6 segundos** con un desvanecimiento suave (`afade=t=out:st=4.5:d=1.5`). Esto redujo su peso en disco de 1.28 MB a **96 KB**, acelerando radicalmente el tiempo de lectura y decodificación de FFmpeg durante la mezcla.
- **Optimización Física de Biblioteca de Efectos de Sonido (SFX WAV) y Rediseño de Mezcla Cinematográfica**:
  1. **Recorte Milimétrico**: Se eliminó el silencio inicial en las 13 pistas de efectos de sonido originales mediante el filtro `silenceremove` de FFmpeg (umbral `-45dB`), garantizando su inyección instantánea sin micro-retrasos.
  2. **Normalización de Pico en Dos Pasos**: Se analizó la amplitud de cada archivo con `volumedetect` para aplicar una escala lineal de ganancia exacta que sitúe el pico máximo de todos los efectos en **`-1.5 dB`**. Esto evita saturaciones (clipping) al mezclarse con las voces.
  3. **Unificación a 16-bit PCM**: Se re-codificaron todos los archivos a formato WAV unificado a **16 bits (`pcm_s16le`)** y 44100 Hz estéreo, lo que redujo el tamaño de almacenamiento en un **33%** para los archivos que estaban en 24 bits, optimizando el uso de RAM al decodificar.
  4. **Purga de Archivos Huérfanos**: Se eliminaron físicamente los 5 efectos de sonido (`air_woosh.wav`, `arrow_whoosh.wav`, `cinematic_tunnel_reverb_woosh.wav`, `fast_sweep.wav` y `rocket_whoosh.wav`) que existían en el disco pero no contaban con lógica de inyección reactiva en el código, dejando una biblioteca limpia de exactamente 8 efectos sincronizados al 100% con `sfx_map` en [render_utils.py](file:///D:/DESAROLLO/NEXUS_STUDIO/modules/render_utils.py).
  5. **Sincronización Word-Level (Pilar 2)**: Se actualizó `extract_sfx_events` en [render_utils.py](file:///D:/DESAROLLO/NEXUS_STUDIO/modules/render_utils.py) para mapear los timestamps de los efectos al milisegundo exacto de la pronunciación de la palabra clave a nivel de palabra (Whisper word-timestamps), incorporando una interpolación proporcional como fallback dinámico.
  6. **Clasificación y Mezcla en Capas (Pilar 1 y 3)**:
     - *SFX de Ambiente (Lluvia, grillos, pasos)*: Se procesan en bucle continuo (`-stream_loop -1`) a volumen muy bajo (`volume=0.08`), aplicando fundidos cruzados (*fade-in* y *fade-out* de 2 segundos) para transiciones fluidas de ambiente, y limitando a un solo ambiente activo a la vez para no saturar.
     - *SFX de Impacto (Ladrido, latido, etc.)*: Se reproducen una sola vez (one-shot) a volumen controlado (`volume=0.22` max) limitándolos a un máximo de un impacto cada 3 segundos.
  7. **Auto-Ducking de Música de Fondo (Pilar 4)**: Se implementó un filtro de volumen dinámico en `render_mix.py` para la música de fondo que atenúa de forma automática un 50% extra su volumen durante 1.8 segundos cada vez que se dispara un SFX de impacto fuerte en el Short final mediante cláusulas matemáticas `between()` en FFmpeg.
- **Optimización Física de Biblioteca de Efectos de Video (Video FX)**:
  1. **Compresión Extrema de Ruido de VHS**: Se optimizó físicamente el archivo de superposición analógica [vhs_overlay.mp4](file:///D:/DESAROLLO/NEXUS_STUDIO/assets/video/fx/vhs_overlay.mp4) de su tamaño original de **253.5 MB** a solo **0.45 MB** (450 KB), logrando una reducción de peso total del **99.8%**. Esto se consiguió limitando de forma estricta el bitrate de la señal de ruido de alta entropía a 2 Mbps VBR (`-b:v 2000k -maxrate 2500k -bufsize 4000k`), recortándolo a 10 segundos de loop y eliminando la pista de audio muerta. Esto erradica por completo la sobrecarga de RAM y el cuello de botella de decodificación al renderizar chunks en la laptop Dell Latitude.
- **Rediseño Premium y Estructura Visual del Paso 4 (Render y Publicación)**:`.mp3`, `.wav` y `.ogg`.
- **Rediseño Premium y Estructura Visual del Paso 4 (Render y Publicación)**:
  1. **Simetría y Altura Coordinada (Sin Scroll)**: Rediseñada la grilla de tres columnas (`.render-step-grid`) en [web/index.html](file:///d:/DESAROLLO/NEXUS_STUDIO/web/index.html) eliminando la altura mínima restrictiva y ajustando el padding a `12px 14px` con gaps compactos de `8px`. Esto permite que todos los paneles quepan en una sola pantalla sin necesidad de hacer scroll vertical.
  2. **Switch Toggle Cyberpunk y Panel Limpio**: Sustituido el checkbox desalineado de activación de subtítulos por un control interactivo de Switch Toggle compacto y removida la tarjeta redundante de previsualización de subtítulos para un panel de compilación más limpio e intuitivo.
  3. **Smartphone Mockup Compacto**: Redimensionado el previsualizador del smartphone (`.phone-mockup-wrapper` en [web/style.css](file:///d:/DESAROLLO/NEXUS_STUDIO/web/style.css)) a `180px` de ancho y `320px` de alto (proporción 9:16 exacta), con notch integrado y controles de reproducción ("PLAY" y "CARPETA") alineados perfectamente a la base con un ancho máximo de `180px` y botones de `24px` de alto.
  4. **Distribución y Descripción Monospace**: Rediseñado el panel de distribución con un textarea de descripción de `75px` de alto, fuente tipográfica `monospace` y fondo atenuado. Todos los select e inputs del formulario fueron estilizados a `28px` de altura de control, y los botones principales a `32px` con efectos hover y transformaciones táctiles premium.
- **Deduplicación de Motor de Render**: Centralizadas todas las funciones de ffprobe y medios en [modules/render_utils.py](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/render_utils.py).
- **Estabilización y Optimización de Renderizado (720p, Hardware Accelerated GPU via MediaFoundation / QSV / CPU)**: Se configuró el pipeline para detectar dinámicamente la aceleración por hardware del sistema en [modules/render_utils.py](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/render_utils.py). En procesadores Intel Haswell (i5-4300U) donde `h264_qsv` falla por incompatibilidad de sesión MFX en versiones recientes de FFmpeg, el sistema activa automáticamente **Windows Media Foundation (`h264_mf`)** configurado con `-rate_control quality -quality 85`, permitiendo aceleración por GPU mediante los transformadores MFT de Windows D3D11 y reduciendo un **42% el peso del archivo final** sin perder calidad visual. Se mantiene un fallback automático a CPU (`libx264`) si ninguna GPU responde. Se implementó un límite estricto de framerate a **30 FPS** (`-r 30` en chunks y salida final) que reduce la carga del procesador y el peso del video. La compresión H.264 se optimizó utilizando bitrate de 2200k, estructura GOP extendida (`-g 90`) y `-movflags +faststart` para optimizar la reproducción inmediata en la web (Shorts/TikTok).
- **Backend Optimizado para I/O Asíncrono**: Refactorización profunda de las rutas API (en `api/routers/channels.py`, `assets.py` y `deps.py`) implementando `aiofiles` y `async def` para lecturas y escrituras asíncronas de configuraciones y archivos temporales, evitando el bloqueo del ThreadPool de FastAPI bajo altas cargas y reduciendo el consumo de memoria de Python.
- **Limpieza Proactiva del Motor JS**: El frontend ha sido actualizado para revocar dinámicamente URLs temporales de Blob (`URL.revokeObjectURL`) y purgar nodos de imagen y video (`src=""` seguido de `.load()`) al presionar "Nuevo Short", liberando la RAM en el motor V8 de Thorium al instante.
- **Estabilización de Caché de Subtítulos y Clips (Multi-capa & Hash Inteligente)**: 
  1. Corregido el bug en [modules/render_mix.py](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/render_mix.py) donde la caché fallaba debido a la recreación del audio temporal `trimmed_voice.wav`.
  2. **Hash de Clips Optimizado**: Se reemplazó el parámetro `sub_style` del cálculo del hash del clip por una bandera booleana `has_card` (que detecta si el fragmento contiene la tarjeta de Reddit en el clip inicial). Esto previene que cambiar los estilos de subtítulo invalide el renderizado de vídeo de los fragmentos, acelerando re-renderizados a segundos.
  3. **Seguridad de Relación de Aspecto**: Se incorporó el mapeo de `target_w` y `target_h` en el hash de caché de fragmentos para asegurar la correcta invalidación ante cambios de resolución.
  4. **Duraciones Dinámicas Deterministas**: Se implementó una semilla fija basada en el hash del título del Short (`random.seed(seed)`) antes de la asignación aleatoria de duraciones de clips en el compilador. Esto garantiza que las duraciones físicas asignadas a cada chunk sean idénticas entre compilaciones consecutivas del mismo Short, asegurando un 100% de aciertos de caché (hits) y evitando re-renderizados innecesarios desde cero.
  5. **Robustez en la Importación del Generador de Hashes**: Corregido el conflicto de scope local en la función de procesamiento de chunks (`process_chunk`) en [modules/render_mix.py](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/render_mix.py) al eliminar una importación redundante local de `hashlib` que causaba `UnboundLocalError` cuando el medio de entrada no requería conversión al vuelo (rutas de imágenes y videos limpios sin ser GIFs o WebP animados).
- **Normalización de Biblioteca SFX e Integración Dinámica**:
  1. **Limpieza Física**: Renombrados los 14 archivos de efectos de sonido en `assets/audio/sfx/` eliminando prefijos de plataformas de descarga (`mixkit-`) y sufijos numéricos aleatorios, adoptando una nomenclatura estandarizada en minúsculas con guiones bajos (p. ej. `footsteps.wav` y `heartbeat.wav`).
  2. **Actualización de Mapeos de Audio**: Sincronizado el archivo [modules/render_utils.py](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/render_utils.py) para utilizar los nuevos formatos de archivo correspondientes a la inyección automática por palabras clave en los guiones.
  3. **Expansión del Detector de Suspenso**: Incorporadas nuevas palabras clave como `lluvia/tormenta/trueno` (`rain_and_thunder_storm.wav`), `perro/ladrar/ladrido` (`dog_bark.wav`), `retro/perdiste` (`arcade_retro_game_over.wav`), `grillo/grillos` (`crickets_ambience.wav`), y `vacío/vacio` (`air_zoom_vacuum.wav`) para enriquecer las mezclas de audio reactivas en base al texto.
- **Asistentes Multimedia Interactivos**:
  1. **Modal de Auto General** (`#modal-auto-general`) y **Gameplay Genérico** (`#modal-gameplay-generic`) habilitados y rediseñados estéticamente sin campos de duración manual, auto-ajustando y recortando dinámicamente según la narración activa.
  2. **Descargador de Fondos Inteligente e IA (Timeline Fallback)**: El backend ahora implementa una caché para reutilizar descargas de YouTube completas y ejecuta segmentación con re-encuadre vertical 9:16 (`slice_video_segments`) de forma automatizada. Adicionalmente, el timeline implementa una **búsqueda y descarga con distribución balanceada en base al índice (40% YouTube, 30% Pexels Video, 30% Imagen)**:
     - *YouTube Video (40% de prioridad base)*: Busca vídeos cortos de stock en YouTube (con `yt-dlp`), los descarga a 720p y extrae dinámicamente un fragmento reproducible de 3 segundos manejando offsets inteligentes para clips cortos.
     - *Pexels Video (30% de prioridad base)*: Busca vídeos verticales de stock en Pexels.
     - *Imagen (30% de prioridad base)*: Busca fotos en Pexels/Pixabay y las anima con zoom/paneo.
     - *Cascada de Fallback*: Si la fuente asignada por índice falla, el sistema consulta el resto de las plataformas automáticamente para asegurar que el Timeline nunca quede incompleto.
     
     Los recursos se guardan respetando su tipo original: los vídeos en `videos_folder_path` y las imágenes fijas en `images_folder_path` con su extensión correspondiente (`.jpg`, `.png`, `.mp4`, etc.). La UI del timeline detecta el tipo al vuelo y renderiza las imágenes y vídeos adecuadamente.
     
     Se configuró `yt-dlp` con la directiva `'nopart': True` para omitir archivos temporales y la descarga segmentada de los primeros 5 minutos (`download_ranges`) del video fuente, evitando el consumo masivo de red y disco por videos extremadamente largos en Windows. El backend autodetecta y elimina de forma reactiva videos de gameplay corruptos o incompletos de la caché mediante comprobación de duración de FFprobe. Además, el motor de segmentación valida que cada fragmento generado sea mayor a 10 KB; si se detecta un clip corrupto o vacío, elimina automáticamente el video fuente de la caché local para forzar su redescarga limpia. Asimismo, el API del timeline devuelve rutas con barras normales (`/`) previniendo errores de escape en Javascript y fallos de previsualización (404 Not Found) en el cliente. Para evitar bloqueos físicos de eliminación en Windows (WinError 32), la UI vacía las etiquetas multimedia (`src = ''` y `.load()`) del DOM del navegador antes de solicitar limpieza, y el backend ejecuta recolección de basura asíncrona (`gc.collect()`) y reintentos robustos (`safe_remove`) al borrar recursos o caché. Adicionalmente, el Asistente General de Medios lee de forma reactiva los checkboxes de recursos a obtener (gameplay, imágenes y GIFs) en el envío del frontend, y el backend implementa búsquedas dinámicas mediante API de Pexels (fotos) y Giphy (GIFs animados) para integrarlos de inmediato al timeline del Short según los intereses del usuario. Asimismo, el compilador de shorts (`bg_generate_short_process`) fue optimizado para recopilar secuencialmente todos los formatos de medios del timeline (videos, GIFs e imágenes) como fondos principales del renderizado MIX final, respetando el orden alfabético que ve el usuario en la interfaz y alternando adecuadamente entre ellos en lugar de restringirse únicamente a archivos de formato de video (`.mp4`), solucionando los saltos omitidos de recursos multimedia. Para lograr un flujo de edición natural y dinámico sin saltos hacia atrás ("efecto rebote de overlays"), el motor de renderizado MIX (`render_mix_mode`) ahora intercala cronológica y secuencialmente los B-rolls descargados de Pexels/YouTube en la pista de fondo principal en lugar de superponerlos como overlays temporales encima de otros clips, lo que elimina el retorno al clip original y genera transiciones fluidas de corte a corte. Por último, para evitar que fallas de extracción de audio (como en videos de gameplay de Roblox mudos o sin pista de audio) provoquen que los chunks de video sean omitidos por completo del compilador final, el motor de renderizado MIX captura la excepción de FFmpeg y autogenera un flujo de audio silencioso en formato WAV (`anullsrc`), rescatando y conservando la pista de video en el Short. De manera complementaria, para evitar que la imagen del video se congele al final de la reproducción por ser más corta que la pista de narración de audio o por cortes desiguales, se incorporó la directiva `-stream_loop -1` de forma dinámica en las llamadas FFMPEG de video y extracción de audio, forzando a que cualquier video de entrada más corto se repita en bucle hasta cubrir con precisión matemática su duración asignada (`render_dur`), y la directiva `-loop 1` para las imágenes fijas en el timeline, lo que previene que FFMPEG cierre prematuramente el stream tras el primer frame y congele la imagen en los segundos finales. A su vez, se optimizó el algoritmo de intercalación de B-rolls para que actúe de forma circular y repita la secuencia de recursos del timeline de fondo si estos se agotan antes de cubrir la duración total de la voz. Asimismo, para compensar la pérdida de duración acumulada por los encabalgamientos de transiciones cruzadas (`xfade`), el compilador calcula de forma anticipada los offsets de las transiciones y escala dinámicamente la duración física de cada chunk de video y especialmente del último chunk, forzando a que el stream de video de salida dure más de los segundos estipulados y evitando cualquier congelamiento en los segundos finales del Short.
  3. **Línea de Tiempo (Timeline) Dinámica**: Creación de los endpoints `GET`, `DELETE` y `/clear` bajo `/api/assets/timeline` para gestionar los recursos, y el endpoint `POST` `/api/assets/upload-resources` para subir múltiples archivos del usuario (videos, imágenes, GIFs) directamente a la línea de tiempo, mapeándolos dinámicamente según su formato. Se añadió un filtrado estricto en el frontend para evitar que los mensajes del render final del Short interfieran en la barra de estado del timeline, asegurando que esta sección solo muestre información limpia relativa a la adición/eliminación de sus propios clips.
  4. Endpoint `/api/assets/gameplay-folders` para obtener dinámicamente las carpetas de gameplays locales.
- **Sintetizador y Carga de Audios en Tiempo Real**:
  1. Endpoint `/api/shorts/synthesize-voice` para generar audios del guion al instante usando Edge-TTS.
  2. Endpoint `/api/assets/upload-audio` para subir grabaciones locales a la carpeta del servidor.
  3. Cierre automático de modales y recarga fluida del listado de audios destacando el archivo resultante al instante sin refrescar la página.
- **Generación Automática de Metadatos y Trazabilidad (Metadata Tracking)**:
  1. Endpoint `/api/shorts/generate-title-description` que utiliza el prompt estructurado en `PROMPT_TITLE_DESCRIPTION.txt` para crear títulos de CTR masivo y descripciones optimizadas en capas.
  2. Disparo asíncrono e inteligente de la IA al generar un guion, sintetizar una voz, o manualmente desde el Paso 4.
  3. Selección dinámica y priorizada de clips de fondo en el compilador filtrando por la palabra clave del `bg_source` activo.
  4. **Trazabilidad de Parámetros de Generación**: Implementación del archivo caché local `generation_metadata.json` (alojado en `config/cache/`) para persistir todos los parámetros técnicos (Prompt Master, Script/Trama completo, duraciones, clips, volumen de voz/música, tipo de subtítulos, calidad, etc.) vinculados unívocamente a cada Short renderizado mediante su `safe_title`. El backend en `/api/analytics/video-details/{video_id}` realiza un cruce dinámico por título con este archivo para inyectar estos parámetros generados directamente al modal de "Detalles de Video" en la interfaz web, permitiendo auditoría técnica en tiempo real.

---

## 2. Arquitectura Modular del Sistema

```
                                +---------------------------------------+
                                |      ShortNexus Web Studio App        |
                                |       (ES6 Modules / web/js/)         |
                                +-------------------+-------------------+
                                                    |
                                                    | REST API / SSE Progress
                                          +---------v---------+
                                          |   FastAPI Server  |
                                          |    (server.py)    |
                                          +---------+---------+
                                                    |
         +------------------------------------------+------------------------------------------+
         |                                          |                                          |
+--------v-------+                         +--------v-------+                         +--------v-------+
|  api/routers/  |                         | AI & Voice     |                         | Video Engine   |
| - shorts.py    |                         | - groq_client  |                         | - render_mix   |
| - channels.py  |                         | - gemini_client|                         | - video_render |
| - analytics.py |                         | - voice_gen    |                         | - compositor   |
| - assets.py    |                         +----------------+                         +----------------+
+----------------+                                  |                                          |
        |                                  +--------v-------+                         +--------v-------+
        |                                  | Social & OAuth |                         | Gameplay Scrap |
        |                                  | - yt_uploader  |                         | - roblox_sourc |
        |                                  | - tiktok_up    |                         | - gameplay_sou |
        |                                  | - analytics    |                         | - pexels/pixab |
        +--------------------------------->+----------------+                         +----------------+
```

---

## 3. Tecnologías y Stack Técnico (Verificado en `repomix-output.xml`)

| Capa / Módulo | Tecnología / Librería | Función |
| :--- | :--- | :--- |
| **Backend API** | FastAPI, APIRouter, Uvicorn, Pydantic, asyncio | Servidor RESTful modularizado por rutas (`api/routers/`) con eventos Server-Sent Events (SSE) para progreso en tiempo real y montado directo de frontend en la raíz. |
| **Lanzador Oficial** | `run_web_app.py` | Inicia el servidor Uvicorn en `http://localhost:8000/`, ejecuta polling activo de salud HTTP 200 para confirmar el inicio 100% completo del backend y abre de forma segura el navegador web. |
| **Frontend Web Studio** | HTML5, Vanilla CSS3 Glassmorphism, JS (ES6 Modules) | Panel de control studio desacoplado por características (`shorts_wizard.js`, `channels_settings.js`, `analytics_dashboard.js`, `viral_map.js`, `subtitles_studio.js`). |
| **Generación de Contenido AI**| Groq API (Llama models), Google Gemini API | Generación de guiones virales, metadatos (título/descripción/hashtags) y prompts visuales. |
| **Síntesis de Voz (TTS)** | Edge-TTS, Kokoro TTS, ElevenLabs | Generación de narraciones en múltiples voces e idiomas (ES, EN, FR, DE, IT). |
| **Procesamiento de Vídeo** | MoviePy, FFMPEG, OpenCV, PIL/Pillow | Ensamblado de vídeo 9:16, subtítulos dinámicos estilo Hormozi, Reddit History y Roblox Gaming, LUTs de color, VHS y subliminales. |
| **Descarga de Recursos** | `yt-dlp`, Pexels API, Pixabay API | Obtención y segmentación de fondistas (Roblox, Parkour, GTA, Minecraft) y stock mediático. |
| **Automatización Social** | Google OAuth 2.0 (`google-api-python-client`), TikTok API | Programación y subida automática multicanal de YouTube Shorts y TikTok. |
| **Analítica y Métricas** | YouTube Data API v3, NetworkX / Vis.js | Captura de estadísticas por canal y generación del mapa viral de rendimiento. |

---

## 4. Estructura de Directorios del Proyecto (Estructura Modularizada)

```
supergenerador/
├── run_web_app.py         # Lanzador principal del servidor Web
├── server.py              # Servidor FastAPI principal (~50 líneas, monta APIRouters y static en '/')
├── Analisis_Completo.md   # Documento de análisis técnico
├── reglas_locales.md      # Reglas y directivas locales del proyecto
├── repomix-output.xml     # Grafo maestro de código (170k tokens)
├── api/                   # Módulo de backend modularizado
│   ├── deps.py            # Dependencias comunes, modelos Pydantic y colas SSE
│   └── routers/           # APIRouters independientes
│       ├── channels.py    # Gestión de canales y prompts master
│       ├── shorts.py      # Generación de guiones, voz, render y SSE
│       ├── analytics.py   # Estadísticas y mapa de viralidad
│       └── assets.py      # Explorador de música, voz, descargas y subtítulos custom
├── assets/                # Fuentes, audios base, SFX, vídeos de fondo
├── cache/                 # Directorios de trabajo dinámicos (limpios)
├── config/                # Prompts estandarizados, settings, tokens OAuth2 y subtitle_styles.json
├── core/                  # project_manager, math_logic, utils
├── credenciales/          # client_secrets.json oficiales
├── modules/               # Motores IA, voz, render, uploader, analytics
├── projects/renders/      # Directorio de salida para los Shorts renderizados
├── tools/                 # yt-dlp.exe
└── web/                   # Frontend Web Studio (ES6 Modules)
    ├── index.html         # Panel principal SPA
    ├── style.css          # Estilos Glassmorphic
    └── js/                # Módulos JavaScript orientados a características
        ├── main.js        # Punto de entrada principal ES6
        ├── api.js         # Cliente de llamadas HTTP REST
        ├── shorts_wizard.js # Wizard de 4 pasos para la creación de Shorts
        ├── subtitles_studio.js # Editor y emulador de subtítulos custom
        ├── channels_settings.js # Gestión de canales y prompts master
        ├── analytics_dashboard.js # Gráficos Chart.js y estadísticas
        └── viral_map.js   # Grafo de viralidad Vis.js e informe IA
```
