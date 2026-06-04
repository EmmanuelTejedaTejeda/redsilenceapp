import math

def calculate_visual_segments(audio_duration_seconds):
    """
    Regla de los 3 segundos:
    Calcula cuántos segmentos visuales (imágenes) se necesitan
    para cubrir la duración del audio con cortes rápidos.
    Lógica: Ceiling(duration / 3.0)
    """
    if audio_duration_seconds <= 0:
        return 0
    return math.ceil(audio_duration_seconds / 3.0)
