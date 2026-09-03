import os

try:
    from google import genai
    HAS_NEW_GENAI = True
except ImportError:
    HAS_NEW_GENAI = False

DEFAULT_MODEL = "gemini-2.5-flash"

def validate_api_key(api_key):
    """Verifica si la API Key tiene el formato correcto (básico)."""
    if not api_key or len(api_key) < 20:
        return False
    return True

def generate_content(prompt, api_key, model_name=DEFAULT_MODEL):
    """
    Envía el prompt a Google Gemini y retorna la respuesta de texto.
    Soporta la nueva SDK 'google-genai' con fallback a 'google-generativeai'.
    """
    if not validate_api_key(api_key):
        return "ERROR: API Key inválida o no configurada."

    try:
        if HAS_NEW_GENAI:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if hasattr(response, "text") and response.text:
                return response.text
            return "ERROR: La respuesta de Gemini vino vacía (sin texto)."
        else:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)
            model = genai_legacy.GenerativeModel(model_name)
            generation_config = genai_legacy.types.GenerationConfig(
                candidate_count=1,
                max_output_tokens=32000,
                temperature=0.9,
            )
            response = model.generate_content(prompt, generation_config=generation_config)
            if response.text:
                return response.text
            return "ERROR: La respuesta de Gemini vino vacía (sin texto)."

    except Exception as e:
        return f"ERROR DE CONEXIÓN CON GEMINI ({model_name}): {str(e)}"
