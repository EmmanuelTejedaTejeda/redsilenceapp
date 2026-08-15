# REGLAS LOCALES DEL PROYECTO

> **DIRECTIVA ANTI-PEREZA Y AHORRO DE TOKENS**: Antes de realizar cualquier cambio a petición del usuario, DEBES consultar obligatoriamente `repomix-output.xml` para saber exactamente en qué archivo editar. **QUEDA ESTRICTAMENTE PROHIBIDO analizar los archivos del proyecto uno por uno si `repomix-output.xml` ya existe.**
> **Sincronización Destructiva**: Al actualizar `Analisis_Completo.md`, elimina la lógica desactualizada y reemplázala. Prohibido crear secciones de "Historial" o "Changelog".

## Optimización de Hardware y Entorno Local (Dell Latitude E5540)
1. **Límites de CPU y Temperatura (i5-4300U / ThrottleStop)**: El procesador de la máquina es de bajo consumo (2 núcleos / 4 hilos) optimizado por ThrottleStop. Cualquier ejecución de FFMPEG, MoviePy u otras herramientas de renderizado pesado debe limitar explícitamente los hilos a un máximo de `-threads 2` (o `-threads 1`) para evitar congelamientos del sistema operativo y estrangulamiento térmico (thermal throttling).
2. **Ahorro de Espacio en Unidad C: (SSD 128 GB)**: El disco de sistema C: es muy pequeño. Queda estrictamente prohibido usar el directorio C: o `%TEMP%` en C: para almacenar renders de salida, cachés de descargas masivas (`yt-dlp`), fragmentos temporales grandes o audios. Todo debe escribirse, almacenarse y descargarse en la unidad D: (SSD 1 TB), que es donde se aloja este workspace.
3. **Gestión de Memoria RAM (12 GB + ISLC)**: Para evitar fugas de memoria, se debe optimizar el consumo al procesar arrays de datos en Python o arrays en el DOM, sabiendo que el usuario cuenta con ISLC para liberar memoria standby.
4. **Compatibilidad con Thorium Browser**: El navegador de depuración principal es Thorium. Las características CSS y JS implementadas deben ser altamente eficientes, priorizando el rendimiento del motor V8 optimizado del navegador.

## Reglas Adicionales
1. Consultar siempre `repomix-output.xml` para ubicar archivos y funciones antes de realizar modificaciones.
2. Mantener la documentación y el archivo `Analisis_Completo.md` al día tras cualquier modificación sustancial del código.
