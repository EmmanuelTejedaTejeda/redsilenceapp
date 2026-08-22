import { API_BASE } from './api.js';

let currentEditingChannel = null;
let channelPromptsList = [];

function getChannelTheme(channel) {
    if (!channel) return 'YouTube';
    return channel.theme || channel.platform || 'YouTube';
}

function renderChannelsGrid(channels, activeChannel) {
    const container = document.getElementById("settings-channels-list") || document.getElementById("channels-list-container");
    if (!container) return;

    if (!channels || channels.length === 0) {
        container.innerHTML = `<div style="color: var(--color-text-dim); text-align: center; padding: 20px; font-size: 11px;">No hay canales vinculados todavía. Usa el formulario de abajo para agregar uno.</div>`;
        return;
    }

    container.innerHTML = channels.map(c => {
        const isActive = c.name === activeChannel;
        const color = c.theme_color || '#e50914';
        const themeText = getChannelTheme(c);
        const langText = (c.language || 'es').toUpperCase();
        const secretPath = c.credential_file || c.secret_path || '';
        const secretName = secretPath ? secretPath.split(/[\\/]/).pop() : 'Sin credencial OAuth2';

        return `
            <div class="channel-item-card ${isActive ? 'active-channel-card' : ''}" 
                 style="background: rgba(22, 22, 30, 0.95); border: 1px solid ${isActive ? color : 'rgba(255, 255, 255, 0.12)'}; border-left: 4px solid ${color}; border-radius: 12px; padding: 12px 14px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.4); backdrop-filter: blur(10px);">
                
                <!-- 1. Cabecera del Canal (Nombre & Badges) -->
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%;">
                    <div style="display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1;">
                        <div style="width: 36px; height: 36px; border-radius: 8px; background: ${color}22; border: 1px solid ${color}55; display: flex; align-items: center; justify-content: center; color: ${color}; font-size: 16px; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
                            <i class="fa-brands fa-youtube"></i>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 1px; min-width: 0; flex: 1;">
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <span style="font-weight: 800; font-size: 14px; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${c.name}">${c.name}</span>
                                ${isActive ? `<span style="background: rgba(229,9,20,0.25); border: 1px solid rgba(229,9,20,0.6); color: #ff5e62; font-size: 8px; font-weight: 800; padding: 2px 6px; border-radius: 8px; text-transform: uppercase; flex-shrink: 0;"><i class="fa-solid fa-circle-check"></i> ACTIVO</span>` : ''}
                            </div>
                            <div style="font-size: 10px; color: #7a7e8c; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${secretPath}">
                                <i class="fa-solid fa-key" style="opacity: 0.6; font-size: 8px;"></i> ${secretName}
                            </div>
                        </div>
                    </div>
                    
                    <span style="background: rgba(0,255,204,0.1); border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 6px; flex-shrink: 0; height: fit-content;"><i class="fa-solid fa-globe"></i> ${langText}</span>
                </div>

                <!-- 2. Temática del Canal -->
                <div style="font-size: 11px; color: #b0b5c5; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.06); padding: 6px 10px; border-radius: 6px; display: flex; align-items: center; gap: 6px; min-width: 0; overflow: hidden;" title="${themeText}">
                    <i class="fa-solid fa-masks-theater text-accent" style="font-size: 10px; flex-shrink: 0;"></i>
                    <span style="font-weight: 600; color: #e0e5f5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${themeText}</span>
                </div>

                <!-- 3. Barra de Botones de Acción (Ancho Completo Distribuidos) -->
                <div style="display: flex; align-items: center; gap: 6px; width: 100%; margin-top: 2px;">
                    <button class="btn btn-sm btn-secondary" onclick="window.openEditChannelModal('${c.name}')" title="Configurar Temática e Idioma" style="flex: 1; height: 30px; padding: 0 8px; font-size: 11px; font-weight: 700; border-radius: 6px; display: flex; align-items: center; justify-content: center; gap: 5px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #ffffff;">
                        <i class="fa-solid fa-gear" style="color: #00ffcc;"></i> Configurar
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="window.openPromptsModal('${c.name}')" title="Prompts Master" style="flex: 1; height: 30px; padding: 0 8px; font-size: 11px; font-weight: 700; border-radius: 6px; display: flex; align-items: center; justify-content: center; gap: 5px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);">
                        <i class="fa-solid fa-scroll" style="color: var(--color-accent);"></i> Prompts
                    </button>
                    ${!isActive ? `<button class="btn btn-sm btn-accent" onclick="window.selectActiveChannel('${c.name}')" style="flex: 1; height: 30px; padding: 0 8px; font-size: 11px; font-weight: 700; border-radius: 6px; display: flex; align-items: center; justify-content: center; gap: 4px;"><i class="fa-solid fa-check"></i> Activar</button>` : ''}
                    <button class="btn btn-sm btn-danger-icon" onclick="window.deleteChannel('${c.name}')" title="Eliminar Canal" style="height: 30px; width: 30px; border-radius: 6px; display: flex; align-items: center; justify-content: center; background: rgba(255,51,51,0.15); border: 1px solid rgba(255,51,51,0.3); color: #ff4d4d; flex-shrink: 0;">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>

            </div>
        `;
    }).join('');
}

function renderHomeChannelsCards(channels, activeChannel) {
    const container = document.getElementById("channels-cards-container");
    if (!container) return;

    if (!channels || channels.length === 0) {
        container.innerHTML = `
            <div class="glass-panel" style="padding: 20px; text-align: center; color: var(--color-text-dim); font-size: 11px; width: 100%;">
                <i class="fa-solid fa-folder-plus" style="font-size: 24px; margin-bottom: 8px; opacity: 0.5;"></i>
                <div>No hay canales vinculados todavía. Ve a <strong>Ajustes Generales</strong> para vincular un canal de YouTube.</div>
            </div>
        `;
        return;
    }

    container.innerHTML = channels.map(c => {
        const isActive = c.name === activeChannel;
        const color = c.theme_color || '#e50914';
        const themeText = getChannelTheme(c);
        const langText = (c.language || 'es').toUpperCase();

        return `
            <div class="channel-card ${isActive ? 'active' : ''}" style="border-top: 3px solid ${color}; cursor: pointer;" onclick="window.selectActiveChannel('${c.name}')">
                <div class="channel-card-header" style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 800; font-size: 13px; color: #fff;">${c.name}</span>
                    ${isActive ? '<span class="badge badge-accent" style="font-size: 9px;"><i class="fa-solid fa-circle-check"></i> ACTIVO</span>' : ''}
                </div>
                <div style="font-size: 10px; color: var(--color-text-dim); margin-top: 6px; display: flex; align-items: center; gap: 6px;">
                    <i class="fa-solid fa-masks-theater"></i> ${themeText}
                    <span style="background: rgba(0,255,204,0.1); color: #00ffcc; font-size: 8px; padding: 1px 4px; border-radius: 4px; font-weight: 700;">${langText}</span>
                </div>
                <div style="display: flex; gap: 6px; margin-top: 12px;">
                    ${!isActive ? `<button class="btn btn-sm btn-accent" style="width: 100%; font-size: 10px;" onclick="event.stopPropagation(); window.selectActiveChannel('${c.name}')"><i class="fa-solid fa-check"></i> Seleccionar Canal</button>` : `<button class="btn btn-sm btn-secondary" style="width: 100%; font-size: 10px;" onclick="event.stopPropagation(); window.openPromptsModal('${c.name}')"><i class="fa-solid fa-scroll"></i> Ver Prompts</button>`}
                </div>
            </div>
        `;
    }).join('');
}

export async function loadChannelsList() {
    try {
        const res = await fetch(`${API_BASE}/channels`);
        if (!res.ok) return;

        const data = await res.json();
        const channels = data.channels || [];
        const activeChannel = data.active_channel;

        window.cachedChannelsList = channels;

        renderChannelsGrid(channels, activeChannel);
        renderHomeChannelsCards(channels, activeChannel);
        updateGlobalChannelDropdown(channels, activeChannel);

    } catch (e) {
        console.error("Error cargando lista de canales:", e);
    }
}

function updateGlobalChannelDropdown(channels, activeChannel) {
    const dropdown = document.getElementById("global-channel-dropdown");
    if (!dropdown) return;

    if (!channels || channels.length === 0) {
        dropdown.innerHTML = `<option value="">Sin Canales</option>`;
        return;
    }

    dropdown.innerHTML = channels.map(c => `
        <option value="${c.name}" ${c.name === activeChannel ? 'selected' : ''}>
            ${c.name} (${c.theme || c.platform}) [${(c.language || 'es').toUpperCase()}]
        </option>
    `).join('');

    dropdown.style.borderLeft = `3px solid ${channels.find(c => c.name === activeChannel)?.theme_color || '#e50914'}`;
}

export function setupChannelsSettingsListeners() {
    window.selectActiveChannel = async (channelName) => {
        try {
            const res = await fetch(`${API_BASE}/channels/select`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ channel_name: channelName })
            });

            if (res.ok) {
                await loadChannelsList();
                window.dispatchEvent(new CustomEvent("channelChanged", { detail: { channelName } }));
            }
        } catch (e) {
            console.error("Error cambiando de canal activo:", e);
        }
    };

    window.openEditChannelModal = (channelName) => {
        const channels = window.cachedChannelsList || [];
        const ch = channels.find(c => c.name === channelName);
        if (!ch) return;

        currentEditingChannel = channelName;
        const modal = document.getElementById("edit-channel-modal");
        const titleEl = document.getElementById("edit-channel-name-title");
        const themeInput = document.getElementById("edit-channel-theme");
        const langSelect = document.getElementById("edit-channel-language");
        const colorInput = document.getElementById("edit-channel-color");

        if (titleEl) titleEl.textContent = channelName;
        if (themeInput) themeInput.value = ch.theme || "";
        if (langSelect) langSelect.value = ch.language || "es";
        if (colorInput) colorInput.value = ch.theme_color || "#e50914";

        if (modal) modal.style.display = "flex";
    };

    const btnSaveChannelSettings = document.getElementById("btn-save-channel-settings");
    if (btnSaveChannelSettings) {
        btnSaveChannelSettings.addEventListener("click", async () => {
            if (!currentEditingChannel) return;
            const theme = document.getElementById("edit-channel-theme")?.value || "General";
            const language = document.getElementById("edit-channel-language")?.value || "es";
            const theme_color = document.getElementById("edit-channel-color")?.value || "#e50914";

            try {
                const res = await fetch(`${API_BASE}/channels/${currentEditingChannel}/theme`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ theme, language, theme_color })
                });
                if (res.ok) {
                    const modal = document.getElementById("edit-channel-modal");
                    if (modal) modal.style.display = "none";
                    await loadChannelsList();
                } else {
                    alert("Error guardando la configuración del canal.");
                }
            } catch (e) {
                console.error("Error guardando canal:", e);
            }
        });
    }

    const btnCancelChannelSettings = document.getElementById("btn-cancel-channel-settings");
    const btnCloseEditModal = document.getElementById("close-edit-channel-modal-btn");
    const closeEditModal = () => {
        const modal = document.getElementById("edit-channel-modal");
        if (modal) modal.style.display = "none";
    };
    if (btnCancelChannelSettings) btnCancelChannelSettings.addEventListener("click", closeEditModal);
    if (btnCloseEditModal) btnCloseEditModal.addEventListener("click", closeEditModal);

    window.updateChannelColor = async (channelName, color) => {
        const channels = window.cachedChannelsList || [];
        const ch = channels.find(c => c.name === channelName);
        const currentTheme = ch ? ch.theme : "General";
        const currentLang = ch ? ch.language : "es";

        try {
            await fetch(`${API_BASE}/channels/${channelName}/theme`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ theme: currentTheme, language: currentLang, theme_color: color })
            });
            await loadChannelsList();
        } catch (e) {
            console.error("Error actualizando color:", e);
        }
    };

    window.deleteChannel = async (channelName) => {
        if (!confirm(`¿Eliminar el canal '${channelName}' y su configuración?`)) return;
        try {
            await fetch(`${API_BASE}/channels/${channelName}`, { method: "DELETE" });
            await loadChannelsList();
        } catch (e) {
            alert("Error eliminando el canal");
        }
    };

    window.openPromptsModal = async (channelName) => {
        currentEditingChannel = channelName;
        const modal = document.getElementById("prompts-manager-modal");
        const titleEl = document.getElementById("prompt-channel-title");
        if (titleEl) titleEl.textContent = channelName;
        if (modal) modal.style.display = "flex";
        
        resetPromptEditor();
        await loadChannelPrompts(channelName);
    };

    // Formulario de agregar canal
    const btnAddChannel = document.getElementById("btn-add-channel");
    const handleAddChannel = async (e) => {
        if (e) e.preventDefault();
        const name = document.getElementById("new-channel-name")?.value;
        const platform = document.getElementById("new-channel-platform")?.value || "YouTube";
        const language = document.getElementById("new-channel-language")?.value || "es";
        const color = document.getElementById("new-channel-theme-color")?.value || "#e50914";

        if (!name) return alert("Por favor ingresa el nombre del canal.");

        try {
            const res = await fetch(`${API_BASE}/channels`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, theme: platform, language, theme_color: color })
            });

            if (!res.ok) {
                const errData = await res.json();
                return alert(errData.detail || "Error al crear el canal");
            }

            document.getElementById("new-channel-name").value = "";
            await loadChannelsList();
            alert(`¡Canal '${name}' vinculado con éxito!`);
        } catch (e) {
            console.error("Error agregando canal:", e);
            alert("Error de conexión al agregar canal");
        }
    };

    if (btnAddChannel) {
        btnAddChannel.addEventListener("click", handleAddChannel);
    }

    setupPromptsManagerListeners();
}

async function loadChannelPrompts(channelName) {
    const container = document.getElementById("prompts-list-container");
    if (!container) return;
    container.innerHTML = `<div style="color: var(--color-text-dim); text-align: center; font-size: 11px;">Cargando prompts...</div>`;

    try {
        const res = await fetch(`${API_BASE}/channels/${channelName}/prompts`);
        if (!res.ok) return;

        channelPromptsList = await res.json();
        renderPromptsList(channelPromptsList);
    } catch (e) {
        console.error("Error cargando prompts del canal:", e);
        container.innerHTML = `<div style="color: #ff4444; font-size: 11px;">Error cargando prompts.</div>`;
    }
}

function renderPromptsList(prompts) {
    const container = document.getElementById("prompts-list-container");
    if (!container) return;

    if (!prompts || prompts.length === 0) {
        container.innerHTML = `<div style="color: var(--color-text-dim); text-align: center; font-size: 11px; padding: 10px;">No hay prompts guardados para este canal.</div>`;
        return;
    }

    container.innerHTML = prompts.map(p => `
        <div class="prompt-item-card" data-id="${p.id}" style="background: rgba(255,255,255,0.03); border: 1px solid var(--color-border); border-radius: 8px; padding: 10px; cursor: pointer; display: flex; align-items: center; justify-content: space-between; transition: all 0.2s;">
            <div style="flex-grow: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <div style="font-weight: 700; font-size: 12px; color: var(--color-text-main);">${p.title}</div>
                <div style="font-size: 10px; color: var(--color-text-dim);">${p.category || 'Shorts'}</div>
            </div>
            <button class="btn btn-sm btn-danger-icon delete-prompt-btn" data-id="${p.id}" style="padding: 4px 8px; font-size: 10px;">
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `).join('');

    container.querySelectorAll(".prompt-item-card").forEach(card => {
        card.addEventListener("click", (e) => {
            if (e.target.closest(".delete-prompt-btn")) return;
            const promptId = card.getAttribute("data-id");
            const selectedPrompt = prompts.find(p => p.id === promptId);
            if (selectedPrompt) {
                populatePromptEditor(selectedPrompt);
            }
        });
    });

    container.querySelectorAll(".delete-prompt-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const promptId = btn.getAttribute("data-id");
            if (!confirm(`¿Eliminar el prompt '${promptId}'?`)) return;

            try {
                const res = await fetch(`${API_BASE}/channels/${currentEditingChannel}/prompts/${promptId}`, {
                    method: "DELETE"
                });
                if (res.ok) {
                    channelPromptsList = await res.json();
                    renderPromptsList(channelPromptsList);
                    resetPromptEditor();
                }
            } catch (err) {
                console.error("Error eliminando prompt:", err);
            }
        });
    });
}

function populatePromptEditor(prompt) {
    const pane = document.getElementById("prompt-editor-pane");
    if (pane) {
        pane.style.opacity = "1";
        pane.style.pointerEvents = "auto";
    }

    const titleInput = document.getElementById("prompt-title-input");
    const categoryInput = document.getElementById("prompt-category-input");
    const bodyInput = document.getElementById("prompt-body-input");

    if (titleInput) titleInput.value = prompt.title || "";
    if (categoryInput) categoryInput.value = prompt.category || "Shorts";
    if (bodyInput) bodyInput.value = prompt.prompt || "";
}

function resetPromptEditor() {
    const pane = document.getElementById("prompt-editor-pane");
    if (pane) {
        pane.style.opacity = "0.5";
        pane.style.pointerEvents = "none";
    }

    const titleInput = document.getElementById("prompt-title-input");
    const categoryInput = document.getElementById("prompt-category-input");
    const bodyInput = document.getElementById("prompt-body-input");

    if (titleInput) titleInput.value = "";
    if (categoryInput) categoryInput.value = "Shorts";
    if (bodyInput) bodyInput.value = "";
}

function setupPromptsManagerListeners() {
    const modal = document.getElementById("prompts-manager-modal");
    const btnClose = document.getElementById("close-prompts-modal-btn");
    if (btnClose && modal) {
        btnClose.addEventListener("click", () => {
            modal.style.display = "none";
        });
    }

    const btnNewPrompt = document.getElementById("btn-new-prompt");
    if (btnNewPrompt) {
        btnNewPrompt.addEventListener("click", () => {
            populatePromptEditor({
                id: "",
                title: "Nuevo_Prompt",
                category: "Shorts",
                prompt: ""
            });
        });
    }

    const btnSavePrompt = document.getElementById("btn-save-prompt");
    if (btnSavePrompt) {
        btnSavePrompt.addEventListener("click", async () => {
            if (!currentEditingChannel) return;

            const title = document.getElementById("prompt-title-input")?.value;
            const category = document.getElementById("prompt-category-input")?.value || "Shorts";
            const prompt = document.getElementById("prompt-body-input")?.value;

            if (!title || !prompt) {
                return alert("Ingresa un título y las instrucciones del prompt.");
            }

            try {
                const res = await fetch(`${API_BASE}/channels/${currentEditingChannel}/prompts`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, category, prompt })
                });

                if (res.ok) {
                    channelPromptsList = await res.json();
                    renderPromptsList(channelPromptsList);
                    alert("Prompt guardado con éxito.");
                } else {
                    alert("Error guardando el prompt.");
                }
            } catch (e) {
                console.error("Error guardando prompt:", e);
            }
        });
    }

    const btnImport = document.getElementById("btn-import-prompts");
    const inputImport = document.getElementById("import-prompts-input");
    if (btnImport && inputImport) {
        btnImport.addEventListener("click", () => inputImport.click());

        inputImport.addEventListener("change", async (e) => {
            const files = e.target.files;
            if (!files || files.length === 0 || !currentEditingChannel) return;

            for (let file of files) {
                const text = await file.text();
                const title = file.name.replace(/\.txt$/i, "");
                await fetch(`${API_BASE}/channels/${currentEditingChannel}/prompts`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        title: title,
                        category: "Shorts",
                        prompt: text
                    })
                });
            }

            alert("Prompts importados con éxito.");
            await loadChannelPrompts(currentEditingChannel);
            inputImport.value = "";
        });
    }

    const btnGenerateStory = document.getElementById("btn-generate-story-prompt");
    if (btnGenerateStory) {
        btnGenerateStory.addEventListener("click", async () => {
            if (!currentEditingChannel) return;

            btnGenerateStory.disabled = true;
            btnGenerateStory.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generando con Groq...`;

            try {
                const res = await fetch(`${API_BASE}/channels/${currentEditingChannel}/generate-story-prompt`, {
                    method: "POST"
                });

                const data = await res.json();
                if (res.ok && data.status === "success") {
                    channelPromptsList = data.prompts || [];
                    renderPromptsList(channelPromptsList);

                    populatePromptEditor({
                        id: data.title,
                        title: data.title,
                        category: "Shorts",
                        prompt: data.prompt
                    });

                    alert(`¡Prompt '${data.title}' generado y adaptado para ${currentEditingChannel} con éxito!`);
                } else {
                    alert("Error al generar el prompt de historia: " + (data.detail || "Error desconocido"));
                }
            } catch (err) {
                console.error("Error conectando con Groq:", err);
                alert("Error de conexión al generar el prompt con Groq.");
            } finally {
                btnGenerateStory.disabled = false;
                btnGenerateStory.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Generar Prompt de Historia`;
            }
        });
    }
}

export async function initChannelsModule() {
    await loadChannelsList();
    setupChannelsSettingsListeners();
}

