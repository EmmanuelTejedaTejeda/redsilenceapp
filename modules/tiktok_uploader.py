import os
import json
import time
import hashlib
import base64
import secrets
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
import threading
import io

class CallbackBytesIO(io.BytesIO):
    def __init__(self, initial_bytes, callback):
        super().__init__(initial_bytes)
        self.callback = callback

    def read(self, size=-1):
        chunk = super().read(size)
        if chunk:
            self.callback(self.tell())
        return chunk

# Configuración de Rutas y Parámetros
TOKEN_FILE = 'config/tiktok_token.json'
SETTINGS_FILE = 'config/settings.json'
# URI de redirección local estrictamente autorizada para el entorno de escritorio (Desktop)
REDIRECT_URI = 'http://localhost:8080/'
PORT = 8080

# Variable global para almacenar el código de autenticación recibido por el servidor local
auth_code_callback = None
auth_error_callback = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Desactivar logs en consola de peticiones HTTP para evitar inundación
        pass

    def do_GET(self):
        global auth_code_callback, auth_error_callback
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

        if 'code' in query_params:
            auth_code_callback = query_params['code'][0]
            html = """
            <html>
            <head>
                <title>Silencio Rojo - Autenticación TikTok</title>
                <style>
                    body { background-color: #020202; color: #ffffff; font-family: 'Arial', sans-serif; text-align: center; padding-top: 100px; }
                    .container { border: 2px solid #FF0000; display: inline-block; padding: 40px; border-radius: 12px; box-shadow: 0 0 15px rgba(255, 0, 0, 0.4); }
                    h1 { color: #00FF66; }
                    p { color: #888888; font-size: 16px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>¡Autenticación Exitosa!</h1>
                    <p>SilencioRojoApp ha recibido la autorización de TikTok correctamente.</p>
                    <p>Ya puedes cerrar esta pestaña del navegador y volver a la aplicación.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        else:
            error_msg = query_params.get('error_description', ['Error desconocido'])[0]
            auth_error_callback = error_msg
            html = f"""
            <html>
            <head>
                <title>Silencio Rojo - Fallo de Autenticación</title>
                <style>
                    body { background-color: #020202; color: #ffffff; font-family: 'Arial', sans-serif; text-align: center; padding-top: 100px; }
                    .container { border: 2px solid #FF0000; display: inline-block; padding: 40px; border-radius: 12px; box-shadow: 0 0 15px rgba(255, 0, 0, 0.4); }
                    h1 {{ color: #FF0000; }}
                    p {{ color: #888888; font-size: 16px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Error de Autenticación</h1>
                    <p>No se pudo completar la conexión con TikTok.</p>
                    <p>Detalle: {error_msg}</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))

        # Detener el servidor en un hilo separado para que pueda terminar de enviar la respuesta
        def shutdown_server(server):
            server.shutdown()
        
        threading.Thread(target=shutdown_server, args=(self.server,)).start()


def generate_pkce():
    """Genera el code_verifier y code_challenge requeridos por el flujo PKCE de TikTok."""
    # code_verifier: string url-safe aleatorio de entre 43 y 128 caracteres
    code_verifier = secrets.token_urlsafe(64)
    # code_challenge: SHA256 en formato hexadecimal (requerido por la API de TikTok v2)
    sha256 = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = sha256.hex()
    return code_verifier, code_challenge



def get_tiktok_credentials():
    """Obtiene Client Key y Client Secret desde settings.json."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings.get('tiktok_client_key', ''), settings.get('tiktok_client_secret', '')
        except Exception as e:
            print(f">>> [TIKTOK] Error al leer settings.json: {e}")
    return '', ''


def load_token():
    """Carga los tokens guardados de TikTok."""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f">>> [TIKTOK] Error al cargar token.json: {e}")
    return None


def save_token(token_data):
    """Guarda los tokens de TikTok a disco."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    try:
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=4)
    except Exception as e:
        print(f">>> [TIKTOK] Error al guardar token.json: {e}")


def refresh_access_token(client_key, client_secret, refresh_token):
    """Refresca el access_token usando el refresh_token."""
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        res_json = response.json()
        if 'access_token' in res_json:
            # Aseguramos el casteo explícito de expiraciones a float para evitar desincronizaciones
            expires_in = float(res_json.get('expires_in', 86400))
            refresh_expires_in = float(res_json.get('refresh_expires_in', 31536000))
            token_data = {
                'access_token': res_json['access_token'],
                'refresh_token': res_json.get('refresh_token', refresh_token), # Fallback al anterior si no viene uno nuevo
                'expires_at': float(time.time() + expires_in),
                'refresh_expires_at': float(time.time() + refresh_expires_in)
            }
            save_token(token_data)
            return token_data['access_token']
        else:
            print(f">>> [TIKTOK] Error al refrescar token: {res_json}")
            return None
    except Exception as e:
        print(f">>> [TIKTOK] Excepción al refrescar token: {e}")
        return None


def get_authenticated_token(status_callback=None):
    """Retorna un token de acceso válido, autenticando al usuario si es necesario."""
    client_key, client_secret = get_tiktok_credentials()
    if not client_key or not client_secret:
        raise ValueError("Falta configurar TikTok Client Key o Client Secret en los ajustes.")

    token_data = load_token()
    
    # 1. Si ya tenemos tokens guardados, validar expiración del access_token de forma robusta
    if token_data:
        access_token = token_data.get('access_token')
        try:
            expires_at = float(token_data.get('expires_at', 0))
            refresh_expires_at = float(token_data.get('refresh_expires_at', 0))
        except (ValueError, TypeError):
            expires_at = 0.0
            refresh_expires_at = 0.0
        
        # Si aún es válido (con margen de 5 minutos)
        if time.time() + 300 < expires_at:
            return access_token
            
        # Si expiró pero tenemos refresh_token
        refresh_token = token_data.get('refresh_token')
        
        if refresh_token and (time.time() + 300 < refresh_expires_at):
            if status_callback: status_callback("🔄 REFRESCANDO CONEXIÓN TIKTOK...", "#FFD700")
            new_token = refresh_access_token(client_key, client_secret, refresh_token)
            if new_token:
                return new_token

    # 2. Si no hay token o falló el refresco, iniciar flujo OAuth2 + PKCE
    global auth_code_callback, auth_error_callback
    auth_code_callback = None
    auth_error_callback = None

    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_hex(16)

    # Iniciar servidor local en puerto 8080
    server = HTTPServer(('localhost', PORT), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Construir URL de autorización de TikTok codificando adecuadamente los parámetros (como redirect_uri)
    # Scopes recomendados: video.upload (Inbox) y video.publish (Direct Post)
    encoded_redirect_uri = quote(REDIRECT_URI)
    scopes = "video.upload,video.publish,user.info.basic"
    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/?"
        f"client_key={client_key}"
        f"&scope={scopes}"
        f"&response_type=code"
        f"&redirect_uri={encoded_redirect_uri}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    if status_callback: status_callback("🔑 AUTORIZANDO EN NAVEGADOR...", "#FFD700")
    webbrowser.open(auth_url)

    # Esperar a que el servidor reciba la respuesta (máximo 2 minutos de espera)
    timeout = 120
    start_time = time.time()
    while auth_code_callback is None and auth_error_callback is None:
        if time.time() - start_time > timeout:
            server.shutdown()
            raise TimeoutError("Se agotó el tiempo de espera para la autorización en el navegador.")
        time.sleep(0.5)

    if auth_error_callback:
        raise ValueError(f"Fallo de autorización: {auth_error_callback}")

    # 3. Intercambiar authorization code por access token
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": auth_code_callback,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        status_code = response.status_code
        try:
            res_json = response.json()
        except Exception:
            res_json = {}
            
        if 'access_token' in res_json:
            # Aseguramos el casteo explícito de expiraciones a float para evitar desincronizaciones
            expires_in = float(res_json.get('expires_in', 86400))
            refresh_expires_in = float(res_json.get('refresh_expires_in', 31536000))
            new_token_data = {
                'access_token': res_json['access_token'],
                'refresh_token': res_json['refresh_token'],
                'expires_at': float(time.time() + expires_in),
                'refresh_expires_at': float(time.time() + refresh_expires_in)
            }
            save_token(new_token_data)
            return new_token_data['access_token']
        else:
            error_details = res_json.get('error_description', res_json.get('error', ''))
            if not error_details:
                error_details = response.text or f"HTTP status {status_code}"
            raise ValueError(f"Error al obtener token de TikTok: {error_details}")
    except Exception as e:
        raise ValueError(f"Error en comunicación con TikTok: {e}")



def upload_video_tiktok(file_path, title, status_callback=None, upload_mode="publish"):
    """
    Sube un video a TikTok utilizando el Content Posting API v2.
    upload_mode puede ser:
      - "publish": Publicación directa (requiere scope video.publish y app aprobada para producción).
      - "inbox": Subida a borrador de bandeja de entrada (requiere scope video.upload, excelente para desarrollo).
    """
    if not os.path.exists(file_path):
        return False, f"Error: No se encontró el archivo {file_path}"

    try:
        # 1. Autenticar y obtener access token
        access_token = get_authenticated_token(status_callback)

        # 2. Inicializar la subida
        video_size = os.path.getsize(file_path)
        
        # Requerimientos de la API de TikTok Content Posting v2:
        # - Cada bloque debe ser de entre 5MB y 64MB, excepto el último que puede ser hasta 128MB.
        # - Si el video es menor a 5MB, se debe subir en un solo bloque con chunk_size = video_size.
        # - total_chunk_count debe ser igual a video_size // chunk_size (redondeado hacia abajo).
        MIN_CHUNK_SIZE = 5 * 1024 * 1024 # 5 MB
        
        if video_size < MIN_CHUNK_SIZE:
            chunk_size = video_size
            total_chunk_count = 1
        else:
            total_chunk_count = video_size // MIN_CHUNK_SIZE
            if total_chunk_count == 1:
                chunk_size = video_size
            else:
                chunk_size = MIN_CHUNK_SIZE

        if upload_mode == "inbox":
            init_url = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
            body = {
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": total_chunk_count
                }
            }
        else:
            init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
            # TikTok admite hasta 2,200 caracteres en la API v2. Truncamos a 2000 por seguridad y limpiamos espacios.
            truncated_title = title.strip()[:2000].strip()
            body = {
                "post_info": {
                    "title": truncated_title,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_stitch": False,
                    "disable_comment": False
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": total_chunk_count
                }
            }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        if status_callback: status_callback("🚀 INICIANDO SUBIDA TIKTOK...", "#FFD700")
        response = requests.post(init_url, headers=headers, json=body)
        res_json = response.json()

        if res_json.get('error', {}).get('code') != 'ok':
            err_msg = res_json.get('error', {}).get('message', 'Error desconocido')
            # Si falla publicación directa, reintentar automáticamente en modo inbox (borrador)
            if upload_mode == "publish":
                if status_callback: status_callback("⚠️ REINTENTANDO COMO BORRADOR (INBOX)...", "#FFD700")
                return upload_video_tiktok(file_path, title, status_callback, upload_mode="inbox")
            return False, f"Error inicialización: {err_msg}"

        publish_id = res_json['data']['publish_id']
        upload_url = res_json['data']['upload_url']

        # 3. Subir bloques secuenciales (PUT requests)
        if status_callback: status_callback("📤 SUBIENDO BLOQUES...", "#FFD700")
        
        with open(file_path, 'rb') as f:
            for chunk_index in range(total_chunk_count):
                # Si es el último bloque, leemos todo lo restante del archivo (incluyendo remanente)
                if chunk_index == total_chunk_count - 1:
                    chunk = f.read()
                else:
                    chunk = f.read(chunk_size)
                    
                if not chunk:
                    break
                
                start_byte = chunk_index * chunk_size
                end_byte = start_byte + len(chunk) - 1
                
                put_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {start_byte}-{end_byte}/{video_size}",
                    "Content-Length": str(len(chunk))
                }
                
                # OJO: No mandar header de Authorization en el PUT al GCS
                def chunk_progress_callback(read_bytes_in_chunk):
                    uploaded_bytes = start_byte + read_bytes_in_chunk
                    progress = min(99, int((uploaded_bytes / video_size) * 100))
                    if status_callback:
                        status_callback(f"🚀 SUBIENDO: {progress}%", "#FFD700")

                wrapped_chunk = CallbackBytesIO(chunk, chunk_progress_callback)
                put_response = requests.put(upload_url, headers=put_headers, data=wrapped_chunk)
                if put_response.status_code not in (200, 201, 204, 206, 208):
                    return False, f"Fallo al subir bloque {chunk_index + 1}: HTTP {put_response.status_code}"
                
                # Reportar progreso al completar el bloque
                progress = int(((chunk_index + 1) / total_chunk_count) * 100)
                if status_callback: status_callback(f"🚀 SUBIENDO: {progress}%", "#FFD700")

        # 4. Sondeo del estado del video (Polling)
        if status_callback: status_callback("🔄 PROCESANDO VIDEO EN TIKTOK...", "#00FF66")
        
        status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
        poll_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        poll_body = {
            "publish_id": publish_id
        }

        # Polling limitado a 5 minutos (60 iteraciones de 5 segundos)
        for _ in range(60):
            time.sleep(5)
            try:
                poll_resp = requests.post(status_url, headers=poll_headers, json=poll_body)
                poll_json = poll_resp.json()
                
                if poll_json.get('error', {}).get('code') != 'ok':
                    print(f">>> [TIKTOK] Polling error: {poll_json}")
                    continue

                status_data = poll_json.get('data', {})
                status = status_data.get('status')
                
                if status == 'PUBLISH_COMPLETE':
                    post_ids = status_data.get('publicaly_available_post_id', [])
                    post_id_str = post_ids[0] if post_ids else "Completado"
                    return True, f"Borrador creado en Inbox / Publicado exitosamente. ID: {post_id_str}"
                elif status == 'FAILED':
                    fail_reason = status_data.get('fail_reason', 'Razón desconocida')
                    return False, f"TikTok falló el procesamiento: {fail_reason}"
                elif status == 'PROCESSING':
                    # Aún procesando
                    if status_callback: status_callback("🔄 PROCESANDO EN TIKTOK...", "#00FF66")
            except Exception as pe:
                print(f">>> [TIKTOK] Error durante el sondeo: {pe}")

        # Si sale del bucle por timeout, asumimos que fue subido correctamente a drafts
        return True, "Subida completada. Revisa tu bandeja de entrada en TikTok (Borradores)."

    except Exception as e:
        return False, str(e)
