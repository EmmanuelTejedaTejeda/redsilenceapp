import os



# --- TEMPLATE PATHS ---
from core.utils import get_resource_path

# --- SETTINGS LOADING ---
import json
SETTINGS_PATH = "config/settings.json"
PROMPTS_ROOT = "config/prompts"

DEFAULT_STORY_FILE = "TERROR_ANALOGICO_EXTREMO.txt"
DEFAULT_VISUAL_FILE = "visual_version5.txt"
DEFAULT_COVER_FILE = "cover_version3.txt"
DEFAULT_VOICE_FILE = "voice_instructions2.txt"

def list_prompts(category):
    """Retorna una lista de archivos .txt en la carpeta de la categoría."""
    path = get_resource_path(os.path.join(PROMPTS_ROOT, category))
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if f.endswith(".txt")]

def load_settings_for_prompts():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def update_paths_from_settings():
    global STORY_TEMPLATE_PATH, VISUAL_TEMPLATE_PATH, COVER_TEMPLATE_PATH, VOICE_TEMPLATE_PATH
    global STORY_PROMPT_TEMPLATE, VISUAL_PROMPT_TEMPLATE, COVER_PROMPT_TEMPLATE, VOICE_PROMPT_TEMPLATE
    global DEFAULT_PROMPT
    
    settings = load_settings_for_prompts()
    
    def get_safe_path(category, filename, default):
        # 1. Intentar con el nombre solicitado
        path = get_resource_path(os.path.join(PROMPTS_ROOT, category, filename))
        if os.path.exists(path): return path
        
        # 2. Intentar con el default
        path_def = get_resource_path(os.path.join(PROMPTS_ROOT, category, default))
        if os.path.exists(path_def): return path_def
        
        # 3. Fallback al primer .txt que encuentre
        available = list_prompts(category)
        if available:
            return get_resource_path(os.path.join(PROMPTS_ROOT, category, available[0]))
        
        return path # Retornar el original aunque no exista para que de el error controlado

    story_file = settings.get("story_template", DEFAULT_STORY_FILE)
    visual_file = settings.get("visual_template", DEFAULT_VISUAL_FILE)
    cover_file = settings.get("cover_template", DEFAULT_COVER_FILE)
    voice_file = settings.get("voice_template", DEFAULT_VOICE_FILE)
    
    STORY_TEMPLATE_PATH = get_safe_path("story", story_file, DEFAULT_STORY_FILE)
    VISUAL_TEMPLATE_PATH = get_safe_path("visuals", visual_file, DEFAULT_VISUAL_FILE)
    COVER_TEMPLATE_PATH = get_safe_path("cover", cover_file, DEFAULT_COVER_FILE)
    VOICE_TEMPLATE_PATH = get_safe_path("voice", voice_file, DEFAULT_VOICE_FILE)
    
    STORY_PROMPT_TEMPLATE = load_template(STORY_TEMPLATE_PATH, "ERROR: Template not found for Story.")
    VISUAL_PROMPT_TEMPLATE = load_template(VISUAL_TEMPLATE_PATH, "ERROR: Template not found for Visuals.")
    COVER_PROMPT_TEMPLATE = load_template(COVER_TEMPLATE_PATH, "ERROR: Template not found for Cover.")
    VOICE_PROMPT_TEMPLATE = load_template(VOICE_TEMPLATE_PATH, "ERROR: Template not found for Voice.")
    DEFAULT_PROMPT = STORY_PROMPT_TEMPLATE

def load_template(path, fallback=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading template {path}: {e}")
        return fallback

# Iniciar paths la primera vez
update_paths_from_settings()

# --- VARIABLES DE ALEATORIEDAD NARRATIVA - SILENCIO ROJO ---
import json

NARRATIVE_VARS_PATH = os.path.join("config", "narrative_vars.json")

# DEFAULTS
DEFAULT_GANCHOS = [
    "TIPO A (La Advertencia): Empieza con un imperativo negativo. El protagonista ya cometió el error y advierte al espectador. (Ej: 'No abras la puerta', 'Jamás contestes').",
    "TIPO B (El Hallazgo): El protagonista encontró algo extraño (cinta, objeto, lugar) y lo describe con fascinación morbosa antes de que todo salga mal.",
    "TIPO C (In Media Res): La historia empieza a mitad de una persecución. Sin explicaciones, solo respiración agitada, ruido de pasos y pánico total.",
    "TIPO D (La Prueba): El protagonista está intentando desmentir un mito urbano en vivo y se da cuenta de que es real.",
    "TIPO E (El Testigo): El protagonista está escondido viendo cómo la entidad ataca a otra persona o cosa, narrando en susurros."
]

DEFAULT_MONSTRUOS = [
    "TIPO A (Biológico): Dientes, garras, músculos, saliva, sangre. Miedo a ser devorado físicamente.",
    "TIPO B (Uncanny Valley): Piel de plástico, facciones demasiado perfectas, movimientos rígidos, sonrisas falsas. Miedo a lo que parece humano pero no lo es.",
    "TIPO C (Sombra/Cosmic): Oscuridad viviente, siluetas sin rostro, geometría imposible, muchos ojos. Miedo a lo desconocido.",
    "TIPO D (El Glitch): La entidad parece un error de la realidad, se mueve en frames cortados, su cuerpo se estira o pixelea.",
    "TIPO E (El Mímico): La entidad tiene la voz o la apariencia de un ser querido del protagonista, pero deformada."
]

DEFAULT_ATMOSFERA = [
    "OLOR QUÍMICO: Azufre, cloro, ozono, plástico quemado.",
    "OLOR ORGÁNICO: Tierra mojada, flores de funeral, humedad vieja.",
    "SENSACIÓN TÉRMICA: Frío glacial repentino que empaña la cámara.",
    "SENSACIÓN AUDITIVA: Un zumbido eléctrico constante que causa dolor de cabeza.",
    "SENSACIÓN FÍSICA: Presión en el pecho, como si la gravedad aumentara."
]

DEFAULT_CIERRES = [
    "TIPO A (Bucle Gramatical): La última palabra conecta con la primera del inicio. (NOTA: PROHIBIDO USAR LA FRASE 'NO DEJES DE MIRAR').",
    "TIPO B (Corte Abrupto): El audio se corta en medio de un grito o golpe seco.",
    "TIPO C (Interferencia): El audio se distorsiona con estática y una voz ininteligible al final.",
    "TIPO D (La Súplica): Termina rezando o pidiendo perdón a alguien (mamá, dios).",
    "TIPO E (La Invitación Maldita): El protagonista, ya poseído o muerto, invita al espectador a unirse a él con voz calmada."
]

# VARIABLES ACTIVAS (Se inicializan con defaults, pueden ser sobreescritas por JSON)
LISTA_GANCHOS = list(DEFAULT_GANCHOS)
LISTA_MONSTRUOS = list(DEFAULT_MONSTRUOS)
LISTA_ATMOSFERA = list(DEFAULT_ATMOSFERA)
LISTA_CIERRES = list(DEFAULT_CIERRES)

def save_narrative_vars():
    data = {
        "ganchos": LISTA_GANCHOS,
        "monstruos": LISTA_MONSTRUOS,
        "atmosfera": LISTA_ATMOSFERA,
        "cierres": LISTA_CIERRES
    }
    try:
        with open(NARRATIVE_VARS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving narrative vars: {e}")
        return False

def load_narrative_vars():
    global LISTA_GANCHOS, LISTA_MONSTRUOS, LISTA_ATMOSFERA, LISTA_CIERRES
    if os.path.exists(NARRATIVE_VARS_PATH):
        try:
            with open(NARRATIVE_VARS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                LISTA_GANCHOS[:] = data.get("ganchos", DEFAULT_GANCHOS)
                LISTA_MONSTRUOS[:] = data.get("monstruos", DEFAULT_MONSTRUOS)
                LISTA_ATMOSFERA[:] = data.get("atmosfera", DEFAULT_ATMOSFERA)
                LISTA_CIERRES[:] = data.get("cierres", DEFAULT_CIERRES)
        except Exception as e:
            print(f"Error loading narrative vars: {e}")

# Cargar automáticamente al importar
load_narrative_vars()
