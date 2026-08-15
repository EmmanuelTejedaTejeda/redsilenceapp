import os
import sys
import subprocess
import time
import webbrowser

def main():
    print("==================================================")
    print("      SHORTNEXUS STUDIO | WEB SYSTEM             ")
    print("==================================================")
    
    # 1. Verificar dependencias
    print("\n[+] Verificando entorno de ejecución...")
    try:
        import fastapi
        import uvicorn
        print("    [OK] FastAPI y Uvicorn están instalados.")
    except ImportError:
        print("    [!] Faltan dependencias. Instalando fastapi y uvicorn...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "jinja2"])
        print("    [OK] Dependencias instaladas con éxito.")

    # 2. Iniciar servidor FastAPI con Uvicorn
    print("\n[+] Iniciando backend FastAPI localmente en http://localhost:8000 ...")
    
    # Ejecutamos uvicorn como un proceso secundario (escuchando en todas las interfaces)
    cmd = [
        sys.executable, "-m", "uvicorn", "server:app", 
        "--host", "0.0.0.0", 
        "--port", "8000", 
        "--reload",
        "--log-level", "info"
    ]
    
    server_process = subprocess.Popen(cmd)
    
    # Esperar activamente a que el servidor FastAPI esté 100% funcional y respondiendo solicitudes HTTP
    print("\n[+] Esperando a que el servidor FastAPI esté 100% listo...")
    import urllib.request
    import urllib.error

    url = "http://localhost:8000/"
    server_ready = False
    max_wait_seconds = 20
    start_wait = time.time()

    while time.time() - start_wait < max_wait_seconds:
        if server_process.poll() is not None:
            print("    [!] Error: El proceso del servidor se cerró inesperadamente.")
            break
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=1) as response:
                if response.status in (200, 304):
                    server_ready = True
                    break
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
            time.sleep(0.2)

    if server_ready:
        print("    [OK] ¡Servidor 100% activo y respondiendo!")
        print("\n[+] Abriendo panel de control en tu navegador predeterminado...")
        try:
            subprocess.Popen(f'start "" "{url}"', shell=True)
        except Exception as e:
            print(f"    [!] Error abriendo navegador de forma directa, reintentando: {e}")
            webbrowser.open(url)
    else:
        print("    [!] Advertencia: El servidor no respondió dentro del tiempo límite.")

    print("\n==================================================")
    print("  SERVIDOR CORRIENDO. Presiona Ctrl + C para salir ")
    print("==================================================")

    try:
        # Mantener el proceso vivo hasta que el usuario presione Ctrl + C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] Apagando servidor Red Silence...")
        server_process.terminate()
        server_process.wait()
        print("[+] Servidor cerrado. ¡Hasta pronto!")

if __name__ == "__main__":
    main()
