// ShortNexus Studio - Módulo del Estudio de Subtítulos (Subtitles Studio)
import { API_BASE } from './api.js';

let allStyles = {};
let activeStyleName = "Reddit History";
let simulationInterval = null;
let simulationIndex = 0;
let simulationSegments = [];

export async function initSubtitlesStudioModule() {
    setupTabNavigation();
    setupInputsListeners();
    setupPresetsHandler();
    setupSimulationHandler();
    
    // Cargar estilos iniciales desde el backend
    await loadSubtitleStyles();
}

// --- NAVEGACIÓN DE PESTAÑAS INTERNAS ---
function setupTabNavigation() {
    const tabs = document.querySelectorAll(".studio-tabs-nav .btn-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            
            const targetId = tab.getAttribute("data-studio-tab");
            document.querySelectorAll(".studio-tab-content").forEach(content => {
                content.style.display = "none";
            });
            
            const targetContent = document.getElementById(`studio-tab-${targetId}`);
            if (targetContent) {
                targetContent.style.display = "block";
            }
        });
    });
}

// --- LISTENERS DE CAMBIOS EN INPUTS ---
function setupInputsListeners() {
    const inputs = [
        "sub-studio-font-family",
        "sub-studio-font-size-916",
        "sub-studio-font-size-169",
        "sub-studio-casing",
        "sub-studio-bold",
        "sub-studio-italic",
        "sub-studio-color-primary",
        "sub-studio-color-outline",
        "sub-studio-color-back",
        "sub-studio-color-highlight",
        "sub-studio-outline",
        "sub-studio-shadow",
        "sub-studio-animation",
        "sub-studio-alignment",
        "sub-studio-margin-v-916",
        "sub-studio-margin-v-169",
        "sub-studio-hook-type",
        "sub-studio-emojis",
        "sub-studio-bg-select"
    ];

    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const eventName = (el.type === "checkbox" || el.tagName === "SELECT") ? "change" : "input";
            el.addEventListener(eventName, () => {
                updateLabels();
                updatePhoneMockup();
            });
        }
    });
}

// --- ACTUALIZAR TEXTOS DE LOS SLIDERS ---
function updateLabels() {
    const size916 = document.getElementById("sub-studio-font-size-916")?.value || 90;
    const size169 = document.getElementById("sub-studio-font-size-169")?.value || 68;
    const outline = document.getElementById("sub-studio-outline")?.value || 4;
    const shadow = document.getElementById("sub-studio-shadow")?.value || 0;
    const margin916 = document.getElementById("sub-studio-margin-v-916")?.value || 450;
    const margin169 = document.getElementById("sub-studio-margin-v-169")?.value || 120;

    const setLabel = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };

    setLabel("lbl-sub-size-916", `${size916}px`);
    setLabel("lbl-sub-size-169", `${size169}px`);
    setLabel("lbl-sub-outline", outline);
    setLabel("lbl-sub-shadow", shadow);
    setLabel("lbl-sub-margin-916", `${margin916}px`);
    setLabel("lbl-sub-margin-169", `${margin169}px`);

    // Actualizar leyendas de color hexadecimal
    const updateHexLabel = (inputId, labelId) => {
        const val = document.getElementById(inputId)?.value;
        const el = document.getElementById(labelId);
        if (el && val) el.textContent = val;
    };

    updateHexLabel("sub-studio-color-primary", "lbl-studio-color-primary");
    updateHexLabel("sub-studio-color-outline", "lbl-studio-color-outline");
    updateHexLabel("sub-studio-color-back", "lbl-studio-color-back");
    updateHexLabel("sub-studio-color-highlight", "lbl-studio-color-highlight");
}

// --- CARGAR ESTILOS DESDE EL BACKEND ---
export async function loadSubtitleStyles() {
    try {
        const res = await fetch(`${API_BASE}/assets/subtitle-styles`);
        if (!res.ok) return;
        allStyles = await res.json();
        
        // Poblar el select de presets
        const select = document.getElementById("sub-studio-preset-select");
        if (select) {
            select.innerHTML = "";
            Object.keys(allStyles).forEach(name => {
                const opt = document.createElement("option");
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            });
            
            // Seleccionar el activo
            select.value = activeStyleName;
        }

        // Cargar el estilo activo en los controles
        applyStyleToControls(activeStyleName);
    } catch (e) {
        console.error("Error al cargar estilos de subtítulos:", e);
    }
}

// --- APLICAR ESTILO A LOS CONTROLES DEL FORMULARIO ---
function applyStyleToControls(styleName) {
    const style = allStyles[styleName];
    if (!style) return;

    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el && val !== undefined) el.value = val;
    };
    const setChecked = (id, val) => {
        const el = document.getElementById(id);
        if (el && val !== undefined) el.checked = !!val;
    };

    setVal("sub-studio-style-name", style.name || styleName);
    setVal("sub-studio-font-family", style.font_name || "Arial Black");
    setVal("sub-studio-font-size-916", style.font_size_9_16 || 90);
    setVal("sub-studio-font-size-169", style.font_size_16_9 || 68);
    setVal("sub-studio-casing", style.text_case || "uppercase");
    
    setChecked("sub-studio-bold", style.bold === undefined ? true : style.bold === -1);
    setChecked("sub-studio-italic", style.italic === undefined ? false : style.italic === -1);
    
    // Formato de color ASS a hexadecimal HTML: &H00BBGGRR -> #RRGGBB
    const assToHex = (assColor) => {
        if (!assColor) return "#ffffff";
        let clean = assColor.replace(/&H|&/gi, '');
        if (clean.length === 8) {
            // Eliminar los primeros dos dígitos (transparencia/Alpha)
            clean = clean.substring(2);
        }
        if (clean.length === 6) {
            // BGR a RGB
            const b = clean.substring(0, 2);
            const g = clean.substring(2, 4);
            const r = clean.substring(4, 6);
            return `#${r}${g}${b}`;
        }
        return "#ffffff";
    };

    setVal("sub-studio-color-primary", assToHex(style.primary_color));
    setVal("sub-studio-color-outline", assToHex(style.outline_color));
    setVal("sub-studio-color-back", assToHex(style.back_color));
    
    // Highlight color ASS to hex
    setVal("sub-studio-color-highlight", assToHex(style.highlight_color));
    
    setVal("sub-studio-outline", style.outline === undefined ? 4 : style.outline);
    setVal("sub-studio-shadow", style.shadow === undefined ? 0 : style.shadow);
    setVal("sub-studio-animation", style.animation_type || "TikTok");
    setVal("sub-studio-alignment", style.alignment || 2);
    setVal("sub-studio-margin-v-916", style.margin_v_9_16 || 450);
    setVal("sub-studio-margin-v-169", style.margin_v_16_9 || 120);
    setVal("sub-studio-hook-type", style.hook_type || "none");
    setChecked("sub-studio-emojis", style.emojis_enabled === undefined ? true : style.emojis_enabled);

    updateLabels();
    updatePhoneMockup();
}

// --- PRESETS HANDLER (CAMBIO DE PLANTILLA Y CRUD) ---
function setupPresetsHandler() {
    const select = document.getElementById("sub-studio-preset-select");
    if (select) {
        select.addEventListener("change", (e) => {
            activeStyleName = e.target.value;
            applyStyleToControls(activeStyleName);
        });
    }

    // Botón Guardar
    const btnSave = document.getElementById("btn-sub-studio-save");
    if (btnSave) {
        btnSave.addEventListener("click", async () => {
            const name = document.getElementById("sub-studio-style-name")?.value.trim();
            if (!name) {
                alert("Por favor introduce un nombre para el estilo.");
                return;
            }

            // Convertir colores Hex a ASS BGR: #RRGGBB -> &H00BBGGRR
            const hexToAss = (hex) => {
                if (!hex) return "&H00FFFFFF";
                const clean = hex.replace("#", "");
                if (clean.length === 6) {
                    const r = clean.substring(0, 2);
                    const g = clean.substring(2, 4);
                    const b = clean.substring(4, 6);
                    return `&H00${b}${g}${r}`;
                }
                return "&H00FFFFFF";
            };

            const payload = {
                name: name,
                font_name: document.getElementById("sub-studio-font-family")?.value || "Arial Black",
                font_size_9_16: parseInt(document.getElementById("sub-studio-font-size-916")?.value || 90),
                font_size_16_9: parseInt(document.getElementById("sub-studio-font-size-169")?.value || 68),
                primary_color: hexToAss(document.getElementById("sub-studio-color-primary")?.value),
                outline_color: hexToAss(document.getElementById("sub-studio-color-outline")?.value),
                back_color: hexToAss(document.getElementById("sub-studio-color-back")?.value),
                bold: document.getElementById("sub-studio-bold")?.checked ? -1 : 0,
                italic: document.getElementById("sub-studio-italic")?.checked ? -1 : 0,
                outline: parseInt(document.getElementById("sub-studio-outline")?.value || 4),
                shadow: parseInt(document.getElementById("sub-studio-shadow")?.value || 0),
                alignment: parseInt(document.getElementById("sub-studio-alignment")?.value || 2),
                margin_v_9_16: parseInt(document.getElementById("sub-studio-margin-v-916")?.value || 450),
                margin_v_16_9: parseInt(document.getElementById("sub-studio-margin-v-169")?.value || 120),
                animation_type: document.getElementById("sub-studio-animation")?.value || "TikTok",
                text_case: document.getElementById("sub-studio-casing")?.value || "uppercase",
                highlight_color: hexToAss(document.getElementById("sub-studio-color-highlight")?.value),
                emojis_enabled: document.getElementById("sub-studio-emojis")?.checked || false,
                hook_type: document.getElementById("sub-studio-hook-type")?.value || "none"
            };

            try {
                btnSave.disabled = true;
                btnSave.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Guardando...`;

                const res = await fetch(`${API_BASE}/assets/subtitle-styles`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Error en guardado");
                }

                alert(`🎉 Estilo '${name}' guardado correctamente.`);
                activeStyleName = name;
                await loadSubtitleStyles();
                
                // Disparar evento para actualizar el Wizard
                window.dispatchEvent(new CustomEvent("subStylesChanged"));
            } catch (err) {
                console.error("Error guardando estilo de subtítulo:", err);
                alert(`Error al guardar estilo: ${err.message}`);
            } finally {
                btnSave.disabled = false;
                btnSave.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Guardar Estilo`;
            }
        });
    }

    // Botón Eliminar
    const btnDelete = document.getElementById("btn-sub-studio-delete");
    if (btnDelete) {
        btnDelete.addEventListener("click", async () => {
            const name = document.getElementById("sub-studio-preset-select")?.value;
            if (!name) return;

            if (["Reddit History", "Roblox Gaming"].includes(name)) {
                alert("No se pueden eliminar los estilos predeterminados del sistema.");
                return;
            }

            if (!confirm(`¿Estás seguro de que deseas eliminar permanentemente el estilo de subtítulos '${name}'?`)) {
                return;
            }

            try {
                btnDelete.disabled = true;
                const res = await fetch(`${API_BASE}/assets/subtitle-styles/${encodeURIComponent(name)}`, {
                    method: "DELETE"
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Error eliminando estilo");
                }

                alert(`Estilo '${name}' eliminado correctamente.`);
                activeStyleName = "Reddit History";
                await loadSubtitleStyles();
                
                window.dispatchEvent(new CustomEvent("subStylesChanged"));
            } catch (err) {
                console.error("Error eliminando estilo:", err);
                alert(`Error al eliminar estilo: ${err.message}`);
            } finally {
                btnDelete.disabled = false;
            }
        });
    }

    // Botón Exportar JSON
    const btnExport = document.getElementById("btn-sub-studio-export");
    if (btnExport) {
        btnExport.addEventListener("click", () => {
            const name = document.getElementById("sub-studio-style-name")?.value || "export_style";
            const styleObj = {
                name: name,
                font_name: document.getElementById("sub-studio-font-family")?.value || "Arial Black",
                font_size_9_16: parseInt(document.getElementById("sub-studio-font-size-916")?.value || 90),
                font_size_16_9: parseInt(document.getElementById("sub-studio-font-size-169")?.value || 68),
                primary_color: document.getElementById("sub-studio-color-primary")?.value,
                outline_color: document.getElementById("sub-studio-color-outline")?.value,
                back_color: document.getElementById("sub-studio-color-back")?.value,
                bold: document.getElementById("sub-studio-bold")?.checked,
                italic: document.getElementById("sub-studio-italic")?.checked,
                outline: parseInt(document.getElementById("sub-studio-outline")?.value || 4),
                shadow: parseInt(document.getElementById("sub-studio-shadow")?.value || 0),
                alignment: parseInt(document.getElementById("sub-studio-alignment")?.value || 2),
                margin_v_9_16: parseInt(document.getElementById("sub-studio-margin-v-916")?.value || 450),
                margin_v_16_9: parseInt(document.getElementById("sub-studio-margin-v-169")?.value || 120),
                animation_type: document.getElementById("sub-studio-animation")?.value || "TikTok",
                text_case: document.getElementById("sub-studio-casing")?.value || "uppercase",
                highlight_color: document.getElementById("sub-studio-color-highlight")?.value,
                emojis_enabled: document.getElementById("sub-studio-emojis")?.checked || false,
                hook_type: document.getElementById("sub-studio-hook-type")?.value || "none"
            };

            const jsonStr = JSON.stringify(styleObj, null, 2);
            navigator.clipboard.writeText(jsonStr)
                .then(() => alert("📋 Estilo exportado en formato JSON y copiado al portapapeles."))
                .catch(() => {
                    alert("No se pudo copiar automáticamente. Copia este JSON manualmente:\n\n" + jsonStr);
                });
        });
    }

    // Botón Importar JSON
    const btnImport = document.getElementById("btn-sub-studio-import");
    if (btnImport) {
        btnImport.addEventListener("click", () => {
            const rawJson = prompt("Pega el JSON de tu plantilla de subtítulos aquí:");
            if (!rawJson) return;

            try {
                const style = JSON.parse(rawJson);
                
                const setVal = (id, val) => {
                    const el = document.getElementById(id);
                    if (el && val !== undefined) el.value = val;
                };
                const setChecked = (id, val) => {
                    const el = document.getElementById(id);
                    if (el && val !== undefined) el.checked = !!val;
                };

                setVal("sub-studio-style-name", style.name || "Estilo Importado");
                setVal("sub-studio-font-family", style.font_name || "Arial Black");
                setVal("sub-studio-font-size-916", style.font_size_9_16 || 90);
                setVal("sub-studio-font-size-169", style.font_size_16_9 || 68);
                setVal("sub-studio-casing", style.text_case || "uppercase");
                setChecked("sub-studio-bold", style.bold === undefined ? true : style.bold);
                setChecked("sub-studio-italic", style.italic === undefined ? false : style.italic);
                
                // Acepta colores tanto en Hex (#ffffff) como en ASS BGR
                const parseColor = (col) => {
                    if (col && col.startsWith("#")) return col;
                    // BGR ASS
                    let clean = col.replace(/&H|&/gi, '');
                    if (clean.length === 8) clean = clean.substring(2);
                    if (clean.length === 6) {
                        const b = clean.substring(0,2);
                        const g = clean.substring(2,4);
                        const r = clean.substring(4,6);
                        return `#${r}${g}${b}`;
                    }
                    return "#ffffff";
                };

                setVal("sub-studio-color-primary", parseColor(style.primary_color));
                setVal("sub-studio-color-outline", parseColor(style.outline_color));
                setVal("sub-studio-color-back", parseColor(style.back_color));
                setVal("sub-studio-color-highlight", parseColor(style.highlight_color));
                
                setVal("sub-studio-outline", style.outline || 4);
                setVal("sub-studio-shadow", style.shadow || 0);
                setVal("sub-studio-animation", style.animation_type || "TikTok");
                setVal("sub-studio-alignment", style.alignment || 2);
                setVal("sub-studio-margin-v-916", style.margin_v_9_16 || 450);
                setVal("sub-studio-margin-v-169", style.margin_v_16_9 || 120);
                setVal("sub-studio-hook-type", style.hook_type || "none");
                setChecked("sub-studio-emojis", style.emojis_enabled === undefined ? true : style.emojis_enabled);

                updateLabels();
                updatePhoneMockup();
                alert("✨ Estilo cargado en el editor. Haz clic en 'Guardar Estilo' para guardarlo permanentemente.");
            } catch (e) {
                alert("❌ JSON inválido o estructura incorrecta.");
            }
        });
    }
}

// --- ACTUALIZAR EL MOCKUP DEL CELULAR 9:16 EN TIEMPO REAL ---
function updatePhoneMockup() {
    const screen = document.getElementById("sub-studio-screen");
    const container = document.getElementById("sub-studio-text-container");
    const textRendered = document.getElementById("sub-studio-text-rendered");
    
    if (!screen || !container || !textRendered) return;

    // 1. Cambiar fondo simulado del celular
    const bgSelect = document.getElementById("sub-studio-bg-select")?.value;
    if (bgSelect === "parkour") {
        screen.style.background = "linear-gradient(rgba(0,0,0,0.1), rgba(0,0,0,0.1)), url('https://images.unsplash.com/photo-1607988795691-3d0147b43231?q=80&w=250&auto=format&fit=crop')";
    } else if (bgSelect === "obby") {
        screen.style.background = "linear-gradient(rgba(0,0,0,0.15), rgba(0,0,0,0.15)), url('https://images.unsplash.com/photo-1511512578047-dfb367046420?q=80&w=250&auto=format&fit=crop')";
    } else if (bgSelect === "creepy") {
        screen.style.background = "linear-gradient(rgba(0,0,0,0.3), rgba(0,0,0,0.3)), url('https://images.unsplash.com/photo-1509198397868-475647b2a1e5?q=80&w=250&auto=format&fit=crop')";
    } else {
        screen.style.background = "#050508";
    }
    screen.style.backgroundSize = "cover";
    screen.style.backgroundPosition = "center";

    // 2. Extraer propiedades estilográficas
    const fontFamily = document.getElementById("sub-studio-font-family")?.value || "Arial Black";
    const fontSizeVal = parseInt(document.getElementById("sub-studio-font-size-916")?.value || 90, 10);
    const colorPrimary = document.getElementById("sub-studio-color-primary")?.value || "#ffffff";
    const colorOutline = document.getElementById("sub-studio-color-outline")?.value || "#000000";
    const colorBack = document.getElementById("sub-studio-color-back")?.value || "#000000";
    const outlineThickness = parseInt(document.getElementById("sub-studio-outline")?.value || 4, 10);
    const shadowDepth = parseInt(document.getElementById("sub-studio-shadow")?.value || 0, 10);
    
    const bold = document.getElementById("sub-studio-bold")?.checked;
    const italic = document.getElementById("sub-studio-italic")?.checked;
    const alignment = parseInt(document.getElementById("sub-studio-alignment")?.value || 2, 10);
    const marginVVal = parseInt(document.getElementById("sub-studio-margin-v-916")?.value || 450, 10);
    const animType = document.getElementById("sub-studio-animation")?.value || "TikTok";

    // 3. Escalar fuentes y contornos al tamaño miniatura del celular (230px de pantalla activa, ~4.7 veces más pequeño)
    const scaleFactor = 4.7;
    const miniFontSize = Math.max(10, fontSizeVal / scaleFactor);
    const miniOutline = Math.max(0.5, outlineThickness / scaleFactor);
    const miniShadow = shadowDepth / scaleFactor;

    // 4. Aplicar tipografía y estilo
    textRendered.style.fontFamily = `"${fontFamily}", Impact, sans-serif`;
    textRendered.style.fontSize = `${miniFontSize}px`;
    textRendered.style.fontWeight = bold ? "900" : "normal";
    textRendered.style.fontStyle = italic ? "italic" : "normal";
    textRendered.style.color = colorPrimary;

    // Simular el Outline ASS BGR y el Shadow en CSS
    let textShadowStyle = "";
    if (outlineThickness > 0) {
        // Generar un stroke limpio en múltiples direcciones
        const steps = 12;
        const shadows = [];
        for (let i = 0; i < steps; i++) {
            const angle = (i * 2 * Math.PI) / steps;
            const x = Math.cos(angle) * miniOutline;
            const y = Math.sin(angle) * miniOutline;
            shadows.push(`${x.toFixed(1)}px ${y.toFixed(1)}px 0 ${colorOutline}`);
        }
        textShadowStyle = shadows.join(", ");
    }
    
    if (shadowDepth > 0) {
        const shadowPart = `${miniShadow.toFixed(1)}px ${miniShadow.toFixed(1)}px ${Math.max(1, miniShadow).toFixed(1)}px ${colorBack}`;
        textShadowStyle = textShadowStyle ? `${textShadowStyle}, ${shadowPart}` : shadowPart;
    }

    textRendered.style.textShadow = textShadowStyle;

    // 5. Aplicar Posición (MarginV % con Alineación)
    const marginPercent = (marginVVal / 1920) * 100;
    container.style.top = "";
    container.style.bottom = "";
    container.style.transform = "";

    if (alignment === 8) {
        // Superior
        container.style.top = `${marginPercent.toFixed(1)}%`;
    } else if (alignment === 5) {
        // Centro
        container.style.top = "50%";
        container.style.transform = "translateY(-50%)";
    } else {
        // Inferior
        container.style.bottom = `${marginPercent.toFixed(1)}%`;
    }

    // 6. Aplicar Animación / Clase
    textRendered.className = "";
    if (animType === "TikTok") {
        textRendered.classList.add("sub-style-tiktok");
    } else if (animType === "Reddit") {
        textRendered.classList.add("sub-style-reddit");
    } else if (animType === "Roblox") {
        textRendered.classList.add("sub-style-roblox");
    }

    // 7. Simular Hook/Gancho Inicial
    const hookType = document.getElementById("sub-studio-hook-type")?.value || "none";
    const redditCard = document.getElementById("preview-reddit-card");
    const gamingHook = document.getElementById("preview-gaming-hook");
    
    if (redditCard) redditCard.style.display = "none";
    if (gamingHook) {
        gamingHook.style.display = "none";
        gamingHook.className = "gaming-hook-sim";
    }

    if (hookType === "reddit_card" && redditCard) {
        redditCard.style.display = "block";
    } else if (hookType === "roblox_double_line" && gamingHook) {
        gamingHook.style.display = "block";
    } else if (hookType === "strobe_red" && gamingHook) {
        gamingHook.style.display = "block";
        gamingHook.classList.add("gaming-hook-sim-strobe");
    }
}

// --- SIMULADOR DE TRANSICIÓN DE SUBTÍTULOS POR COMAS ---
function setupSimulationHandler() {
    const btnPlay = document.getElementById("btn-sub-studio-sim-play");
    const btnStop = document.getElementById("btn-sub-studio-sim-stop");
    const input = document.getElementById("sub-studio-test-input");

    if (!btnPlay || !btnStop || !input) return;

    btnPlay.addEventListener("click", () => {
        const text = input.value.trim();
        if (!text) {
            alert("Introduce un texto de prueba.");
            return;
        }

        // Dividir por comas
        simulationSegments = text.split(",").map(s => s.trim()).filter(s => s.length > 0);
        if (simulationSegments.length === 0) return;

        // Deshabilitar y Habilitar botones
        btnPlay.disabled = true;
        btnPlay.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Simulando...`;
        btnStop.disabled = false;
        input.disabled = true;

        simulationIndex = 0;
        playSimulationStep();
        
        simulationInterval = setInterval(() => {
            simulationIndex = (simulationIndex + 1) % simulationSegments.length;
            playSimulationStep();
        }, 900); // 900ms por frase
    });

    btnStop.addEventListener("click", stopSimulation);
}

function playSimulationStep() {
    const textRendered = document.getElementById("sub-studio-text-rendered");
    if (!textRendered) return;

    const segment = simulationSegments[simulationIndex];
    const casing = document.getElementById("sub-studio-casing")?.value || "uppercase";
    const highlightColor = document.getElementById("sub-studio-color-highlight")?.value || "#00ffff";
    const emojisEnabled = document.getElementById("sub-studio-emojis")?.checked || false;

    let processedText = segment;
    if (casing === "uppercase") {
        processedText = segment.toUpperCase();
    } else if (casing === "lowercase") {
        processedText = segment.toLowerCase();
    }

    // Identificar palabras de terror a resaltar
    const horrorKws = ["miedo", "terror", "sangre", "muerte", "sombra", "espejo", "dolor", "fantasma", "peligro", "secreto", "imposible", "misteriosa", "noche", "detrás"];
    let words = processedText.split(" ");
    
    words = words.map(w => {
        const clean = w.toLowerCase().replace(/[^a-záéíóúñ]/g, "");
        if (horrorKws.includes(clean)) {
            return `<span style="color: ${highlightColor};">${w}</span>`;
        }
        return w;
    });

    processedText = words.join(" ");

    // Forzar trigger de animación pop-in en el mockup
    const container = document.getElementById("sub-studio-text-container");
    if (container) {
        // Clonar y reemplazar para resetear animaciones CSS
        const el = document.getElementById("sub-studio-text-rendered");
        const newEl = el.cloneNode(true);
        newEl.innerHTML = processedText;
        el.parentNode.replaceChild(newEl, el);
    }
}

function stopSimulation() {
    const btnPlay = document.getElementById("btn-sub-studio-sim-play");
    const btnStop = document.getElementById("btn-sub-studio-sim-stop");
    const input = document.getElementById("sub-studio-test-input");

    if (simulationInterval) {
        clearInterval(simulationInterval);
        simulationInterval = null;
    }

    if (btnPlay) {
        btnPlay.disabled = false;
        btnPlay.innerHTML = `<i class="fa-solid fa-play"></i> Iniciar Simulación`;
    }
    if (btnStop) btnStop.disabled = true;
    if (input) {
        input.disabled = false;
    }

    // Reset a texto estático
    const textRendered = document.getElementById("sub-studio-text-rendered");
    if (textRendered) {
        textRendered.textContent = "SUBTÍTULOS";
    }
    updatePhoneMockup();
}
