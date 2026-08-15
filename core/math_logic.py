import math

def calculate_visual_segments(audio_duration_seconds):
    """
    Regla del ritmo visual agresivo (Pacing < 1.5s):
    Calcula cuántos segmentos visuales se necesitan
    para cubrir la duración del audio con cortes rápidos.
    Lógica: Ceiling(duration / 1.2)
    """
    if audio_duration_seconds <= 0:
        return 0
    return math.ceil(audio_duration_seconds / 1.2)
