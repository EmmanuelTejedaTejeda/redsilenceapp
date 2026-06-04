
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

def get_authenticated_service(client_secrets_file='config/client_secrets.json', token_file='config/token.pickle'):
    """Autentica al usuario y retorna el servicio de la API de YouTube."""
    creds = None
    
    # El archivo token.pickle almacena los tokens de acceso y actualización del usuario
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
            
    # Si no hay credenciales válidas disponibles, pedir al usuario que inicie sesión.
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(client_secrets_file):
                     raise FileNotFoundError(f"No se encontró el archivo de credenciales: {client_secrets_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)
        except Exception as e:
            # Si el refresco falla (invalid_grant / expirado), borrar y forzar re-login
            if os.path.exists(token_file): os.remove(token_file)
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Guardar las credenciales para la próxima ejecución
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def upload_video(file_path, title, description, keywords="", status_callback=None):
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
        
        youtube = get_authenticated_service()
        
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
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        )

        if status_callback: status_callback("🚀 SUBIENDO A YOUTUBE...", "#FFD700")

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status and status_callback:
                progress = int(status.progress() * 100)
                status_callback(f"🚀 SUBIENDO: {progress}%", "#FFD700")

        video_id = response.get("id")
        return True, video_id

    except HttpError as e:
        return False, f"HTTP Error: {e.resp.status} - {e.content}"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    # Test rápido (requiere client_secrets.json)
    pass
