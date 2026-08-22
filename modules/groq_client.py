import os
from groq import Groq

DEFAULT_MODEL = "groq/compound"

def validate_api_key(api_key):
    """Verifica si la API Key tiene un formato básico válido."""
    if not api_key or len(api_key) < 20:
        return False
    return True

def generate_content(prompt, api_key, model_name=DEFAULT_MODEL):
    """
    Envía el prompt a Groq y retorna la respuesta de texto.
    """
    if not validate_api_key(api_key):
        return "ERROR: API Key de Groq inválida o no configurada."

    models_to_try = [model_name, "groq/compound", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]
    models_to_try = list(dict.fromkeys(models_to_try))

    last_err = ""
    for m in models_to_try:
        try:
            client = Groq(api_key=api_key)
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
                return chat_completion.choices[0].message.content
        except Exception as e:
            last_err = str(e)
            continue

    return f"ERROR DE CONEXIÓN CON GROQ: {last_err}"

