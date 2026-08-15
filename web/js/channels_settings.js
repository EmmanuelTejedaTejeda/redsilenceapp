// ShortNexus Studio - Módulo de Canales y Ajustes
import { API_BASE } from './api.js';

let currentEditingChannel = null;

export async function initChannelsModule() {
    await loadChannelsList();
    setupEventListeners();
}

export async function loadChannelsList() {
    try {
        const res = await fetch(`${API_BASE}/channels`);
        if (!res.ok) return;
        const data = await res.json();
        
        renderChannelsGrid(data.channels, data.active_channel);
        renderHomeChannelsCards(data.channels, data.active_channel);
        updateActiveChannelDropdown(data.channels, data.active_channel);
    } catch (e) {
        console.error("Error cargando canales:", e);
    }
}

function getChannelTheme(channel) {
    if (!channel) return 'General';
    return channel.theme || channel.platform || 'YouTube';
}

function renderChannelsGrid(channels, activeChannel) {
    const container = document.getElementById("channels-list-container");
    if (!container) return;

    if (!channels || channels.length === 0) {
        container.innerHTML = `<div style="color: var(--color-text-dim); text-align: center; padding: 20px; font-size: 11px;">No hay canales vinculados todavía. Usa el formulario de abajo para agregar uno.</div>`;
        return;
    }

    container.innerHTML = channels.map(c => {
        const isActive = c.name === activeChannel;
        const color = c.theme_color || '#e50914';
        const themeText = getChannelTheme(c);
        const secretName = c.credential_file || c.secret_path ? (c.credential_file || c.secret_path).split(/[\\/]/).pop() : 'Sin credencial OAuth2';

        return `
            <div class="channel-item ${isActive ? 'active-channel-card' : ''}" style="border-left: 3px solid ${color};">
                <div class="channel-item-main">
                    <div class="channel-item-header">
                        <span class="channel-name-title">${c.name}</span>
                        ${isActive ? '<span class="active-badge"><i class="fa-solid fa-check-circle"></i> ACTIVO</span>' : ''}
                    </div>
                    <div class="channel-item-info">
                        <span><i class="fa-solid fa-tag"></i> ${themeText}</span>
                        <span title="${secretName}"><i class="fa-solid fa-key"></i> ${secretName}</span>
                    </div>
                </div>

                <div class="channel-actions-row">
                    <div class="color-picker-input-wrapper" title="Cambiar color del canal">
                        <input type="color" value="${color}" onchange="window.updateChannelColor('${c.name}', this.value)">
                    </div>
                    <button class="btn btn-sm btn-secondary" onclick="window.openPromptsModal('${c.name}')" title="Prompts Master">
                        <i class="fa-solid fa-scroll"></i> Prompts
                    </button>
                    ${!isActive ? `<button class="btn btn-sm btn-accent" onclick="window.selectActiveChannel('${c.name}')">Activar</button>` : ''}
                    <button class="btn btn-sm btn-danger-icon" onclick="window.deleteChannel('${c.name}')" title="Eliminar Canal">
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

        return `
            <div class="channel-card ${isActive ? 'active' : ''}" style="border-top: 3px solid ${color}; cursor: pointer;" onclick="window.selectActiveChannel('${c.name}')">
                <div class="channel-card-header" style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 800; font-size: 13px; color: #fff;">${c.name}</span>
                    ${isActive ? '<span class="badge badge-accent" style="font-size: 9px;"><i class="fa-solid fa-circle-check"></i> ACTIVO</span>' : ''}
                </div>
                <div style="font-size: 10px; color: var(--color-text-dim); margin-top: 6px;">
                    <i class="fa-solid fa-masks-theater"></i> ${themeText}
                </div>
                <div style="display: flex; gap: 6px; margin-top: 12px;">
                    ${!isActive ? `<button class="btn btn-sm btn-accent" style="width: 100%; font-size: 10px;" onclick="event.stopPropagation(); window.selectActiveChannel('${c.name}')"><i class="fa-solid fa-check"></i> Seleccionar Canal</button>` : `<button class="btn btn-sm btn-secondary" style="width: 100%; font-size: 10px;" onclick="event.stopPropagation(); window.openPromptsModal('${c.name}')"><i class="fa-solid fa-scroll"></i> Ver Prompts</button>`}
                </div>
            </div>
        `;
    }).join('');
}

function updateActiveChannelDropdown(channels, activeChannel) {
    const select = document.getElementById("global-channel-dropdown");
    if (!select) return;

    if (!channels || channels.length === 0) {
        select.innerHTML = `<option value="">Sin canales guardados</option>`;
        return;
    }

    select.innerHTML = channels.map(c => {
        const themeText = getChannelTheme(c);
        const selectedAttr = c.name === activeChannel ? 'selected' : '';
        return `<option value="${c.name}" ${selectedAttr}>${c.name} (${themeText})</option>`;
    }).join('');
}

function setupEventListeners() {
    const btnGenerateThemes = document.getElementById("btn-generate-themes");
    if (btnGenerateThemes) {
        btnGenerateThemes.addEventListener("click", async () => {
            const originalHTML = btnGenerateThemes.innerHTML;
            btnGenerateThemes.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generando...';
            btnGenerateThemes.disabled = true;

            try {
                const res = await fetch(`${API_BASE}/channels/generate-themes`, { method: "POST" });
                if (!res.ok) {
                    throw new Error("Error al generar temáticas");
                }
                const data = await res.json();
                console.log("Temáticas generadas:", data.themes);
                
                // Mostrar alerta
                let themesHtml = "<div style='text-align: left; margin-top: 10px; font-size: 11px; background: rgba(0,0,0,0.5); padding: 10px; border-radius: 6px;'>";
                for (const [ch, theme] of Object.entries(data.themes)) {
                    themesHtml += `<div style="margin-bottom: 4px;"><strong style="color: var(--color-accent);">${ch}:</strong> ${theme}</div>`;
                }
                themesHtml += "</div>";

                if (typeof Swal !== "undefined") {
                    Swal.fire({
                        title: '¡Temáticas Generadas!',
                        html: `Se han deducido las estéticas para todos los canales basándose en sus prompts en disco:<br>${themesHtml}`,
                        icon: 'success',
                        background: '#1a1a1a',
                        color: '#fff',
                        confirmButtonColor: '#e50914'
                    });
                } else {
                    alert("Temáticas generadas con éxito.");
                }
            } catch (e) {
                console.error(e);
                alert("Ocurrió un error al generar las temáticas.");
            } finally {
                btnGenerateThemes.innerHTML = originalHTML;
                btnGenerateThemes.disabled = false;
            }
        });
    }

    window.selectActiveChannel = async (channelName) => {
        if (!channelName) return;
        try {
            const res = await fetch(`${API_BASE}/channels/select`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ channel_name: channelName })
            });
            if (res.ok) {
                await loadChannelsList();
                // Notificar evento a main.js para refrescar analíticas y grafo inmediatamente
                window.dispatchEvent(new CustomEvent("channelChanged", { detail: { channelName } }));
            }
        } catch (e) {
            console.error("Error cambiando de canal activo:", e);
        }
    };

    window.updateChannelColor = async (channelName, color) => {
        try {
            await fetch(`${API_BASE}/channels/${channelName}/theme`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ theme: "Terror Analógico", theme_color: color })
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
        const modal = document.getElementById("prompts-modal");
        const titleEl = document.getElementById("prompts-modal-title");
        if (titleEl) titleEl.textContent = `Prompts Master - ${channelName}`;
        if (modal) modal.style.display = "flex";
        await loadChannelPrompts(channelName);
    };

    const closeModalBtn = document.getElementById("close-prompts-modal");
    if (closeModalBtn) {
        closeModalBtn.onclick = () => {
            const modal = document.getElementById("prompts-modal");
            if (modal) modal.style.display = "none";
        };
    }

    // Formulario de agregar canal
    const addChannelForm = document.getElementById("add-channel-form");
    if (addChannelForm) {
        addChannelForm.onsubmit = async (e) => {
            e.preventDefault();
            const name = document.getElementById("new-channel-name")?.value;
            const theme = document.getElementById("new-channel-theme")?.value;
            const color = document.getElementById("new-channel-color")?.value || "#e50914";

            if (!name || !theme) return alert("Por favor ingresa nombre y temática del canal.");

            try {
                const res = await fetch(`${API_BASE}/channels`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, theme, theme_color: color })
                });

                if (!res.ok) {
                    const err = await res.json();
                    return alert(err.detail || "Error agregando el canal");
                }

                document.getElementById("new-channel-name").value = "";
                await loadChannelsList();
            } catch (err) {
                alert("Error al guardar el canal.");
            }
        };
    }
}

async function loadChannelPrompts(channelName) {
    try {
        const res = await fetch(`${API_BASE}/channels/${channelName}/prompts`);
        const prompts = await res.json();
        const container = document.getElementById("prompts-modal-list");
        if (!container) return;

        if (!prompts || prompts.length === 0) {
            container.innerHTML = `<div style="color: var(--color-text-dim); text-align: center; padding: 15px; font-size: 11px;">No hay Prompts Master creados para este canal.</div>`;
            return;
        }

        container.innerHTML = prompts.map(p => `
            <div class="prompt-card-item" style="background: rgba(0,0,0,0.3); border: 1px solid var(--color-border); padding: 10px; border-radius: 8px; margin-bottom: 8px;">
                <div style="font-weight: 700; font-size: 11px; color: var(--color-accent);">${p.title}</div>
                <div style="font-size: 9px; color: var(--color-text-dim); margin-bottom: 4px;">Categoría: ${p.category}</div>
                <div style="font-size: 10px; background: rgba(0,0,0,0.4); padding: 6px; border-radius: 4px; font-family: monospace; white-space: pre-wrap;">${p.prompt.slice(0, 150)}...</div>
            </div>
        `).join('');
    } catch (e) {
        console.error("Error cargando prompts master:", e);
    }
}
