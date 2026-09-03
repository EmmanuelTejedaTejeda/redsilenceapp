import os
import sys
import asyncio

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from api.routers import channels, shorts, analytics, assets, youtube_upload

app = FastAPI(
    title="ShortNexus Studio - API",
    description="Servicios backend para supergenerador multicanal de Shorts y analíticas"
)

# Configurar middleware CORS para permitir peticiones locales
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Manejador global para silenciar advertencias ruidosas de desconexión abrupta en Windows (WinError 10054)
    loop = asyncio.get_running_loop()
    def custom_exception_handler(loop, context):
        exception = context.get('exception')
        if isinstance(exception, ConnectionResetError) or (isinstance(exception, OSError) and getattr(exception, 'winerror', None) == 10054):
            return
        loop.default_exception_handler(context)
    loop.set_exception_handler(custom_exception_handler)

class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if path.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff2', '.ttf', '.ico')):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "no-cache"
        return response

@app.get("/robots.txt", response_class=Response)
def get_robots():
    return Response(content="User-agent: *\nAllow: /\n", media_type="text/plain")

@app.get("/favicon.ico", response_class=Response)
def favicon():
    return Response(status_code=204)

@app.get("/sw.js")
def service_worker_dummy():
    return Response(status_code=204)

# Montar los routers de la API
app.include_router(channels.router)
app.include_router(shorts.router)
app.include_router(analytics.router)
app.include_router(assets.router)
app.include_router(youtube_upload.router)

# Servir archivos estáticos del frontend (HTML, CSS, JS) en la raíz
web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/", CachedStaticFiles(directory=web_dir, html=True), name="static")

