import os
from groq import Groq

DEFAULT_MODEL = "openai/gpt-oss-120b"

# Mapeo de modelos antiguos/deprecados a sus reemplazos activos oficiales de Groq
DEPRECATED_MODEL_MAP = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "deepseek-r1-distill-llama-70b": "openai/gpt-oss-120b",
    "gemma2-9b-it": "openai/gpt-oss-20b",
    "Groq (Llama 3)": "openai/gpt-oss-120b",
}

def validate_api_key(api_key):
    """Verifica si la API Key tiene un formato básico válido."""
    if not api_key or len(api_key) < 20:
        return False
    return True

def get_active_models(client=None):
    """Intenta obtener la lista dinámica de modelos activos de Groq o retorna la lista oficial actualizada."""
    fallback_models = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
        "groq/compound",
        "groq/compound-mini"
    ]
    if client:
        try:
            models_res = client.models.list()
            if models_res and hasattr(models_res, "data"):
                fetched = [m.id for m in models_res.data if hasattr(m, "id")]
                if fetched:
                    return fetched
        except Exception:
            pass
    return fallback_models

def generate_content(prompt, api_key, model_name=DEFAULT_MODEL):
    """
    Envía el prompt a Groq y retorna la respuesta de texto.
    Prueba únicamente modelos oficiales activos sin modelos descontinuados.
    """
    if not validate_api_key(api_key):
        return "ERROR: API Key de Groq inválida o no configurada."

    # Mapear modelos descontinuados si se solicita uno antiguo
    if model_name in DEPRECATED_MODEL_MAP:
        model_name = DEPRECATED_MODEL_MAP[model_name]

    client = None
    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        return f"ERROR DE CONEXIÓN CON GROQ: No se pudo inicializar el cliente Groq: {e}"

    valid_models = get_active_models(client)

    models_to_try = [model_name] + [m for m in valid_models if m != model_name]
    models_to_try = [m for m in dict.fromkeys(models_to_try) if m]

    errors = []
    for m in models_to_try:
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=m,
                temperature=0.7,
                max_completion_tokens=4000
            )
            if chat_completion.choices and chat_completion.choices[0].message:
                res_content = chat_completion.choices[0].message.content
                if res_content and res_content.strip():
                    return res_content.strip()
        except Exception as e:
            err_msg = str(e)
            print(f"[GROQ CLIENT WARNING] Error probando modelo '{m}': {err_msg}")
            errors.append(f"[{m}]: {err_msg}")
            continue

    return f"ERROR DE CONEXIÓN CON GROQ: {'; '.join(errors)}"
