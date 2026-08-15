import cv2
import numpy as np
import os
import logging
import imageio

# Configuración básica de logging si no existe
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VideoCompositor")

class VideoCompositor:
    def compose(self, background_path, overlay_path, output_path, progress_callback=None):
        """
        Superpone un video con transparencia (overlay) sobre un fondo (imagen o video).
        Este método es un wrapper hacia compose_robust que es la implementación preferida.
        """
        return self.compose_robust(background_path, overlay_path, output_path, progress_callback)

    def compose_robust(self, background_path, overlay_path, output_path, progress_callback=None):
        """
        Versión robusta usando ImageIO para asegurar lectura de Alpha.
        Soluciona problemas donde OpenCV (vía ffmpeg backend) ignora el canal alpha en algunos WebM.
        """
        logger.info(f"Compositing Robust: {os.path.basename(background_path)} + {os.path.basename(overlay_path)}")
        
        reader_overlay = None
        reader_bg = None
        writer = None
        
        try:
             # Intentar forzar lectura RGBA para no perder el canal alpha
             try:
                 reader_overlay = imageio.get_reader(overlay_path, pixelformat='rgba')
             except TypeError:
                 # Fallback si version vieja no soporta pixelformat arg o es irrelevante
                 logger.warning("pixelformat arg not supported in get_reader or error, falling back default")
                 reader_overlay = imageio.get_reader(overlay_path)

             meta = reader_overlay.get_meta_data()
             detected_fps = meta.get('fps', 30)
             logger.info(f"Overlay Input FPS: {detected_fps}")
             
             # Sanitize FPS to avoid stuttering from VFR or bad metadata
             fps = float(detected_fps)
             if fps < 20 or fps > 62: # Allow 60fps (sometimes 60.00xxx)
                 logger.warning(f"FPS {fps} fuera de rango normal (20-60). Forzando 30 FPS para evitar lag.")
                 fps = 30.0
             
             # Log shape del primer frame para debug
             try:
                first_frame = reader_overlay.get_data(0)
                logger.info(f"Overlay Frame Shape detected: {first_frame.shape}")
             except:
                pass
            
             # Usamos iterador para saber total frames si es posible, o estimado
             # ImageIO a veces no da nframes exacto en streams.
             # Intentamos obtener duración probando
             try:
                 total_frames = int(reader_overlay.count_frames())
             except:
                 total_frames = 100 # Dummy fallback
                 
             # Fondo
             bg_ext = os.path.splitext(background_path)[1].lower()
             is_bg_video = bg_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif']
             
             bg_image = None
             bg_iter = None
             
             if is_bg_video:
                reader_bg = imageio.get_reader(background_path)
                bg_iter = iter(reader_bg)
             else:
                bg_image = imageio.imread(background_path)

             # Writer - Usamos libx264 para mejor compatibilidad MP4
             # Agregamos preset y CRF para encoding standard
             writer = imageio.get_writer(output_path, fps=fps, codec='libx264', pixelformat='yuv420p', macro_block_size=None, ffmpeg_params=['-preset', 'fast', '-crf', '23'])
            
             frame_idx = 0
             # Iterar sobre el overlay (que manda en duración)
             for frame_ov in reader_overlay:
                # frame_ov es RGB o RGBA (ImageIO standard)
                height, width = frame_ov.shape[:2]
                
                # Obtener frame fondo
                frame_bg = None
                if is_bg_video:
                    try:
                        frame_bg = next(bg_iter)
                    except StopIteration:
                        # Loop video fondo: reabrir
                        reader_bg.close()
                        reader_bg = imageio.get_reader(background_path)
                        bg_iter = iter(reader_bg)
                        frame_bg = next(bg_iter)
                    
                    # Resize video frame every time
                    if frame_bg.shape[:2] != (height, width):
                        frame_bg = cv2.resize(frame_bg, (width, height))
                else:
                    # Aplicar ZOOM BASE de 1.1x (Regla de Oro del Horror)
                    # Si ya está en caché con el tamaño correcto, no recalculamos, pero
                    # la lógica de zoom debe ejecutarse al menos una vez por imagen única.
                    if bg_image.shape[:2] != (height, width):
                        # 1. Redimensionar al tamaño del canvas
                        bg_resized = cv2.resize(bg_image, (width, height))
                        
                        # 2. Aplicar zoom del 10% (1.1x)
                        z_factor = 1.1
                        new_h, new_w = int(height * z_factor), int(width * z_factor)
                        bg_temp = cv2.resize(bg_resized, (new_w, new_h))
                        
                        # 3. Cortar el centro para volver a (height, width)
                        start_y = (new_h - height) // 2
                        start_x = (new_w - width) // 2
                        bg_image = bg_temp[start_y:start_y+height, start_x:start_x+width]
                    
                    frame_bg = bg_image
                
                # Composición
                composite = None
                
                # Verificar canal Alpha
                has_alpha = False
                if frame_ov.shape[2] == 4:
                    has_alpha = True
                
                if has_alpha:
                    # Tiene Alpha Real
                    alpha = frame_ov[:, :, 3].astype(float) / 255.0
                    alpha = np.stack([alpha]*3, axis=2) # 3 canales para multiplicar RGB
                    
                    foreground = frame_ov[:, :, :3].astype(float)
                    # Asegurar que fondo tiene 3 canales (quitando alpha si tuviera)
                    background = frame_bg[:, :, :3].astype(float)
                    
                    composite = (foreground * alpha + background * (1.0 - alpha)).astype(np.uint8)
                else:
                    # Sin Alpha detectado (posible error de lectura o video sin alpha).
                    # Intentar Fallback: Luma Key (Asumir negro = transparente)
                    if frame_idx == 0:
                        logger.warning("Overlay sin canal Alpha detectado. Aplicando Luma Key (Fondo Negro -> Transparente)")
                    
                    # Convertir a escala de grises para mascara
                    # frame_ov es RGB
                    gray = np.dot(frame_ov[...,:3], [0.2989, 0.5870, 0.1140])
                    
                    # Crear mascara suave
                    # Pixeles negros puros (0) son transparentes.
                    # Pixeles brillantes son opacos.
                    mask = np.clip((gray - 10) / 20.0, 0, 1) # Soft threshold
                    alpha = np.stack([mask]*3, axis=2)
                    
                    foreground = frame_ov[:, :, :3].astype(float)
                    background = frame_bg[:, :, :3].astype(float)
                    
                    composite = (foreground * alpha + background * (1.0 - alpha)).astype(np.uint8)
                
                writer.append_data(composite)
                
                frame_idx += 1
                if progress_callback and total_frames > 0:
                     progress_callback(frame_idx / total_frames)
                     
             logger.info(f"Composición finalizada: {frame_idx} frames procesados.")
             return True

        except Exception as e:
            logger.error(f"Error en composición: {e}")
            import traceback
            traceback.print_exc()
            return False # Indicar fallo
        finally:
            if reader_overlay: reader_overlay.close()
            if reader_bg: reader_bg.close()
            if writer: writer.close()
