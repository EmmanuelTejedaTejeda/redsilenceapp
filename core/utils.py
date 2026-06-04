import os
import sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def copy_to_clipboard_persistent(text):
    """
    Copies text to the system clipboard in a persistent way (survives app exit).
    Uses PowerShell on Windows to ensure UTF-8 support and persistence.
    """
    import subprocess
    import platform
    
    try:
        if platform.system() == "Windows":
            # Usar PowerShell para garantizar soporte completo de UTF-8 y persistencia
            try:
                # El comando Set-Clipboard de PowerShell maneja nativamente Unicode
                process = subprocess.Popen(['powershell', '-NoProfile', '-Command', 'Set-Clipboard -Value $input'], 
                                         stdin=subprocess.PIPE, text=True, encoding='utf-8')
                process.communicate(input=text)
                return True
            except Exception as e:
                # Fallback a clip.exe si PowerShell falla por alguna razón técnica
                p = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=False)
                p.communicate(input=text.encode('cp1252', errors='replace'))
                return True
            
    except Exception as e:
        print(f"Clipboard Error: {e}")
        return False


def force_focus(window):
    """
    Punch-through focus strategy:
    Forces a window to the front by temporarily setting it to topmost,
    then releases it after a short delay so it doesn't block other apps.
    """
    try:
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        # Release after 200ms
        window.after(200, lambda: window.attributes("-topmost", False))
    except:
        pass
