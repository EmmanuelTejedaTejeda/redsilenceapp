
import google.generativeai as genai
import os

# Modelo por defecto (Versión 2.5 Flash solicitada por el usuario)
DEFAULT_MODEL = "gemini-2.5-flash"

def validate_api_key(api_key):
    """Verifica si la API Key tiene el formato correcto (básico)."""
    if not api_key or len(api_key) < 30:
        return False
    return True

def generate_content(prompt, api_key, model_name=DEFAULT_MODEL):
    """
    Envía el prompt a Google Gemini y retorna la respuesta de texto.
    """
    if not validate_api_key(api_key):
        return "ERROR: API Key inválida o no configurada."

    try:
        genai.configure(api_key=api_key)
        
        # Uso directo del modelo solicitado
        model = genai.GenerativeModel(model_name)
        generation_config = genai.types.GenerationConfig(
            candidate_count=1,
            # Aumentamos agresivamente para listas largas (Flash soporta contexto largo)
            max_output_tokens=32000, 
            temperature=0.9, 
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        
        if response.text:
            return response.text
        else:
            return "ERROR: La respuesta de Gemini vino vacía (sin texto)."

    except Exception as e:
        return f"ERROR DE CONEXIÓN CON GEMINI ({model_name}): {str(e)}"
