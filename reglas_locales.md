# Reglas de Desarrollo para SilencioRojoApp

Cada vez que el usuario solicite realizar una modificación, depuración, optimización o creación de código en este proyecto, debes seguir estrictamente el siguiente flujo de trabajo secuencial:

## 1. Investigación y Contexto (Antes de Programar)
Antes de editar o crear cualquier archivo de código, debes consultar la documentación técnica del proyecto:
*   Lee [Analisis_Completo.md](file:///d:/Descargas/SilencioRojoApp/Analisis_Completo.md) para comprender la funcionalidad exacta, variables, clases y la lógica del módulo o componente que vas a tocar.
*   Revisa [Grafo_SilencioRojo.md](file:///d:/Descargas/SilencioRojoApp/Grafo_SilencioRojo.md) para entender las dependencias y relaciones de este componente con otras partes del sistema.

*No pierdas tiempo buscando desde cero o explorando el árbol de directorios a ciegas si la información ya está detallada en estos archivos.*

## 2. Implementación del Cambio
*   Realiza las modificaciones requeridas en el código fuente manteniendo la coherencia con el diseño del sistema.
*   Asegúrate de respetar el estilo estético neón-horror de la interfaz, el manejo asíncrono de subprocesos (FFmpeg, Winsound, etc.) y la compatibilidad con entornos Windows.

## 3. Actualización de Documentación (Después de Programar)
Es **obligatorio** que la documentación técnica refleje fielmente cualquier cambio en el sistema. Inmediatamente después de editar el código:
1.  **Actualizar el Análisis**: Modifica [Analisis_Completo.md](file:///d:/Descargas/SilencioRojoApp/Analisis_Completo.md) agregando, modificando o eliminando descripciones de funciones, clases, lógica de negocio o flujos de trabajo que hayan cambiado.
2.  **Actualizar el Grafo**: Modifica [Grafo_SilencioRojo.md](file:///d:/Descargas/SilencioRojoApp/Grafo_SilencioRojo.md) si has introducido nuevos módulos, nuevas dependencias externas (librerías) o si has modificado funciones que afecten la relación de comunicación entre pestañas de la interfaz y módulos de backend.

*Mantener esta documentación actualizada garantiza que en chats o sesiones futuras la IA entienda el sistema al 100% de manera inmediata.*
