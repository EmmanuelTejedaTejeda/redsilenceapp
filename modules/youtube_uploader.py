
import os
import pickle
import socket
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Alcances (Scopes) requeridos para subir videos
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

import re
from api.deps import get_settings

def get_authenticated_service(channel_name=None, client_secrets_file=None, token_file=None):
    """Autentica al usuario para el canal activo especificado y retorna el servicio de la API de YouTube."""
    settings = get_settings()
    channel_name = channel_name or settings.get("active_channel")
    channels = settings.get("channels", [])
    ch_info = next((c for c in channels if c.get("name", "").lower() == (channel_name or "").lower()), None)
    
    clean_ch = re.sub(r'[^a-zA-Z0-9_]', '', (channel_name or "default").replace(' ', '_').lower())
    
    if not token_file:
        token_dir = os.path.join("config", "tokens")
        os.makedirs(token_dir, exist_ok=True)
        token_file = os.path.join(token_dir, f"{clean_ch}_token.pickle")
        
    if not client_secrets_file:
        if ch_info and ch_info.get("credential_file") and os.path.exists(ch_info["credential_file"]):
            client_secrets_file = ch_info["credential_file"]
        else:
            client_secrets_file = 'config/client_secrets.json'

    creds = None
    
    # El archivo token_file almacena los tokens de acceso y actualización del canal
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            try:
                creds = pickle.load(token)
            except Exception:
                creds = None
            
    # Si no hay credenciales válidas disponibles, pedir al usuario que inicie sesión.
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(client_secrets_file):
                     raise FileNotFoundError(f"No se encontró el archivo de credenciales para '{channel_name}': {client_secrets_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)
        except Exception as e:
            # Si el refresco falla (invalid_grant / expirado), borrar y forzar re-login
            if os.path.exists(token_file): os.remove(token_file)
            if not os.path.exists(client_secrets_file):
                 raise FileNotFoundError(f"No se encontró el archivo de credenciales para '{channel_name}': {client_secrets_file}")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Guardar las credenciales aisladas para este canal
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def upload_video(file_path, title, description, keywords="", channel_name=None, status_callback=None):
    """
    Sube un video a YouTube con:
    - Categoría: Entretenimiento (24)
    - Etiqueta IA: Sí
    - Programación: 6:15 PM (Hoy/Mañana)
    """
    if not os.path.exists(file_path):
        return False, f"Error: No se encontró el archivo {file_path}"

    try:
        from datetime import datetime, timedelta
        
        youtube = get_authenticated_service(channel_name=channel_name)
        
        # --- LÓGICA DE PROGRAMACIÓN DINÁMICA ---
        now = datetime.now()
        
        def get_target_for_day(dt):
            # Lunes (0) a Viernes (4) -> 18:15
            # Sábado (5) y Domingo (6) -> 10:00
            if dt.weekday() < 5:
                return dt.replace(hour=18, minute=15, second=0, microsecond=0)
            else:
                return dt.replace(hour=10, minute=0, second=0, microsecond=0)

        target_time = get_target_for_day(now)
        
        # Si ya pasó la hora objetivo de hoy, buscar el horario del día siguiente
        if now >= target_time:
            target_time = get_target_for_day(now + timedelta(days=1))
            
        # Formato ISO 8601 para YouTube (con offset local)
        publish_at_iso = target_time.astimezone().isoformat()

        # Youtube Shorts son detectados automáticamente si son verticales y tienen #Shorts
        if "#Shorts" not in title and "#Shorts" not in description:
            title = f"{title} #Shorts"

        # Etiquetas fijas solicitadas por el usuario + las enviadas desde la UI
        fixed_tags = ["terror analógico extremo", "horror psicológico found footage", "vhs terror analogico español"]
        user_tags = keywords.split(",") if keywords else []
        all_tags = list(set(fixed_tags + user_tags)) # Evitar duplicados

        body = {
            'snippet': {
                'title': title[:100], # YouTube tiene límite de 100 caracteres
                'description': description,
                'tags': all_tags,
                'categoryId': "24", # 24 = Entretenimiento
                'defaultLanguage': 'es',
                'defaultAudioLanguage': 'es'
            },
            'status': {
                'privacyStatus': 'private', # Obligatorio para programar
                'publishAt': publish_at_iso,
                'selfDeclaredMadeForKids': False,
                'selfDeclaredMadeForSyntheticContent': True # Etiqueta de "Hecho con IA"
            }
        }

        # Subir el archivo
        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=MediaFileUpload(file_path, chunksize=256 * 1024, resumable=True)
        )

        print(f"🚀 [YOUTUBE UPLOAD] Iniciando subida de '{title}' para el canal '{channel_name}'...")
        if status_callback: status_callback("🚀 SUBIENDO A YOUTUBE...", "#FFD700")

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"🚀 [YOUTUBE UPLOAD] {progress}% completado...")
                if status_callback:
                    status_callback(f"🚀 Subiendo a YouTube: {progress}% completado", "#FFD700")

        video_id = response.get("id")
        print(f"🎉 [YOUTUBE UPLOAD] ¡Subida exitosa! Video ID: {video_id}")
        return True, video_id

    except HttpError as e:
        return False, f"HTTP Error: {e.resp.status} - {e.content}"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    # Test rápido (requiere client_secrets.json)
    pass
