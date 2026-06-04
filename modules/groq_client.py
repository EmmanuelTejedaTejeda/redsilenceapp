import os
from groq import Groq

DEFAULT_MODEL = "llama-3.3-70b-versatile"

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

    try:
        # Inicializar el cliente localmente para no interferir con el entorno global
        client = Groq(api_key=api_key)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model_name,
            temperature=0.9, # Mantenemos la temperatura alta para creatividad
            max_completion_tokens=4000 # Groq Llama 3 maneja contextos grandes
        )
        
        if chat_completion.choices and chat_completion.choices[0].message:
            return chat_completion.choices[0].message.content
        else:
            return "ERROR: La respuesta de Groq vino vacía."

    except Exception as e:
        return f"ERROR DE CONEXIÓN CON GROQ ({model_name}): {str(e)}"
