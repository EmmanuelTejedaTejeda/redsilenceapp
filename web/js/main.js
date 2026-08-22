import { API_BASE } from './api.js?v=18';
import { initChannelsModule } from './channels_settings.js?v=18';
import { initShortsWizardModule } from './shorts_wizard.js?v=18';
import { initAnalyticsModule } from './analytics_dashboard.js?v=18';
import { initViralMapModule, generateViralAuditReport } from './viral_map.js?v=18';
import { initSubtitlesStudioModule } from './subtitles_studio.js?v=18';

document.addEventListener("DOMContentLoaded", async () => {
    console.log("🚀 ShortNexus Studio Web App Inicializada");

    // 1. Configurar navegación de Pestañas de la Barra Lateral y Accesos Rápidos
    setupNavigation();

    // 2. Configurar Modal de Ajustes de Carpetas
    setupFoldersModal();

    // 3. Inicializar Módulo de Canales
    try {
        await initChannelsModule();
    } catch (e) {
        console.error("⚠️ Error inicializando Módulo de Canales:", e);
    }

    // 4. Inicializar Módulo del Wizard de Shorts
    try {
        await initShortsWizardModule();
    } catch (e) {
        console.error("⚠️ Error inicializando Módulo del Wizard de Shorts:", e);
    }

    // 5. Inicializar Estudio de Subtítulos
    try {
        await initSubtitlesStudioModule();
    } catch (e) {
        console.error("⚠️ Error inicializando Módulo del Estudio de Subtítulos:", e);
    }

    // 6. Obtener canal activo y aplicar color de interfaz
    try {
        await updateActiveChannelThemeAndModules();
    } catch (e) {
        console.error("⚠️ Error actualizando tema de canal activo:", e);
    }

    // Evento de cambio en la lista desplegable global
    const activeChannelSelect = document.getElementById("global-channel-dropdown");
    if (activeChannelSelect) {
        activeChannelSelect.addEventListener("change", (e) => {
            const ch = e.target.value;
            if (ch && window.selectActiveChannel) {
                window.selectActiveChannel(ch);
            }
        });
    }

    // Escuchar evento custom de cambio de canal para refrescar módulos y tema
    window.addEventListener("channelChanged", async () => {
        await updateActiveChannelThemeAndModules();
        if (typeof window.loadServerAudios === "function") window.loadServerAudios();
        if (typeof window.loadTimelineClips === "function") window.loadTimelineClips();
        if (typeof window.loadLastRenderedVideoPreview === "function") window.loadLastRenderedVideoPreview();
    });

    // Botón de Auditoría con IA
    const btnAudit = document.getElementById("btn-generate-audit");
    if (btnAudit) {
        btnAudit.addEventListener("click", () => {
            const activeChannelSelect = document.getElementById("global-channel-dropdown");
            const ch = activeChannelSelect ? activeChannelSelect.value : null;
            if (ch) generateViralAuditReport(ch);
        });
    }

    // Botón de Reiniciar Servidor
    const btnRestart = document.getElementById("btn-restart-server");
    if (btnRestart) {
        btnRestart.addEventListener("click", async () => {
            if (confirm("¿Deseas reiniciar el servidor del sistema?")) {
                try {
                    await fetch(`${API_BASE}/restart-server`, { method: "POST" });
                } catch (e) {
                    // Servidor reiniciándose
                }
                setTimeout(() => window.location.reload(), 2000);
            }
        });
    }
});

async function updateActiveChannelThemeAndModules() {
    try {
        const res = await fetch(`${API_BASE}/channels`);
        if (!res.ok) return;
        const data = await res.json();
        const activeName = data.active_channel;
        const activeChannel = (data.channels || []).find(c => c.name === activeName);

        if (activeChannel && activeChannel.theme_color) {
            applyInterfaceThemeColor(activeChannel.theme_color);
        } else {
            applyInterfaceThemeColor("#e50914");
        }

        if (activeName) {
            initAnalyticsModule(activeName);
            initViralMapModule(activeName);
        }
    } catch (e) {
        console.error("Error actualizando tema del canal activo:", e);
    }
}

function applyInterfaceThemeColor(color) {
    if (!color) color = "#e50914";
    document.documentElement.style.setProperty('--color-primary', color);
    document.documentElement.style.setProperty('--color-accent', color);
    document.documentElement.style.setProperty('--color-primary-glow', `${color}4D`);
}

export function switchToTab(tabName) {
    if (!tabName) return;

    const cleanTabName = tabName.replace(/^#/, '').replace(/^tab-/, '');

    // Actualizar clase active en los elementos del menú lateral
    const menuItems = document.querySelectorAll(".menu-item");
    menuItems.forEach(item => {
        const itemDataTab = item.getAttribute("data-tab");
        const itemHref = (item.getAttribute("href") || "").replace(/^#/, '');
        const targetName = itemDataTab || itemHref;

        if (targetName === cleanTabName) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    // Ocultar/Mostrar secciones .tab-section
    const tabSections = document.querySelectorAll(".tab-section");
    tabSections.forEach(section => {
        const sectionTabName = section.id.replace(/^tab-/, '');
        if (sectionTabName === cleanTabName) {
            section.classList.add("active");
            section.style.display = "block";
        } else {
            section.classList.remove("active");
            section.style.display = "none";
        }
    });
}

window.switchToTab = switchToTab;

function setupNavigation() {
    document.addEventListener("click", (e) => {
        const link = e.target.closest("a[data-tab], a[href^='#'], .menu-item, .action-card");
        if (!link) return;

        if (link.id === "menu-folders-settings") {
            e.preventDefault();
            openFoldersModal();
            return;
        }

        const dataTab = link.getAttribute("data-tab");
        const href = link.getAttribute("href");

        if (dataTab) {
            e.preventDefault();
            switchToTab(dataTab);
        } else if (href && href.startsWith("#") && href.length > 1) {
            e.preventDefault();
            switchToTab(href.substring(1));
        }
    });
}

async function openFoldersModal() {
    const modal = document.getElementById("folders-settings-modal");
    if (!modal) return;

    try {
        const res = await fetch(`${API_BASE}/channels/folders`);
        if (res.ok) {
            const data = await res.json();
            const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ""; };
            
            const titleEl = document.getElementById("folders-modal-channel-title");
            if (titleEl && data.channel_name) {
                titleEl.textContent = data.channel_name;
            }

            setVal("modal-folder-audio", data.audio_folder_path);
            setVal("modal-folder-music", data.music_folder_path);
            setVal("modal-folder-images", data.images_folder_path);
            setVal("modal-folder-videos", data.videos_folder_path);
            setVal("modal-folder-renders", data.renders_folder_path);
            setVal("modal-folder-downloader", data.downloader_folder_path);
        }
    } catch (e) {
        console.error("Error cargando carpetas:", e);
    }

    modal.style.display = "flex";
}

function setupFoldersModal() {
    const modal = document.getElementById("folders-settings-modal");
    const closeBtn = document.getElementById("close-folders-modal-btn");
    const cancelBtn = document.getElementById("btn-cancel-folders");
    const saveBtn = document.getElementById("btn-save-folders");

    const closeModal = () => { if (modal) modal.style.display = "none"; };

    if (closeBtn) closeBtn.onclick = closeModal;
    if (cancelBtn) cancelBtn.onclick = closeModal;

    if (saveBtn) {
        saveBtn.onclick = async () => {
            const getVal = (id) => document.getElementById(id)?.value || "";
            const payload = {
                audio_folder_path: getVal("modal-folder-audio"),
                music_folder_path: getVal("modal-folder-music"),
                images_folder_path: getVal("modal-folder-images"),
                videos_folder_path: getVal("modal-folder-videos"),
                renders_folder_path: getVal("modal-folder-renders"),
                downloader_folder_path: getVal("modal-folder-downloader")
            };

            saveBtn.disabled = true;
            saveBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Guardando...`;

            try {
                const res = await fetch(`${API_BASE}/channels/folders`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    closeModal();
                    window.dispatchEvent(new Event("foldersChanged"));
                } else {
                    const errText = await res.text();
                    alert(`Error al guardar las rutas de carpetas: ${errText}`);
                }
            } catch (e) {
                alert(`Error al guardar las rutas de carpetas: ${e.message}`);
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Guardar Ajustes`;
            }
        };
    }
}
