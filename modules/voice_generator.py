import os
import wave
import traceback

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

def generate_voice(text, api_key, voice_instructions_path, output_path, model_name="gemini-2.5-flash-preview-tts"):
    """
    Genera audio a partir de texto utilizando Gemini (voz Charon)
    y una plantilla de instrucciones de voz específica.
    
    Args:
        text (str): El guion o texto a convertir en voz.
        api_key (str): La API Key de Google Gemini.
        voice_instructions_path (str): Ruta al archivo de texto con las instrucciones de voz.
        output_path (str): Ruta de destino para guardar el archivo .wav generado.
        model_name (str): Nombre del modelo Gemini a utilizar.
        
    Returns:
        str: Ruta del archivo generado si fue exitoso.
    """
    if not GENAI_AVAILABLE:
        raise ImportError("El SDK de Google Gen AI ('google-genai') no está instalado o no se pudo cargar.")
        
    if not api_key:
        raise ValueError("La API Key de Gemini es obligatoria.")
        
    if not os.path.exists(voice_instructions_path):
        raise FileNotFoundError(f"No se encontró el archivo de plantilla de voz en: {voice_instructions_path}")
        
    # Leer las instrucciones de voz
    with open(voice_instructions_path, "r", encoding="utf-8") as f:
        voice_instructions = f.read().strip()

    # Crear cliente de Gemini usando el nuevo SDK
    client = genai.Client(api_key=api_key)
    
    # Formatear el contenido para guiar la actuación de voz de la IA sin causar el error 500 de la API
    prompt_content = f"""INSTRUCCIONES DE ACTUACIÓN VOCAL (NO LEER EN VOZ ALTA):
{voice_instructions}

Por favor, lee el siguiente guion en voz alta. Sigue las instrucciones de actuación vocal anteriores para modular tu entonación, velocidad y pausas, pero lee ÚNICAMENTE el guion provisto a continuación. No leas las instrucciones, no digas 'Guion', ni agregues explicaciones.

Guion a leer en voz alta:
{text}"""

    # Configurar para obtener salida de AUDIO utilizando la voz "Charon"
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Charon"
                )
            )
        ),
        temperature=0.7
    )
    
    try:
        # Realizar llamada de generación
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_content,
            config=config
        )
        
        # Extraer los bytes de audio PCM de los parts de la respuesta
        audio_data = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    audio_data = part.inline_data.data
                    break
                    
        if not audio_data:
            err_msg = ""
            if response.text:
                err_msg = f": {response.text}"
            raise ValueError(f"No se recibió audio de la API de Gemini. Comprueba que el modelo '{model_name}' soporte salida de audio{err_msg}")
            
        # Guardar como archivo WAV de 24kHz, 16-bit PCM Mono
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)      # Mono
            wf.setsampwidth(2)      # 2 bytes = 16 bits
            wf.setframerate(24000)  # 24kHz
            wf.writeframes(audio_data)
            
    except Exception as e:
        print(">>> [CRITICAL] ERROR DETECTADO EN modules/voice_generator.py (generate_voice):")
        traceback.print_exc()
        raise e
        
    return output_path
