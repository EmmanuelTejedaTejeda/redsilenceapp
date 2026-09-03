// ShortNexus Studio - Módulo del Wizard de Generación de Shorts (Refactorizado)
import { API_BASE } from './api.js';

let activeStep = 1;
let currentEventSource = null;
let allServerAudios = [];
let selectedAudioFile = null;
let currentRenderedVideoPath = null;

export async function initShortsWizardModule() {
    setupStepNavigation();
    setupCompileHandler();
    setupScriptGenerator();
    setupAudioPlayer();
    setupModalsAndSEO();
    setupYouTubeUpload(); // Inicializar subida a YouTube
    setupResetButton();

    // Await initial loads before restoring inputs
    await loadMasterPromptsForActiveChannel();
    await setupMusicOptions();

    // Initialize inputs auto-saving and loading
    setupWizardStatePersistence();

    // Cargar clips iniciales en el timeline
    loadTimelineClips();

    // Cargar la vista previa del último renderizado si existe
    await loadLastRenderedVideoPreview();

    // Cargar estilos dinámicos de subtítulos
    await loadSubtitleStylesDropdown();
    const subStyleSelect = document.getElementById("shorts-sub-style");
    if (subStyleSelect) {
        subStyleSelect.addEventListener("change", updateSubtitlesStylePreview);
    }
    window.addEventListener("subStylesChanged", async () => {
        await loadSubtitleStylesDropdown();
    });

    // Recargar prompts cuando cambie el canal activo
    window.addEventListener("channelChanged", async () => {
        await loadMasterPromptsForActiveChannel();
        loadServerAudios();
        loadTimelineClips();
        await loadLastRenderedVideoPreview();
    });

    // Recargar música y audios del servidor cuando cambien las rutas de carpetas
    window.addEventListener("foldersChanged", async () => {
        await setupMusicOptions();
        loadServerAudios();
        loadTimelineClips();
        await loadLastRenderedVideoPreview();
    });

    // Bindeo del botón de refrescar audios del servidor
    const btnRefreshAudios = document.getElementById("btn-refresh-audios");
    if (btnRefreshAudios) {
        btnRefreshAudios.addEventListener("click", async () => {
            const icon = btnRefreshAudios.querySelector("i");
            if (icon) icon.classList.add("fa-spin");
            await loadServerAudios();
            if (icon) icon.classList.remove("fa-spin");
        });
    }

    // Auto-refresco al volver a la ventana (focus) si está en el Paso 2
    window.addEventListener("focus", () => {
        if (activeStep === 2) {
            loadServerAudios(null, true);
        }
    });

    // Polling inteligente cada 4 segundos si el Paso 2 está activo
    setInterval(() => {
        if (activeStep === 2) {
            loadServerAudios(null, true);
        }
    }, 4000);
}

function setupStepNavigation() {
    const stepBtns = document.querySelectorAll(".step-btn");
    stepBtns.forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const stepNum = parseInt(btn.getAttribute("data-step"));
            if (!isNaN(stepNum)) {
                switchStep(stepNum);
            }
        });
    });
}

export function switchStep(stepNum) {
    activeStep = stepNum;

    // Actualizar botones de pasos
    document.querySelectorAll(".step-btn").forEach(item => {
        const num = parseInt(item.getAttribute("data-step"));
        if (num === stepNum) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    // Ocultar/Mostrar contenidos de pasos
    document.querySelectorAll(".step-content").forEach(content => {
        content.classList.remove("active");
        content.style.display = "none";
    });

    const target = document.getElementById(`step-${stepNum}`);
    if (target) {
        target.classList.add("active");
        target.style.display = "block";
    }

    if (stepNum === 2) {
        loadServerAudios(null, true);
    }
}

async function loadMasterPromptsForActiveChannel() {
    const select = document.getElementById("shorts-master-prompt");
    if (!select) return;

    const channelSelect = document.getElementById("global-channel-dropdown");
    const channelName = channelSelect ? channelSelect.value : "";

    try {
        // 1. Cargar prompts físicos (del sistema)
        const resPhysical = await fetch(`${API_BASE}/assets/story-prompts`);
        const physicalPrompts = resPhysical.ok ? await resPhysical.json() : [];

        // 2. Cargar prompts personalizados del canal
        let channelPrompts = [];
        if (channelName) {
            const resChannel = await fetch(`${API_BASE}/channels/${channelName}/prompts`);
            channelPrompts = resChannel.ok ? await resChannel.json() : [];
        }

        // 3. Reconstruir opciones
        let optionsHtml = `<option value="Ninguno">Ninguno</option>`;

        if (physicalPrompts.length > 0) {
            optionsHtml += `<optgroup label="Prompts por Defecto (Sistema)">`;
            optionsHtml += physicalPrompts.map(p => 
                `<option value="${p}">${p.replace('.txt', '').replace(/_/g, ' ')}</option>`
            ).join('');
            optionsHtml += `</optgroup>`;
        }

        if (channelPrompts.length > 0) {
            optionsHtml += `<optgroup label="Prompts del Canal (${channelName})">`;
            optionsHtml += channelPrompts.map(p => 
                `<option value="${p.title}">${p.title}</option>`
            ).join('');
            optionsHtml += `</optgroup>`;
        }

        select.innerHTML = optionsHtml;
    } catch (e) {
        console.error("Error cargando prompts en el Wizard:", e);
    }
}

async function setupMusicOptions() {
    const select = document.getElementById("shorts-music");
    if (!select) return;

    try {
        const res = await fetch(`${API_BASE}/assets/music`);
        const files = await res.json();

        select.innerHTML = `<option value="Ninguno">Sin música de fondo</option>` + 
            files.map(f => `<option value="${f}">${f}</option>`).join('');
    } catch (e) {
        console.error("Error cargando música de fondo:", e);
    }
}

function setupScriptGenerator() {
    const btnGenerate = document.getElementById("btn-generate-script");
    if (!btnGenerate) return;

    btnGenerate.addEventListener("click", async () => {
        const channelSelect = document.getElementById("global-channel-dropdown");
        const channelName = channelSelect ? channelSelect.value : "";
        if (!channelName) {
            return alert("Por favor, selecciona un canal activo primero.");
        }

        const promptSelect = document.getElementById("shorts-master-prompt");
        const promptTitle = promptSelect ? promptSelect.value : "Ninguno";
        if (promptTitle === "Ninguno") {
            return alert("Por favor, selecciona un Prompt Master para guiar la generación.");
        }

        const customInstructions = document.getElementById("shorts-trama")?.value || "";
        const aiEngine = document.getElementById("shorts-ia-engine")?.value || "Groq (Llama 3)";

        btnGenerate.disabled = true;
        btnGenerate.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generando Guion...`;

        try {
            const payload = {
                channel_name: channelName,
                prompt_title: promptTitle,
                custom_instructions: customInstructions,
                ai_engine: aiEngine
            };

            const res = await fetch(`${API_BASE}/shorts/generate-script`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                alert(data.detail || "Error al generar el guion.");
                return;
            }

            const scriptTextarea = document.getElementById("shorts-script");
            if (scriptTextarea) {
                scriptTextarea.value = data.script || "";
                saveWizardState();
                alert("¡Guion generado con éxito! Puedes revisarlo y editarlo en la sección derecha.");
                generateSeoMetadata();
            } else {
                console.error("No se encontró el textarea #shorts-script");
            }
        } catch (e) {
            console.error("Error en la llamada de generación de guion:", e);
            alert("Error de conexión al generar el guion.");
        } finally {
            btnGenerate.disabled = false;
            btnGenerate.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Generar Guion con IA`;
        }
    });
}

function setupCompileHandler() {
    const btnCompile = document.getElementById("btn-compile-video");
    if (!btnCompile) return;

    btnCompile.addEventListener("click", async () => {
        const channelSelect = document.getElementById("global-channel-dropdown");
        const channel_name = channelSelect ? channelSelect.value : "";
        if (!channel_name) {
            return alert("Por favor, selecciona un canal activo primero.");
        }

        const scriptText = document.getElementById("shorts-script")?.value || "";
        const voice = document.getElementById("shorts-voice-model")?.value || "Fritz-PlayAI";
        const subtitleStyle = document.getElementById("shorts-sub-style")?.value || "Reddit History";
        const musicFile = document.getElementById("shorts-music")?.value || "Ninguno";
        const bgSource = document.getElementById("shorts-bg-source")?.value || "Minecraft Parkour";
        const renderQuality = document.getElementById("shorts-render-quality")?.value || "720p (Balanceado)";
        const translateAudio = document.getElementById("shorts-translate-audio")?.checked !== false;
        const enableSubtitles = document.getElementById("shorts-enable-subtitles")?.checked || false;
        const aiEngine = document.getElementById("shorts-ia-engine")?.value || "Groq (Llama 3)";

        if (!scriptText) return alert("Por favor escribe o genera un guion primero en el Paso 1.");

        btnCompile.disabled = true;
        btnCompile.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Iniciando...`;

        const logConsole = document.getElementById("render-console-logs");
        if (logConsole) logConsole.innerHTML = `<div>[SISTEMA] Iniciando compilación de Short...</div>`;

        try {
            const payload = {
                channel_name: channel_name,
                prompt_title: document.getElementById("shorts-master-prompt")?.value || null,
                custom_prompt: scriptText,
                music_name: musicFile,
                sub_style: subtitleStyle,
                render_quality: renderQuality,
                voice_name: voice,
                bg_source: bgSource,
                ai_engine: aiEngine,
                narration_file: selectedAudioFile,
                video_title: document.getElementById("shorts-video-title")?.value || null,
                enable_subtitles: enableSubtitles
            };

            const res = await fetch(`${API_BASE}/shorts/generate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                alert(data.detail || "Error al iniciar renderizado.");
                btnCompile.disabled = false;
                btnCompile.innerHTML = `<i class="fa-solid fa-gears"></i> Compilar Short (Render)`;
                return;
            }

            // Escuchar progreso vía Server-Sent Events (SSE) usando el channel_name
            connectSSEProgress(channel_name);
        } catch (e) {
            alert("Error conectando con el servidor de renderizado.");
            btnCompile.disabled = false;
            btnCompile.innerHTML = `<i class="fa-solid fa-gears"></i> Compilar Short (Render)`;
        }
    });
}

function connectSSEProgress(channelName) {
    if (currentEventSource) currentEventSource.close();

    const logConsole = document.getElementById("render-console-logs");
    const progressBar = document.getElementById("compile-progress-bar-fill");
    const progressPercent = document.getElementById("compile-percentage-text");
    const statusLabel = document.getElementById("compile-status-label");

    currentEventSource = new EventSource(`${API_BASE}/shorts/progress/${channelName}`);

    let currentPct = 0;

    currentEventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.percentage !== undefined && data.percentage !== null) {
            const p = parseInt(data.percentage, 10);
            if (!isNaN(p) && p >= 0) {
                currentPct = p;
            }
        }
        
        if (progressBar) progressBar.style.width = `${currentPct}%`;
        if (progressPercent) progressPercent.textContent = `${currentPct}%`;
        if (statusLabel && data.status) {
            statusLabel.textContent = data.status;
        }

        if (logConsole) {
            const entry = document.createElement("div");
            entry.textContent = `[${currentPct}%] ${data.status || ''}`;
            if (data.color) {
                entry.style.color = data.color;
            }
            logConsole.appendChild(entry);
            logConsole.scrollTop = logConsole.scrollHeight;
        }

        // Reflejar progreso en el timeline (Paso 3) si no es un mensaje del renderizado del Short final
        if (data.status) {
            const statusLower = data.status.toLowerCase();
            const isRenderMessage = statusLower.includes("render") || 
                                    statusLower.includes("compila") || 
                                    statusLower.includes("ensambla") || 
                                    statusLower.includes("doblaje") || 
                                    statusLower.includes("subtítulo") || 
                                    statusLower.includes("lut") || 
                                    statusLower.includes("vhs") || 
                                    statusLower.includes("audio de la narración");
            
            if (!isRenderMessage) {
                const isFinished = (data.percentage >= 100) || data.status.includes("❌") || data.status.includes("✅");
                let displayStatus = data.status;
                if (statusLower.includes("gameplay segmentado con éxito") || statusLower.includes("clips integrados")) {
                    displayStatus = "✅ Clips agregados con éxito.";
                }
                updateTimelineStatus(displayStatus, !isFinished);
            }
        }

        if (data.percentage >= 100 || data.status?.includes("❌")) {
            currentEventSource.close();
            const btnCompile = document.getElementById("btn-compile-video");
            if (btnCompile) {
                btnCompile.disabled = false;
                btnCompile.innerHTML = `<i class="fa-solid fa-gears"></i> Compilar Short (Render)`;
            }
            if (data.output_path) {
                currentRenderedVideoPath = data.output_path;
                const videoPreview = document.getElementById("render-preview-video");
                const wrapper = document.getElementById("render-preview-video-wrapper");
                const placeholder = document.getElementById("render-preview-placeholder");
                if (videoPreview) {
                    videoPreview.src = `${API_BASE}/assets/file-preview?path=${encodeURIComponent(data.output_path)}&t=${Date.now()}`;
                    videoPreview.load();
                    if (wrapper) wrapper.style.display = "flex";
                    if (placeholder) placeholder.style.display = "none";
                }
                
                // Habilitar botón de subir a YouTube
                const btnUpload = document.getElementById("btn-upload-youtube");
                if (btnUpload) btnUpload.disabled = false;
            }
            // Si terminó con éxito, recargar los clips en la línea de tiempo
            if (!data.status?.includes("❌")) {
                loadTimelineClips();
            }
        }
    };

    currentEventSource.onerror = () => {
        if (currentEventSource) currentEventSource.close();
    };
}


// --- CONTROLADOR DE AUDIO PLAYER Y LISTA DE NARRACIONES DEL SERVIDOR ---
function setupAudioPlayer() {
    const audioEl = document.getElementById("shorts-audio-element");
    const playBtn = document.getElementById("custom-play-btn");
    const progressBar = document.getElementById("player-progress-bar");
    const currentTimeEl = document.getElementById("player-current-time");
    const durationEl = document.getElementById("player-duration");
    const volumeBar = document.getElementById("player-volume-bar");
    const volumeBtn = document.getElementById("player-volume-btn");

    if (!audioEl) return;

    // Cargar audios iniciales
    loadServerAudios();

    // Event listener para deseleccionar audio
    const clearSelectedBtn = document.getElementById("btn-clear-selected-audio");
    if (clearSelectedBtn) {
        clearSelectedBtn.addEventListener("click", () => {
            selectedAudioFile = null;
            const infoBanner = document.getElementById("selected-audio-info");
            if (infoBanner) infoBanner.style.display = "none";
            const searchInput = document.getElementById("audio-search-input");
            filterServerAudios(searchInput ? searchInput.value : "");
            resetAudioPlayer(); // Limpiar el reproductor de la izquierda
            saveWizardState();
        });
    }

    // Event listener para buscador
    const searchInput = document.getElementById("audio-search-input");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            filterServerAudios(e.target.value);
        });
    }

    // Play/Pause
    if (playBtn) {
        playBtn.addEventListener("click", () => {
            if (audioEl.paused) {
                audioEl.play().catch(err => console.error("Error reproduciendo audio:", err));
            } else {
                audioEl.pause();
            }
        });
    }

    // Eventos del Audio para el boton e indicador de onda
    audioEl.addEventListener("play", () => {
        const waveBars = document.getElementById("audio-wave-bars");
        if (waveBars) waveBars.classList.add("playing");
        if (playBtn) playBtn.innerHTML = `<i class="fa-solid fa-pause"></i>`;
    });

    audioEl.addEventListener("pause", () => {
        const waveBars = document.getElementById("audio-wave-bars");
        if (waveBars) waveBars.classList.remove("playing");
        if (playBtn) playBtn.innerHTML = `<i class="fa-solid fa-play"></i>`;
    });

    // Actualizar progreso e indicadores de tiempo
    audioEl.addEventListener("timeupdate", () => {
        if (progressBar && audioEl.duration) {
            const pct = (audioEl.currentTime / audioEl.duration) * 100;
            progressBar.value = pct;
        }
        if (currentTimeEl) {
            currentTimeEl.textContent = formatTime(audioEl.currentTime);
        }
    });

    // Cargar metadata de duración
    audioEl.addEventListener("loadedmetadata", () => {
        if (durationEl) {
            durationEl.textContent = formatTime(audioEl.duration);
        }
    });

    // Al terminar de reproducir
    audioEl.addEventListener("ended", () => {
        if (playBtn) {
            playBtn.innerHTML = `<i class="fa-solid fa-play"></i>`;
        }
        if (progressBar) progressBar.value = 0;
        const waveBars = document.getElementById("audio-wave-bars");
        if (waveBars) waveBars.classList.remove("playing");
    });

    // Control de progress bar manual
    if (progressBar) {
        progressBar.addEventListener("input", (e) => {
            if (audioEl.duration) {
                const newTime = (e.target.value / 100) * audioEl.duration;
                audioEl.currentTime = newTime;
            }
        });
    }

    // Control de volumen
    if (volumeBar) {
        volumeBar.addEventListener("input", (e) => {
            const vol = e.target.value / 100;
            audioEl.volume = vol;
            updateVolumeIcon(vol);
        });
    }

    if (volumeBtn) {
        volumeBtn.addEventListener("click", () => {
            if (audioEl.muted) {
                audioEl.muted = false;
                if (volumeBar) volumeBar.value = audioEl.volume * 100;
                updateVolumeIcon(audioEl.volume);
            } else {
                audioEl.muted = true;
                if (volumeBar) volumeBar.value = 0;
                volumeBtn.innerHTML = `<i class="fa-solid fa-volume-xmark"></i>`;
            }
        });
    }
}

function updateVolumeIcon(vol) {
    const volumeBtn = document.getElementById("player-volume-btn");
    if (!volumeBtn) return;
    if (vol === 0) {
        volumeBtn.innerHTML = `<i class="fa-solid fa-volume-xmark"></i>`;
    } else if (vol < 0.5) {
        volumeBtn.innerHTML = `<i class="fa-solid fa-volume-low"></i>`;
    } else {
        volumeBtn.innerHTML = `<i class="fa-solid fa-volume-high"></i>`;
    }
}

function formatTime(secs) {
    if (isNaN(secs)) return "0:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
}

async function loadServerAudios(autoSelectFileName = null, silent = false) {
    const container = document.getElementById("audios-list-container");
    if (!container) return;

    try {
        const channelSelect = document.getElementById("global-channel-dropdown");
        const channelName = channelSelect ? channelSelect.value : "";
        const res = await fetch(`${API_BASE}/assets/narrations?t=${Date.now()}&channel_name=${encodeURIComponent(channelName)}`);
        if (!res.ok) {
            if (!silent) container.innerHTML = `<p class="text-dim" style="text-align: center; padding: 15px; font-size: 12px;">Error cargando audios</p>`;
            return;
        }
        const newAudios = await res.json();
        
        // Detectar si la lista de audios cambió
        const hasChanged = JSON.stringify(newAudios.map(a => a.name)) !== JSON.stringify(allServerAudios.map(a => a.name));
        allServerAudios = newAudios;

        if (autoSelectFileName) {
            selectAudioFile(autoSelectFileName);
        } else if (hasChanged || !silent) {
            const searchInput = document.getElementById("audio-search-input");
            const query = searchInput ? searchInput.value.trim() : "";
            if (query) {
                filterServerAudios(query);
            } else {
                renderAudiosList(allServerAudios);
            }
            
            // Si ya hay un audio seleccionado en el estado guardado, cargarlo en el reproductor (sin autoplay)
            if (selectedAudioFile) {
                const fileObj = allServerAudios.find(f => f.name === selectedAudioFile);
                if (fileObj) {
                    loadAudioInPlayer(fileObj.path, fileObj.name, false);
                }
            }
        }
    } catch (e) {
        console.error("Error cargando audios del servidor:", e);
        if (!silent) container.innerHTML = `<p class="text-dim" style="text-align: center; padding: 15px; font-size: 12px;">Error de conexión.</p>`;
    }
}

function renderAudiosList(files) {
    const container = document.getElementById("audios-list-container");
    if (!container) return;

    if (files.length === 0) {
        container.innerHTML = `<p class="text-dim" style="text-align: center; padding: 15px; font-size: 12px;">No se encontraron audios.</p>`;
        return;
    }

    container.innerHTML = files.map(file => {
        const isSelected = selectedAudioFile === file.name;
        const color = file.color || '#00e5ff';
        const relativeTime = file.relative_time || '';
        const durStr = file.formatted_duration || '';
        const previewText = file.preview_text || 'Audio de voz';

        return `
            <div class="audio-item" data-path="${file.path}" data-name="${file.name}" style="display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; margin-bottom: 8px; background: ${isSelected ? 'rgba(0, 229, 255, 0.12)' : 'rgba(255,255,255,0.03)'}; border: 1px solid ${isSelected ? '#00e5ff' : 'var(--color-border)'}; border-left: 5px solid ${color}; border-radius: 6px; cursor: pointer; transition: all 0.2s;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%;">
                    <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex-grow: 1;">
                        <i class="fa-solid fa-file-audio" style="color: ${color}; flex-shrink: 0; font-size: 14px;"></i>
                        <span class="audio-filename" style="font-size: 11px; font-weight: 600; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; color: var(--color-text-main);" title="${file.name}">${file.name}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
                        ${durStr ? `<span style="background: rgba(0, 229, 255, 0.1); border: 1px solid rgba(0, 229, 255, 0.25); color: #00e5ff; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; display: flex; align-items: center; gap: 3px;"><i class="fa-regular fa-clock"></i> ${durStr}</span>` : ''}
                        ${relativeTime ? `<span style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); color: #aaa; font-size: 10px; padding: 2px 6px; border-radius: 4px; display: flex; align-items: center; gap: 3px;"><i class="fa-regular fa-calendar"></i> ${relativeTime}</span>` : ''}
                        <button class="btn-use-audio" title="${isSelected ? 'Deseleccionar' : 'Usar este audio'}" style="background: none; border: none; color: ${isSelected ? '#00e5ff' : '#888'}; cursor: pointer; font-size: 11px; display: flex; align-items: center; gap: 4px;">
                            <i class="${isSelected ? 'fa-solid fa-square-check' : 'fa-regular fa-square-check'}"></i>
                            <span>${isSelected ? 'Seleccionado' : 'Seleccionar'}</span>
                        </button>
                        <button class="btn-play-item" title="Reproducir" style="background: none; border: none; color: ${color}; cursor: pointer; font-size: 14px;"><i class="fa-solid fa-circle-play"></i></button>
                    </div>
                </div>
                
                <!-- Transcripción automática / Lo que dice el audio -->
                <div style="display: flex; align-items: flex-start; gap: 6px; background: rgba(0,0,0,0.25); padding: 6px 10px; border-radius: 4px; border-left: 2px solid ${color};">
                    <span style="color: ${color}; font-size: 11px; flex-shrink: 0; font-weight: bold;">💬</span>
                    <span style="font-size: 11px; color: #d1d5db; font-style: italic; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-word;">"${previewText}"</span>
                </div>
            </div>
        `;
    }).join('');

    // Bindeo de clicks
    container.querySelectorAll(".audio-item").forEach(item => {
        const path = item.getAttribute("data-path");
        const name = item.getAttribute("data-name");

        // Click en reproducir
        item.querySelector(".btn-play-item").addEventListener("click", (e) => {
            e.stopPropagation();
            playAudioFile(path, name);
        });

        // Click en seleccionar
        item.querySelector(".btn-use-audio").addEventListener("click", (e) => {
            e.stopPropagation();
            toggleAudioSelection(name);
        });

        // Click en la fila también reproduce para pre-escucha cómoda
        item.addEventListener("click", () => {
            playAudioFile(path, name);
        });
    });
}

function toggleAudioSelection(name) {
    selectedAudioFile = (selectedAudioFile === name) ? null : name;
    
    // Si se seleccionó, cargarlo en el reproductor (pausado por defecto)
    if (selectedAudioFile) {
        const fileObj = allServerAudios.find(f => f.name === name);
        if (fileObj) {
            loadAudioInPlayer(fileObj.path, fileObj.name, false);
        }
    } else {
        resetAudioPlayer();
    }
    
    // Actualizar el banner de información
    const infoBanner = document.getElementById("selected-audio-info");
    const nameSpan = document.getElementById("selected-audio-name");
    if (infoBanner && nameSpan) {
        if (selectedAudioFile) {
            nameSpan.textContent = selectedAudioFile;
            infoBanner.style.display = "flex";
        } else {
            infoBanner.style.display = "none";
        }
    }
    
    // Refrescar renderizado de lista para mostrar los estilos correctos
    const searchInput = document.getElementById("audio-search-input");
    filterServerAudios(searchInput ? searchInput.value : "");
    saveWizardState();
}

function filterServerAudios(query) {
    if (!query || !query.trim()) {
        renderAudiosList(allServerAudios);
        return;
    }
    const q = query.trim().toLowerCase();
    const filtered = allServerAudios.filter(f => {
        const nameMatch = f.name && f.name.toLowerCase().includes(q);
        const textMatch = f.preview_text && f.preview_text.toLowerCase().includes(q);
        const timeMatch = f.relative_time && f.relative_time.toLowerCase().includes(q);
        return nameMatch || textMatch || timeMatch;
    });
    renderAudiosList(filtered);
}

function playAudioFile(path, name) {
    loadAudioInPlayer(path, name, true); // Reproducir con autoplay
}

function loadAudioInPlayer(path, name, autoplay = false) {
    const audioEl = document.getElementById("shorts-audio-element");
    const playBtn = document.getElementById("custom-play-btn");
    const audioStatus = document.getElementById("audio-status");
    const customPlayerInfo = document.getElementById("custom-player-info");
    const customAudioControls = document.getElementById("custom-audio-controls");

    if (!audioEl) return;

    // Cambiar estado en el reproductor
    if (audioStatus) {
        audioStatus.style.display = "none";
    }
    
    // Inyectar reproductor de voz premium con el badge dinámico
    if (customPlayerInfo) {
        let badgeHtml = "";
        if (selectedAudioFile === name) {
            badgeHtml = `
                <div style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(0, 200, 83, 0.15)); border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 20px; color: #00e5ff; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; box-shadow: 0 0 10px rgba(0,229,255,0.15);">
                    <i class="fa-solid fa-circle-check" style="color: #00e5ff;"></i> Audio Activo para Compilación
                </div>
            `;
        } else {
            badgeHtml = `
                <div style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: rgba(255,255,255,0.05); border: 1px solid var(--color-border); border-radius: 20px; color: var(--color-text-dim); font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                    <i class="fa-solid fa-headphones"></i> Pre-escuchando (Sin Seleccionar)
                </div>
            `;
        }
        
        customPlayerInfo.innerHTML = `
            ${badgeHtml}
            <div id="audio-wave-bars" class="audio-wave-anim">
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
            </div>
            <p id="audio-status-text" class="audio-status-text" style="font-size: 11px; font-weight: 600; color: var(--color-text-main); margin: 8px auto 0; max-width: 90%; word-break: break-all;">
                <i class="fa-solid fa-music" style="color: var(--color-accent);"></i> ${name}
            </p>
        `;
        customPlayerInfo.style.display = "block";
    }
    
    if (customAudioControls) {
        customAudioControls.style.display = "flex";
    }

    // Configurar origen
    audioEl.src = `${API_BASE}/assets/file-preview?path=${encodeURIComponent(path)}&t=${Date.now()}`;
    
    if (autoplay) {
        audioEl.play()
            .then(() => {
                if (playBtn) playBtn.innerHTML = `<i class="fa-solid fa-pause"></i>`;
                const waveBars = document.getElementById("audio-wave-bars");
                if (waveBars) waveBars.classList.add("playing");
            })
            .catch(err => {
                console.error("Error reproduciendo el archivo de audio:", err);
                alert("No se pudo reproducir este archivo de audio.");
            });
    } else {
        audioEl.load();
        if (playBtn) playBtn.innerHTML = `<i class="fa-solid fa-play"></i>`;
        const waveBars = document.getElementById("audio-wave-bars");
        if (waveBars) waveBars.classList.remove("playing");
    }
}

function resetAudioPlayer() {
    const audioEl = document.getElementById("shorts-audio-element");
    const playBtn = document.getElementById("custom-play-btn");
    const audioStatus = document.getElementById("audio-status");
    const customPlayerInfo = document.getElementById("custom-player-info");
    const customAudioControls = document.getElementById("custom-audio-controls");

    if (audioEl) {
        audioEl.pause();
        audioEl.removeAttribute("src");
    }
    if (playBtn) {
        playBtn.innerHTML = `<i class="fa-solid fa-play"></i>`;
    }
    if (customPlayerInfo) {
        customPlayerInfo.style.display = "none";
        customPlayerInfo.innerHTML = "";
    }
    if (customAudioControls) {
        customAudioControls.style.display = "none";
    }
    if (audioStatus) {
        audioStatus.style.display = "block";
    }
}

// --- SISTEMA DE PERSISTENCIA Y CACHÉ DEL WIZARD (LOCALSTORAGE) ---
function saveWizardState() {
    const state = {
        script: document.getElementById("shorts-script")?.value || "",
        trama: document.getElementById("shorts-trama")?.value || "",
        keywords: document.getElementById("shorts-keywords")?.value || "",
        voice: document.getElementById("shorts-voice-model")?.value || "",
        subStyle: document.getElementById("shorts-sub-style")?.value || "",
        music: document.getElementById("shorts-music")?.value || "",
        bgSource: document.getElementById("shorts-bg-source")?.value || "",
        renderQuality: document.getElementById("shorts-render-quality")?.value || "",
        translateAudio: document.getElementById("shorts-translate-audio")?.checked || false,
        enableSubtitles: document.getElementById("shorts-enable-subtitles")?.checked || false,
        aiEngine: document.getElementById("shorts-ia-engine")?.value || "",
        masterPrompt: document.getElementById("shorts-master-prompt")?.value || "",
        selectedAudio: selectedAudioFile,
        videoTitle: document.getElementById("shorts-video-title")?.value || "",
        videoDesc: document.getElementById("shorts-video-desc")?.value || "",
        ytScheduleMode: document.getElementById("shorts-yt-schedule-mode")?.value || ""
    };
    localStorage.setItem("shorts_wizard_state", JSON.stringify(state));
}

function loadWizardState() {
    try {
        const data = localStorage.getItem("shorts_wizard_state");
        if (!data) return;
        const state = JSON.parse(data);
        
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined) el.value = val;
        };
        
        setVal("shorts-script", state.script);
        setVal("shorts-trama", state.trama);
        setVal("shorts-keywords", state.keywords);
        setVal("shorts-voice-model", state.voice);
        setVal("shorts-sub-style", state.subStyle);
        setVal("shorts-music", state.music);
        setVal("shorts-bg-source", state.bgSource);
        setVal("shorts-render-quality", state.renderQuality);
        
        const chk = document.getElementById("shorts-translate-audio");
        if (chk && state.translateAudio !== undefined) {
            chk.checked = state.translateAudio;
        }
        
        const enableSubsChk = document.getElementById("shorts-enable-subtitles");
        if (enableSubsChk && state.enableSubtitles !== undefined) {
            enableSubsChk.checked = state.enableSubtitles;
        } else if (enableSubsChk) {
            enableSubsChk.checked = false;
        }
        
        setVal("shorts-ia-engine", state.aiEngine);
        setVal("shorts-master-prompt", state.masterPrompt);
        setVal("shorts-video-title", state.videoTitle);
        setVal("shorts-video-desc", state.videoDesc);
        setVal("shorts-yt-schedule-mode", state.ytScheduleMode);
        
        if (state.selectedAudio) {
            selectedAudioFile = state.selectedAudio;
            const infoBanner = document.getElementById("selected-audio-info");
            const nameSpan = document.getElementById("selected-audio-name");
            if (infoBanner && nameSpan) {
                nameSpan.textContent = selectedAudioFile;
                infoBanner.style.display = "flex";
            }
            // Trigger list re-render with restored selection
            const searchInput = document.getElementById("audio-search-input");
            filterServerAudios(searchInput ? searchInput.value : "");
        }
        
        // Sincronizar previsualización de estilo de subtítulos
        updateSubtitlesStylePreview();
    } catch (e) {
        console.error("Error cargando estado del wizard:", e);
    }
}

function setupWizardStatePersistence() {
    loadWizardState();

    const fields = [
        "shorts-script",
        "shorts-trama",
        "shorts-keywords",
        "shorts-voice-model",
        "shorts-sub-style",
        "shorts-music",
        "shorts-bg-source",
        "shorts-render-quality",
        "shorts-translate-audio",
        "shorts-enable-subtitles",
        "shorts-ia-engine",
        "shorts-master-prompt",
        "shorts-video-title",
        "shorts-video-desc",
        "shorts-yt-schedule-mode"
    ];

    fields.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const eventName = el.type === "checkbox" ? "change" : "input";
            el.addEventListener(eventName, saveWizardState);
            if (eventName === "input") {
                el.addEventListener("change", saveWizardState);
            }
        }
    });
}

function setupResetButton() {
    const btnReset = document.getElementById("btn-reset-draft");
    if (!btnReset) return;

    btnReset.addEventListener("click", async () => {
        if (!confirm("¿Estás seguro de que deseas limpiar todo el progreso en pantalla y comenzar un nuevo Short?")) {
            return;
        }

        // 1. Cerrar EventSource si está activo
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }

        // 2. Limpiar localStorage
        localStorage.removeItem("shorts_wizard_state");

        // 2a. Desasociar fuentes de video/audio en el DOM para liberar bloqueos de archivo en Windows
        const timelineGrid = document.getElementById("timeline-clips-grid");
        if (timelineGrid) {
            const videos = timelineGrid.querySelectorAll("video");
            videos.forEach(v => {
                const currentSrc = v.src;
                if (currentSrc && currentSrc.startsWith('blob:')) {
                    URL.revokeObjectURL(currentSrc);
                }
                v.removeAttribute("src");
                v.load();
            });
            const images = timelineGrid.querySelectorAll("img");
            images.forEach(img => {
                const currentSrc = img.src;
                if (currentSrc && currentSrc.startsWith('blob:')) {
                    URL.revokeObjectURL(currentSrc);
                }
                img.removeAttribute("src");
            });
            timelineGrid.innerHTML = `<p class="text-dim" style="grid-column: 1/-1; text-align: center; padding: 20px;">🗑️ Purgando recursos...</p>`;
        }

        const videoPreview = document.getElementById("render-preview-video");
        if (videoPreview) {
            videoPreview.removeAttribute("src");
            try { videoPreview.load(); } catch(e){}
        }

        const audioPlayer = document.getElementById("audio-player");
        if (audioPlayer) {
            audioPlayer.removeAttribute("src");
            try { audioPlayer.load(); } catch(e){}
        }

        // Darle un breve tiempo al navegador (250ms) para cerrar conexiones y liberar archivos
        await new Promise(resolve => setTimeout(resolve, 250));

        // 2b. Limpiar caches y timeline en el servidor
        try {
            await fetch(`${API_BASE}/assets/timeline/clear`, { method: "POST" });
            await fetch(`${API_BASE}/assets/cache/clear`, { method: "POST" });
            if (typeof loadTimelineClips === "function") {
                await loadTimelineClips();
            }
        } catch (err) {
            console.error("Error al limpiar caches en el servidor:", err);
        }

        // 2c. Limpiar campos y consolas del módulo Downloader
        const dlUrl = document.getElementById("downloader-url");
        if (dlUrl) dlUrl.value = "";
        const dlList = document.getElementById("downloader-videos-list");
        if (dlList) dlList.innerHTML = "";
        const dlLogs = document.getElementById("downloader-logs-console");
        if (dlLogs) dlLogs.innerHTML = "";
        const dlPreview = document.getElementById("downloader-preview-wrapper");
        if (dlPreview) dlPreview.style.display = "none";
        const dlProgress = document.getElementById("downloader-progress-wrapper");
        if (dlProgress) dlProgress.style.display = "none";

        // 3. Resetear variables de estado
        selectedAudioFile = null;
        currentRenderedVideoPath = null;

        // 4. Limpiar campos del DOM en pantalla
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val;
        };

        setVal("shorts-trama", "");
        setVal("shorts-keywords", "");
        setVal("shorts-script", "");
        setVal("shorts-bg-query", "");
        setVal("shorts-video-title", "");
        setVal("shorts-video-desc", "");

        // Selects a sus opciones por defecto
        const resetSelect = (id, defaultVal) => {
            const el = document.getElementById(id);
            if (el) {
                if (defaultVal !== undefined) {
                    el.value = defaultVal;
                } else if (el.options.length > 0) {
                    el.selectedIndex = 0;
                }
            }
        };

        resetSelect("shorts-voice-model");
        resetSelect("shorts-sub-style");
        resetSelect("shorts-music", "Ninguno");
        resetSelect("shorts-render-quality");
        resetSelect("shorts-ia-engine");
        resetSelect("shorts-master-prompt", "Ninguno");
        resetSelect("shorts-yt-schedule-mode");
        resetSelect("shorts-bg-mode");

        // Checkbox
        const translateChk = document.getElementById("shorts-translate-audio");
        if (translateChk) translateChk.checked = true;
        
        const enableSubsChk = document.getElementById("shorts-enable-subtitles");
        if (enableSubsChk) enableSubsChk.checked = false;

        // 5. Restablecer UI de Audio Seleccionado
        const infoBanner = document.getElementById("selected-audio-info");
        const nameSpan = document.getElementById("selected-audio-name");
        if (infoBanner) infoBanner.style.display = "none";
        if (nameSpan) nameSpan.textContent = "Ninguno";

        const searchInput = document.getElementById("audio-search-input");
        if (searchInput) searchInput.value = "";
        filterServerAudios("");

        // 6. Restablecer Reproductor de Audio
        resetAudioPlayer();

        // 7. Restablecer Vista Previa de Video
        const wrapper = document.getElementById("render-preview-video-wrapper");
        const placeholder = document.getElementById("render-preview-placeholder");
        const btnUpload = document.getElementById("btn-upload-youtube");

        if (videoPreview) videoPreview.removeAttribute("src");
        if (wrapper) wrapper.style.display = "none";
        if (placeholder) placeholder.style.display = "flex";
        if (btnUpload) btnUpload.disabled = true;

        // 8. Restablecer barra de progreso y logs de consola del render
        const progressBar = document.getElementById("compile-progress-bar-fill");
        const progressPercent = document.getElementById("compile-percentage-text");
        const statusLabel = document.getElementById("compile-status-label");
        const logConsole = document.getElementById("render-console-logs");

        if (progressBar) progressBar.style.width = "0%";
        if (progressPercent) progressPercent.textContent = "0%";
        if (statusLabel) statusLabel.textContent = "Esperando orden de compilación...";
        if (logConsole) logConsole.innerHTML = "";

        // 9. Restablecer estado de compilación
        const btnCompile = document.getElementById("btn-compile-video");
        if (btnCompile) {
            btnCompile.disabled = false;
            btnCompile.innerHTML = `<i class="fa-solid fa-gears"></i> Compilar Short (Render)`;
        }

        // 10. Regresar al Paso 1
        switchStep(1);

        alert("Se ha limpiado el progreso de pantalla. Listo para comenzar un nuevo Short.");
    });
}

function setupModalsAndSEO() {
    console.log("🔧 Inicializando bindeos de modales multimedia y SEO...");
    const btnOpenVoice = document.getElementById("btn-open-voice-modal");
    if (btnOpenVoice) {
        btnOpenVoice.addEventListener("click", () => {
            modalVoiceSettings.classList.add("active");
            modalVoiceSettings.style.display = "flex";
        });
    }
    const modalVoice = document.getElementById("modal-voice-synthesis");
    const btnCloseVoice = document.getElementById("close-voice-synthesis-modal-btn");

    const btnOpenAutoGeneral = document.getElementById("btn-auto-general-modular");
    const modalAutoGeneral = document.getElementById("modal-auto-general");
    const btnCloseAutoGeneral = document.getElementById("close-auto-general-modal-btn");

    if (btnOpenAutoGeneral && modalAutoGeneral) {
        btnOpenAutoGeneral.addEventListener("click", () => {
            console.log("⚡ Click en Auto General (Tema / IA)");
            modalAutoGeneral.classList.add("active");
            modalAutoGeneral.style.display = "flex";
            
            const scriptText = document.getElementById("shorts-script")?.value || "";
            const queryInput = document.getElementById("auto-general-search-query");
            if (queryInput && scriptText) {
                queryInput.value = scriptText.split(/[.!?]/)[0].substring(0, 50).trim();
            }
        });
    }
    if (btnCloseAutoGeneral && modalAutoGeneral) {
        btnCloseAutoGeneral.addEventListener("click", () => {
            modalAutoGeneral.classList.remove("active");
            modalAutoGeneral.style.display = "none";
        });
    }

    window.addEventListener("click", (e) => {
        if (e.target === modalVoice) {
            modalVoice.classList.remove("active");
            modalVoice.style.display = "none";
        }
        if (e.target === modalAutoGeneral) {
            modalAutoGeneral.classList.remove("active");
            modalAutoGeneral.style.display = "none";
        }
    });

    const btnGenerateVoice = document.getElementById("btn-generate-voice");
    if (btnGenerateVoice) {
        if (btnGenerateVoice) {
            btnGenerateVoice.style.display = "none";
        }
    }

    const btnUploadLocalAudio = document.getElementById("btn-upload-local-audio");
    const localAudioInput = document.getElementById("local-audio-input");
    
    if (btnUploadLocalAudio && localAudioInput) {
        btnUploadLocalAudio.addEventListener("click", () => {
            localAudioInput.click();
        });
        
        localAudioInput.addEventListener("change", async () => {
            const file = localAudioInput.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append("file", file);
            
            btnUploadLocalAudio.disabled = true;
            btnUploadLocalAudio.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Subiendo...';
            
            try {
                const res = await fetch(`${API_BASE}/assets/upload-audio`, {
                    method: "POST",
                    body: formData
                });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    modalVoice.classList.remove("active");
                    modalVoice.style.display = "none";
                    await loadServerAudios(data.filename);
                } else {
                    alert("Error subiendo audio: " + (data.detail || "Error desconocido"));
                }
            } catch (e) {
                console.error(e);
                alert("Error de conexión al subir audio.");
            } finally {
                btnUploadLocalAudio.disabled = false;
                btnUploadLocalAudio.innerHTML = '<i class="fa-solid fa-file-audio"></i> Subir Audio';
                localAudioInput.value = "";
            }
        });
    }

    async function getActiveNarrationDuration() {
        const audioEl = document.getElementById("shorts-audio-element");
        if (audioEl && audioEl.duration && !isNaN(audioEl.duration) && audioEl.duration > 0) {
            return Math.ceil(audioEl.duration + 5);
        }
        if (selectedAudioFile) {
            try {
                const res = await fetch(`${API_BASE}/assets/audio-duration?filename=${encodeURIComponent(selectedAudioFile)}`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.duration && data.duration > 0) {
                        return Math.ceil(data.duration + 5);
                    }
                }
            } catch (e) {
                console.error("Error obteniendo duración del audio:", e);
            }
        }
        return 120.0;
    }
    const btnAIGenerateTrama = document.getElementById("btn-ai-generate-trama");
    if (btnAIGenerateTrama) {
        btnAIGenerateTrama.addEventListener("click", async () => {
            const currentScript = document.getElementById("shorts-script")?.value || "";
            if (!currentScript.trim()) {
                return alert("Por favor, ingresa un guion en el Paso 1 para poder generar la trama.");
            }
            const tramaInput = document.getElementById("shorts-trama");
            const keywordsInput = document.getElementById("shorts-keywords");
            if (!tramaInput) return;
            
            const btnOriginalText = btnAIGenerateTrama.innerHTML;
            btnAIGenerateTrama.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generando...';
            btnAIGenerateTrama.disabled = true;
            
            try {
                const channelSelect = document.getElementById("global-channel-dropdown");
                const channelName = channelSelect ? channelSelect.value : "";
                const calculatedDuration = await getActiveNarrationDuration();
                
                const res = await fetch(`${API_BASE}/shorts/generate-trama-from-script`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        script: currentScript,
                        channel_name: channelName,
                        audio_duration: calculatedDuration
                    })
                });
                
                if (res.ok) {
                    const data = await res.json();
                    tramaInput.value = data.trama || "";
                    if (keywordsInput) {
                        const kwList = data.keywords || [];
                        keywordsInput.value = kwList.join(", ");
                    }
                    saveWizardState();
                } else {
                    alert("Error al generar trama con IA.");
                }
            } catch (e) {
                console.error(e);
                alert("Error de conexión al generar trama con IA.");
            } finally {
                btnAIGenerateTrama.innerHTML = btnOriginalText;
                btnAIGenerateTrama.disabled = false;
            }
        });
    }

    const btnGenerateTimelineAI = document.getElementById("btn-generate-timeline-ai");
    if (btnGenerateTimelineAI) {
        btnGenerateTimelineAI.addEventListener("click", async () => {
            const trama = document.getElementById("shorts-trama")?.value || "";
            const keywordsText = document.getElementById("shorts-keywords")?.value || "";
            
            if (!trama.trim() && !keywordsText.trim()) {
                return alert("Por favor, ingresa una Trama o Términos de Búsqueda para descargar recursos.");
            }
            
            const cleanKeywordsText = keywordsText.replace(/(\$?\d+),(\d+)/g, "$1$2");
            const customKeywords = cleanKeywordsText.split(",").map(k => k.trim()).filter(k => k.length > 0);
            const channelSelect = document.getElementById("global-channel-dropdown");
            const channelName = channelSelect ? channelSelect.value : "";
            const currentScript = document.getElementById("shorts-script")?.value || "";
            
            updateTimelineStatus("📥 Calculando duración y descargando recursos...", true);
            
            try {
                const calculatedDuration = await getActiveNarrationDuration();
                const res = await fetch(`${API_BASE}/assets/generate-timeline`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        trama: trama,
                        script: currentScript,
                        channel_name: channelName,
                        audio_duration: calculatedDuration,
                        custom_keywords: customKeywords
                    })
                });
                
                if (!res.ok) {
                    const err = await res.json();
                    console.error("Error generando timeline:", err);
                    updateTimelineStatus("❌ Error al generar recursos del timeline.", false);
                } else {
                    connectSSEProgress(channelName);
                    
                    const intervalId = setInterval(async () => {
                        const spinner = document.getElementById("timeline-search-indicator");
                        if (spinner && spinner.style.display !== "none") {
                            await loadTimelineClips();
                        } else {
                            clearInterval(intervalId);
                            await loadTimelineClips();
                        }
                    }, 3000);
                }
            } catch (e) {
                console.error(e);
                updateTimelineStatus("❌ Error de conexión al generar timeline.", false);
            }
        });
    }

    const btnUploadResources = document.getElementById("btn-upload-manual-resources");
    const inputResources = document.getElementById("input-manual-resources");
    
    if (btnUploadResources && inputResources) {
        btnUploadResources.addEventListener("click", () => {
            inputResources.click();
        });
        
        inputResources.addEventListener("change", async () => {
            const files = inputResources.files;
            if (!files || files.length === 0) return;
            
            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
                formData.append("files", files[i]);
            }
            
            btnUploadResources.disabled = true;
            btnUploadResources.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Subiendo...';
            updateTimelineStatus("📤 Subiendo recursos...", true);
            
            try {
                const res = await fetch(`${API_BASE}/assets/upload-resources`, {
                    method: "POST",
                    body: formData
                });
                const data = await res.json();
                if (res.ok && data.status === "success") {
                    updateTimelineStatus(`✅ Subidos ${data.uploaded.length} recursos con éxito.`, false);
                    await loadTimelineClips();
                } else {
                    alert("Error al subir recursos: " + (data.detail || "Error desconocido"));
                    updateTimelineStatus("❌ Error al subir recursos", false);
                }
            } catch (e) {
                console.error(e);
                alert("Error de conexión al subir recursos.");
                updateTimelineStatus("❌ Error de conexión", false);
            } finally {
                btnUploadResources.disabled = false;
                btnUploadResources.innerHTML = '<i class="fa-solid fa-file-import"></i> Adjuntar Recursos Manualmente';
                inputResources.value = "";
            }
        });
    }

    const btnGenerateSeo = document.getElementById("btn-generate-title-desc-seo");
    if (btnGenerateSeo) {
        btnGenerateSeo.addEventListener("click", () => {
            generateSeoMetadata(true);
        });
    }
}

async function loadVoiceInstructions() {
    const select = document.getElementById("shorts-voice-inst");
    if (!select) return;
    try {
        const res = await fetch(`${API_BASE}/assets/voice-prompts`);
        const files = await res.json();
        if (files && files.length > 0) {
            select.innerHTML = files.map(f => `<option value="${f}">${f.replace('.txt', '').replace(/_/g, ' ')}</option>`).join('');
        } else {
            select.innerHTML = `<option value="voice_instructions.txt">voice instructions</option>`;
        }
    } catch (e) {
        console.error(e);
        select.innerHTML = `<option value="voice_instructions.txt">voice instructions</option>`;
    }
}

function updateTimelineStatus(text, showSpinner) {
    const status = document.getElementById("timeline-status");
    if (status) {
        status.innerText = text;
    }
    const spinner = document.getElementById("timeline-search-indicator");
    if (spinner) {
        spinner.style.display = showSpinner ? "flex" : "none";
    }
}

async function generateSeoMetadata(forceManual = false) {
    const scriptText = document.getElementById("shorts-script")?.value || "";
    if (!scriptText.trim()) {
        if (forceManual) alert("Por favor, escribe o genera un guion primero.");
        return;
    }

    const titleInput = document.getElementById("shorts-video-title");
    const descTextarea = document.getElementById("shorts-video-desc");
    
    if (!forceManual && titleInput && titleInput.value.trim() !== "" && descTextarea && descTextarea.value.trim() !== "") {
        return;
    }

    const aiEngine = document.getElementById("shorts-ia-engine")?.value || "Groq (Llama 3)";
    const channelSelect = document.getElementById("global-channel-dropdown");
    const channelName = channelSelect ? channelSelect.value : "";

    const btnGenerateSeo = document.getElementById("btn-generate-title-desc-seo");
    if (btnGenerateSeo) {
        btnGenerateSeo.disabled = true;
        btnGenerateSeo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> GENERANDO...';
    }

    try {
        const res = await fetch(`${API_BASE}/shorts/generate-title-description`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                story: scriptText,
                ai_engine: aiEngine,
                channel_name: channelName
            })
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
            const chosenTitle = data.title || (data.titles && data.titles.length > 0 ? data.titles[0] : "");
            if (titleInput) titleInput.value = chosenTitle;
            if (descTextarea) descTextarea.value = data.description || "";
            saveWizardState();
            if (forceManual) {
                alert("¡Título y descripción SEO generados con éxito!");
            }
        } else {
            if (forceManual) alert("Error generando SEO: " + (data.detail || "Error desconocido"));
        }
    } catch (e) {
        console.error(e);
        if (forceManual) alert("Error de conexión al generar SEO.");
    } finally {
        if (btnGenerateSeo) {
            btnGenerateSeo.disabled = false;
            btnGenerateSeo.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> GENERAR CON IA';
        }
    }
}

function selectAudioFile(name) {
    selectedAudioFile = name;
    
    if (selectedAudioFile) {
        const fileObj = allServerAudios.find(f => f.name === name);
        if (fileObj) {
            loadAudioInPlayer(fileObj.path, fileObj.name, false);
        }
    } else {
        resetAudioPlayer();
    }
    
    const infoBanner = document.getElementById("selected-audio-info");
    const nameSpan = document.getElementById("selected-audio-name");
    if (infoBanner && nameSpan) {
        if (selectedAudioFile) {
            nameSpan.textContent = selectedAudioFile;
            infoBanner.style.display = "flex";
        } else {
            infoBanner.style.display = "none";
        }
    }
    
    saveWizardState();
    
    const searchInput = document.getElementById("audio-search-input");
    filterServerAudios(searchInput ? searchInput.value : "");
}

async function loadTimelineClips() {
    const grid = document.getElementById("timeline-clips-grid");
    if (!grid) return;
    
    try {
        const res = await fetch(`${API_BASE}/assets/timeline`);
        if (!res.ok) {
            grid.innerHTML = `<p class="text-dim" style="grid-column: 1/-1; text-align: center; padding: 20px;">Error al cargar recursos del timeline.</p>`;
            updateTimelineStatus("❌ Error cargando clips del timeline", false);
            return;
        }
        
        const files = await res.json();
        if (files.length === 0) {
            grid.innerHTML = `<p class="text-dim" style="grid-column: 1/-1; text-align: center; padding: 20px;">No hay clips ni imágenes en la línea de tiempo.</p>`;
            updateTimelineStatus("Sin clips en el timeline", false);
            return;
        }
        
        updateTimelineStatus(`Línea de tiempo cargada (${files.length} recursos)`, false);
        
        grid.innerHTML = files.map((file, index) => {
            const isVideo = file.type === "video";
            const fileUrl = `${API_BASE}/assets/file-preview?path=${encodeURIComponent(file.path)}&t=${Date.now()}`;
            
            let thumbHtml = "";
            if (isVideo) {
                thumbHtml = `<video src="${fileUrl}" class="clip-thumb" muted preload="metadata" style="object-fit: cover; width: 100%; height: 90px; border-radius: 6px;"></video>`;
            } else {
                thumbHtml = `<img src="${fileUrl}" class="clip-thumb" style="object-fit: cover; width: 100%; height: 90px; border-radius: 6px;">`;
            }
            
            return `
                <div class="clip-card" data-path="${file.path}">
                    <div class="clip-number">${index + 1}</div>
                    ${thumbHtml}
                    <div class="clip-name" title="${file.name}">${file.name}</div>
                    <div class="clip-actions">
                        <button onclick="previewTimelineClip('${file.path}', '${file.type}')" style="cursor: pointer;"><i class="fa-solid fa-play"></i> Ver</button>
                        <button class="btn-remove" onclick="deleteTimelineClip('${file.path}')" style="cursor: pointer;"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (e) {
        console.error("Error loading timeline:", e);
        grid.innerHTML = `<p class="text-dim" style="grid-column: 1/-1; text-align: center; padding: 20px;">Error de conexión.</p>`;
        updateTimelineStatus("❌ Error de conexión al cargar timeline", false);
    }
}

window.clearAllTimelineClips = async function() {
    if (!confirm("¿Deseas limpiar todos los recursos de la línea de tiempo? Esto eliminará físicamente los clips del servidor.")) {
        return;
    }
    
    updateTimelineStatus("🗑️ Limpiando timeline...", true);
    
    // Liberar los recursos de video y audio en el DOM para evitar que Windows mantenga bloqueos de archivo
    const timelineGrid = document.getElementById("timeline-clips-grid");
    if (timelineGrid) {
        const mediaElements = timelineGrid.querySelectorAll("video, img");
        mediaElements.forEach(el => {
            el.removeAttribute("src");
            if (el.tagName === 'VIDEO') {
                try { el.load(); } catch(e){}
            }
        });
        timelineGrid.innerHTML = `<p class="text-dim" style="grid-column: 1/-1; text-align: center; padding: 20px;">🗑️ Purgando recursos...</p>`;
    }
    
    const videoPreview = document.getElementById("render-preview-video");
    if (videoPreview) {
        videoPreview.removeAttribute("src");
        try { videoPreview.load(); } catch(e){}
    }
    
    // Breve pausa para dar tiempo al navegador a cerrar handles de red
    await new Promise(resolve => setTimeout(resolve, 300));
    
    try {
        const res = await fetch(`${API_BASE}/assets/timeline/clear`, { method: "POST" });
        if (res.ok) {
            await loadTimelineClips();
        } else {
            alert("Error al limpiar el timeline.");
            updateTimelineStatus("❌ Error al limpiar timeline", false);
        }
    } catch (e) {
        console.error(e);
        alert("Error de conexión al limpiar el timeline.");
        updateTimelineStatus("❌ Error de conexión", false);
    }
};

window.previewTimelineClip = function(path, type) {
    const url = `${API_BASE}/assets/file-preview?path=${encodeURIComponent(path)}&t=${Date.now()}`;
    window.open(url, '_blank');
};

window.deleteTimelineClip = async function(path) {
    if (!confirm("¿Deseas eliminar este clip de la línea de tiempo?")) return;
    
    updateTimelineStatus("🗑️ Eliminando clip...", true);
    
    // Liberar el video en el DOM si es el que se va a eliminar
    const escapedPath = path.replace(/\\/g, '/');
    const videos = document.querySelectorAll('#timeline-clips-grid video');
    videos.forEach(v => {
        const src = v.getAttribute("src") || "";
        if (src.includes(encodeURIComponent(path)) || src.includes(encodeURIComponent(escapedPath))) {
            v.removeAttribute("src");
            try { v.load(); } catch(e){}
        }
    });
    
    const videoPreview = document.getElementById("render-preview-video");
    if (videoPreview) {
        const src = videoPreview.getAttribute("src") || "";
        if (src.includes(encodeURIComponent(path)) || src.includes(encodeURIComponent(escapedPath))) {
            videoPreview.removeAttribute("src");
            try { videoPreview.load(); } catch(e){}
        }
    }
    
    // Pausa para cerrar handles de red en Windows
    await new Promise(resolve => setTimeout(resolve, 300));
    
    try {
        const res = await fetch(`${API_BASE}/assets/timeline?path=${encodeURIComponent(path)}`, {
            method: "DELETE"
        });
        if (res.ok) {
            await loadTimelineClips();
        } else {
            alert("Error al eliminar el clip.");
            updateTimelineStatus("❌ Error al eliminar clip", false);
        }
    } catch (e) {
        console.error(e);
        alert("Error de conexión al eliminar el clip.");
        updateTimelineStatus("❌ Error de conexión", false);
    }
};

async function loadLastRenderedVideoPreview() {
    const channelSelect = document.getElementById("global-channel-dropdown");
    const channelName = channelSelect ? channelSelect.value : "";
    
    try {
        const res = await fetch(`${API_BASE}/shorts/last-render?channel_name=${encodeURIComponent(channelName)}`);
        if (!res.ok) return;
        const data = await res.json();
        
        const videoPreview = document.getElementById("render-preview-video");
        const wrapper = document.getElementById("render-preview-video-wrapper");
        const placeholder = document.getElementById("render-preview-placeholder");
        const btnUpload = document.getElementById("btn-upload-youtube");
        
        if (data.status === "success" && data.path) {
            currentRenderedVideoPath = data.path;
            if (videoPreview) {
                videoPreview.src = `${API_BASE}/assets/file-preview?path=${encodeURIComponent(data.path)}&t=${Date.now()}`;
                if (wrapper) wrapper.style.display = "flex";
                if (placeholder) placeholder.style.display = "none";
            }
            if (btnUpload) btnUpload.disabled = false;
        } else {
            currentRenderedVideoPath = null;
            if (videoPreview) videoPreview.removeAttribute("src");
            if (wrapper) wrapper.style.display = "none";
            if (placeholder) placeholder.style.display = "flex";
            if (btnUpload) btnUpload.disabled = true;
        }
    } catch (err) {
        console.error("Error al cargar la última vista previa del video:", err);
    }
}

function setupYouTubeUpload() {
    const btnUpload = document.getElementById("btn-upload-youtube");
    if (!btnUpload) return;
    
    btnUpload.addEventListener("click", async () => {
        if (!currentRenderedVideoPath) {
            return alert("No hay ningún Short renderizado listo para subir.");
        }
        
        const titleVal = document.getElementById("shorts-video-title")?.value || "";
        const descVal = document.getElementById("shorts-video-desc")?.value || "";
        
        if (!titleVal.trim()) {
            return alert("Por favor, introduce un título para tu Short.");
        }
        
        btnUpload.disabled = true;
        btnUpload.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Subiendo a YouTube...`;
        
        try {
            const channelSelect = document.getElementById("global-channel-dropdown");
            const channelName = channelSelect ? channelSelect.value : "";
            
            if (channelName) {
                connectSSEProgress(channelName);
            }

            const res = await fetch(`${API_BASE}/youtube/upload`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    video_path: currentRenderedVideoPath,
                    title: titleVal,
                    description: descVal,
                    keywords: "Shorts",
                    channel_name: channelName
                })
            });
            
            const data = await res.json();
            if (!res.ok) {
                alert(data.detail || "Error al subir a YouTube.");
            } else {
                alert(`🎉 ¡Short subido/programado con éxito! Video ID: ${data.video_id}`);
            }
        } catch (err) {
            console.error("Error subiendo video:", err);
            alert("Error de conexión al intentar subir a YouTube.");
        } finally {
            btnUpload.disabled = false;
            btnUpload.innerHTML = `<i class="fa-brands fa-youtube" style="font-size: 14px;"></i> Programar en YouTube`;
        }
    });
}

// --- CARGA DE PLANTILLAS Y PREVISUALIZACIÓN DINÁMICA ---
let wizardSubtitleStyles = {};

async function loadSubtitleStylesDropdown() {
    const subStyleSelect = document.getElementById("shorts-sub-style");
    if (!subStyleSelect) return;

    try {
        const res = await fetch(`${API_BASE}/assets/subtitle-styles`);
        if (!res.ok) return;
        
        wizardSubtitleStyles = await res.json();
        const activeVal = subStyleSelect.value || "Reddit History";
        
        subStyleSelect.innerHTML = "";
        Object.keys(wizardSubtitleStyles).forEach(name => {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            subStyleSelect.appendChild(opt);
        });

        if (wizardSubtitleStyles[activeVal]) {
            subStyleSelect.value = activeVal;
        } else {
            subStyleSelect.value = Object.keys(wizardSubtitleStyles)[0];
        }
        
        updateSubtitlesStylePreview();
    } catch (e) {
        console.error("Error cargando dropdown de estilos de subtítulos:", e);
    }
}

function updateSubtitlesStylePreview() {
    const subStyleSelect = document.getElementById("shorts-sub-style");
    const previewBox = document.getElementById("subtitles-preview-box");
    const previewText = document.getElementById("subtitles-preview-text");
    
    if (!subStyleSelect || !previewBox || !previewText) return;
    
    const styleName = subStyleSelect.value;
    const style = wizardSubtitleStyles[styleName];
    
    previewText.style.fontFamily = "";
    previewText.style.fontWeight = "";
    previewText.style.fontStyle = "";
    previewText.style.color = "";
    previewText.style.textShadow = "";
    previewText.style.textTransform = "";
    previewText.style.letterSpacing = "";
    previewText.style.animation = "";
    previewText.className = "";

    if (!style) return;
    
    if (style.animation_type === "TikTok") {
        previewBox.style.background = "linear-gradient(135deg, #180303, #020000)"; 
        previewText.className = "sub-style-tiktok";
    } else if (style.animation_type === "Reddit") {
        previewBox.style.background = "linear-gradient(135deg, #0b1426, #030712)";
        previewText.className = "sub-style-reddit";
    } else if (style.animation_type === "Roblox") {
        previewBox.style.background = "linear-gradient(135deg, #0f172a, #1e1b4b, #311042)";
        previewText.className = "sub-style-roblox";
    } else {
        previewBox.style.background = "#050508";
    }

    const assToHex = (assColor) => {
        if (!assColor) return "#ffffff";
        let clean = assColor.replace(/&H|&/gi, '');
        if (clean.length === 8) clean = clean.substring(2);
        if (clean.length === 6) {
            const b = clean.substring(0, 2);
            const g = clean.substring(2, 4);
            const r = clean.substring(4, 6);
            return `#${r}${g}${b}`;
        }
        return "#ffffff";
    };

    const colorPrimary = assToHex(style.primary_color);
    const colorOutline = assToHex(style.outline_color);
    const colorBack = assToHex(style.back_color);
    const colorHighlight = assToHex(style.highlight_color);

    previewText.style.fontFamily = `"${style.font_name}", Impact, sans-serif`;
    previewText.style.fontWeight = style.bold === -1 || style.bold === true ? "900" : "normal";
    previewText.style.fontStyle = style.italic === -1 || style.italic === true ? "italic" : "normal";
    previewText.style.color = colorPrimary;
    previewText.style.textTransform = style.text_case || "uppercase";

    const scaleFactor = 4.7;
    const miniOutline = Math.max(0.5, (style.outline || 4) / scaleFactor);
    const miniShadow = (style.shadow || 0) / scaleFactor;

    let textShadowStyle = "";
    if (style.outline > 0) {
        const shadows = [];
        for (let i = 0; i < 12; i++) {
            const angle = (i * 2 * Math.PI) / 12;
            const x = Math.cos(angle) * miniOutline;
            const y = Math.sin(angle) * miniOutline;
            shadows.push(`${x.toFixed(1)}px ${y.toFixed(1)}px 0 ${colorOutline}`);
        }
        textShadowStyle = shadows.join(", ");
    }
    if (style.shadow > 0) {
        const shadowPart = `${miniShadow.toFixed(1)}px ${miniShadow.toFixed(1)}px ${Math.max(1, miniShadow).toFixed(1)}px ${colorBack}`;
        textShadowStyle = textShadowStyle ? `${textShadowStyle}, ${shadowPart}` : shadowPart;
    }
    previewText.style.textShadow = textShadowStyle;

    const emoji = style.emojis_enabled ? " 😱" : "";
    if (style.text_case === "lowercase") {
        previewText.innerHTML = `¿otra <span style="color: ${colorHighlight};">misteriosa</span> noche?${emoji}`;
    } else if (style.text_case === "normal") {
        previewText.innerHTML = `¿Otra <span style="color: ${colorHighlight};">Misteriosa</span> Noche?${emoji}`;
    } else {
        previewText.innerHTML = `¿OTRA <span style="color: ${colorHighlight};">MISTERIOSA</span> NOCHE?${emoji}`;
    }
}

window.loadServerAudios = loadServerAudios;
window.loadTimelineClips = loadTimelineClips;
window.loadLastRenderedVideoPreview = loadLastRenderedVideoPreview;

