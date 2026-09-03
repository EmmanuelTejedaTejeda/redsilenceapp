# 🛠️ Plan de Actualización Tecnológica - ShortNexus Studio

> **Fecha de Auditoría**: 29 de Agosto de 2026  
> **Herramienta de Verificación**: Context7 MCP Documentation Hub  
> **Estado del Diagnóstico**: Requiere actualización en 6 módulos clave  

---

## 📌 Resumen Ejecutivo

Mediante la consulta de documentación técnica actualizada en tiempo real a través de **Context7**, se han identificado varias áreas de la arquitectura de **ShortNexus Studio** que utilizan librerías obsoletas, identificadores de modelos discontinuados o patrones de ejecución no optimizados para el hardware objetivo (Intel i5-4300U / SSD D:).

A continuación se detallan los módulos específicos que requieren actualización, el impacto técnico y el plan de migración paso a paso.

---

## 🔍 Hallazgos y Diagnóstico por Módulo

### 1. Migración de Google Gemini SDK (`google-generativeai` ➔ `google-genai`)
- **Archivo afectado**: [`modules/gemini_client.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/gemini_client.py)
- **Diagnóstico Context7 (`/googleapis/python-genai`)**:
  - La librería `google.generativeai` ha sido marcada como heredada por Google.
  - La nueva SDK oficial unificada es **`google-genai`** (`from google import genai`).
  - Ofrece clientes asíncronos nativos (`client.aio.models.generate_content`) que evitan bloquear el event loop de FastAPI, además de soporte para herramientas como `GoogleSearch()` para grounding en tiempo real.
- **Acción Requerida**:
  ```python
  # De (Antiguo):
  import google.generativeai as genai
  genai.configure(api_key=api_key)
  model = genai.GenerativeModel("gemini-2.5-flash")

  # A (Actualizado - google-genai):
  from google import genai
  client = genai.Client(api_key=api_key)
  response = client.models.generate_content(
      model='gemini-2.5-flash',
      contents=prompt
  )
  ```

---

### 2. Actualización de Modelos y Cliente Groq AI
- **Archivo afectado**: [`modules/groq_client.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/groq_client.py)
- **Diagnóstico Context7 (`/groq/groq-python`)**:
  - La lista de reintentos `models_to_try` contiene cadenas de modelos no soportados o no existentes en la API de producción (`"groq/compound"`, `"openai/gpt-oss-120b"`, `"qwen/qwen3.6-27b"`).
- **Acción Requerida**:
  - Actualizar los identificadores de modelo a la lista oficial soportada por Groq:
    1. `llama-3.3-70b-versatile` (Modelo principal de alto rendimiento)
    2. `llama-3.1-8b-instant` (Ultra-rápido para metadatos)
    3. `deepseek-r1-distill-llama-70b` (Razonamiento complejo)
    4. `mixtral-8x7b-32768` (Contexto extenso)
  - Adoptar `AsyncGroq` para llamadas no bloqueantes dentro de las funciones `async` de FastAPI.

---

### 3. Transcripción por Voz: Reemplazar Whisper CPU Local por Groq Whisper API
- **Archivos afectados**: [`api/routers/assets.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/api/routers/assets.py#L72), [`modules/render_mix.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/render_mix.py)
- **Diagnóstico Context7**:
  - Actualmente, `assets.py` intenta cargar la librería `whisper` de OpenAI para transcribir audios localmente en la CPU.
  - En un procesador dual-core (Intel i5-4300U), la ejecución de Whisper en CPU genera un uso del 100% de los núcleos, eleva las temperaturas y tarda varios segundos/minutos.
- **Acción Requerida**:
  - Sustituir la carga local de `whisper` por la API de Groq Audio: `whisper-large-v3-turbo` o `whisper-large-v3`.
  - Transcripción instantánea en la nube (<1 segundo) con coste nulo en la GPU/CPU local.

---

### 4. Modernización de Modelos de Datos a Pydantic V2
- **Archivos afectados**: [`api/deps.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/api/deps.py#L230-L309)
- **Diagnóstico Context7 (`/pydantic/pydantic`)**:
  - Pydantic V2 reescribió su motor de validación en Rust (`pydantic-core`), ofreciendo entre 5x y 20x mayor velocidad en serialización JSON.
  - El código actual mezcla patrones de V1 que pueden generar advertencias de deprecación.
- **Acción Requerida**:
  - Reemplazar `.dict()` por `.model_dump()`.
  - Reemplazar `@validator` por `@field_validator`.
  - Reemplazar `schema_extra` en `Config` por `json_schema_extra`.

---

### 5. Actualización Dinámica del Extractor de Medios (`yt-dlp`)
- **Archivos afectados**: [`tools/yt-dlp.exe`](file:///d:/DESAROLLO/NEXUS_STUDIO/tools/yt-dlp.exe), [`modules/timeline_generator.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/timeline_generator.py)
- **Diagnóstico**:
  - El ejecutable `yt-dlp.exe` en `tools/` es estático. YouTube realiza cambios continuos en la firma JS y descifrado de URLs, lo que invalida binarios estáticos en pocas semanas dando errores `403 Forbidden` o `Signatures extraction failed`.
- **Acción Requerida**:
  - Añadir una verificación automática en el backend que ejecute `yt-dlp.exe -U` o utilizar el paquete de Python `yt_dlp` gestionado por `pip` con actualización programada.

---

### 6. Optimización del Frontend SPA y Recursos JS
- **Archivos afectados**: [`web/index.html`](file:///d:/DESAROLLO/NEXUS_STUDIO/web/index.html), [`web/js/viral_map.js`](file:///d:/DESAROLLO/NEXUS_STUDIO/web/js/viral_map.js)
- **Diagnóstico**:
  - Dependencia de scripts CDN externos para `vis-network`. Si el equipo carece de acceso directo a CDN o experimenta latencia, la pestaña de Mapa Viral no carga.
- **Acción Requerida**:
  - Guardar el archivo `vis-network.min.js` localmente en `web/js/vendor/vis-network.min.js` para asegurar un funcionamiento 100% offline.

---

## 🚀 Plan de Acción Recomendado

1. **Fase 1 (Inmediata)**: Actualizar los modelos en [`modules/groq_client.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/groq_client.py) a la lista oficial de Groq (`llama-3.3-70b-versatile`).
2. **Fase 2 (Rendimiento)**: Reemplazar el Whisper en CPU de [`api/routers/assets.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/api/routers/assets.py) por Groq Audio API (`whisper-large-v3-turbo`).
3. **Fase 3 (SDK Moderno)**: Migrar [`modules/gemini_client.py`](file:///d:/DESAROLLO/NEXUS_STUDIO/modules/gemini_client.py) de `google-generativeai` a la nueva SDK `google-genai`.
4. **Fase 4 (Estabilidad de Descargas)**: Configurar auto-update (`-U`) para `yt-dlp` y empaquetar `vis-network.min.js` en local.

---
