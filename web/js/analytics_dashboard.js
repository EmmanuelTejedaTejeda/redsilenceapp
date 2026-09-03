// ShortNexus Studio - Módulo de Analytics, Estadísticas y Lista de Vídeos
import { API_BASE } from './api.js';

let viewsChartInstance = null;
let currentChannelVideos = [];

export async function initAnalyticsModule(channelName) {
    if (!channelName) return;

    setupVideosViewEvents(channelName);

    try {
        // 1. Cargar analíticas generales del canal
        const resStats = await fetch(`${API_BASE}/analytics/${channelName}`);
        if (resStats.ok) {
            const data = await resStats.json();
            updateStatCards(data);
            const history = data.daily_history || data.history || data.daily_analytics || data.daily_data || [];
            renderViewsChart(history);
        }

        // 2. Cargar listado de vídeos del canal
        await loadChannelVideosList(channelName, false);
    } catch (e) {
        console.error("Error cargando analíticas:", e);
    }
}

function updateStatCards(data) {
    const subsFormatted = Number(data.subscribers || 0).toLocaleString();
    const viewsFormatted = Number(data.total_views || 0).toLocaleString();
    const videosFormatted = Number(data.video_count || 0).toLocaleString();

    // Actualizar Pestaña de Métricas Avanzadas
    const kpiSubs = document.getElementById("kpi-subscribers");
    const kpiViews = document.getElementById("kpi-views");
    const kpiVideos = document.getElementById("kpi-videos");

    if (kpiSubs) kpiSubs.textContent = subsFormatted;
    if (kpiViews) kpiViews.textContent = viewsFormatted;
    if (kpiVideos) kpiVideos.textContent = videosFormatted;

    // Actualizar Panel Principal (Home)
    const homeSummaryLayout = document.getElementById("home-active-channel-summary");
    const homeSubs = document.getElementById("home-kpi-subscribers");
    const homeViews = document.getElementById("home-kpi-views");
    const homeVideos = document.getElementById("home-kpi-videos");

    if (homeSubs) homeSubs.textContent = subsFormatted;
    if (homeViews) homeViews.textContent = viewsFormatted;
    if (homeVideos) homeVideos.textContent = videosFormatted;
    if (homeSummaryLayout) homeSummaryLayout.style.display = "block";
}

function setupVideosViewEvents(channelName) {
    const sortSelect = document.getElementById("videos-sort-select");
    if (sortSelect) {
        sortSelect.onchange = () => {
            renderSortedVideos(sortSelect.value);
        };
    }

    const btnReload = document.getElementById("btn-reload-videos");
    if (btnReload) {
        btnReload.onclick = async () => {
            btnReload.disabled = true;
            btnReload.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Recargando API...`;
            await loadChannelVideosList(channelName, true);
            btnReload.disabled = false;
            btnReload.innerHTML = `<i class="fa-solid fa-rotate"></i> Recargar API`;
        };
    }

    const btnReloadMetrics = document.getElementById("btn-reload-metrics");
    if (btnReloadMetrics) {
        btnReloadMetrics.onclick = async () => {
            btnReloadMetrics.disabled = true;
            btnReloadMetrics.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Recargando...`;
            await initAnalyticsModule(channelName);
            btnReloadMetrics.disabled = false;
            btnReloadMetrics.innerHTML = `<i class="fa-solid fa-rotate"></i> Actualizar Métricas`;
        };
    }
}

export async function loadChannelVideosList(channelName, forceReload = false) {
    const container = document.getElementById("videos-list-container");
    const topListContainer = document.getElementById("metrics-top-videos-list");

    if (!channelName) return;
    try {
        const url = `${API_BASE}/analytics/videos/${channelName}${forceReload ? '?force_reload=true' : ''}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        currentChannelVideos = data.videos || [];

        // Actualizar contador de vídeos en KPI si venía en cero
        const kpiVideos = document.getElementById("kpi-videos");
        if (kpiVideos && (kpiVideos.textContent === "0" || !kpiVideos.textContent)) {
            kpiVideos.textContent = Number(currentChannelVideos.length).toLocaleString();
        }

        // Renderizar lista con el orden actual seleccionado
        const sortSelect = document.getElementById("videos-sort-select");
        const currentSort = sortSelect ? sortSelect.value : "date";
        renderSortedVideos(currentSort);

        // Renderizar Vídeos Top en Métricas Avanzadas
        if (topListContainer) {
            const sorted = [...currentChannelVideos].sort((a, b) => (b.views || 0) - (a.views || 0)).slice(0, 5);
            if (sorted.length === 0) {
                topListContainer.innerHTML = `<div style="color: var(--color-text-dim); font-size: 11px; padding: 10px;">Sin datos virales aún.</div>`;
            } else {
                topListContainer.innerHTML = sorted.map((v, idx) => `
                    <div class="top-item" style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 8px; border: 1px solid var(--color-border); cursor: pointer;" onclick="window.openVideoDetails('${v.video_id}')">
                        <div style="display: flex; align-items: center; gap: 10px; font-size: 11px;">
                            <span style="font-weight: 800; color: var(--color-accent); font-size: 13px;">#${idx + 1}</span>
                            <span style="color: #fff; font-weight: 600; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; max-width: 220px;">${v.title}</span>
                        </div>
                        <span style="font-size: 11px; font-weight: 800; color: var(--color-accent);">${Number(v.views || 0).toLocaleString()} vistas</span>
                    </div>
                `).join('');
            }
        }
    } catch (e) {
        console.error("Error cargando lista de videos:", e);
    }
}

function renderSortedVideos(sortBy) {
    const container = document.getElementById("videos-list-container");
    if (!container) return;

    if (currentChannelVideos.length === 0) {
        container.innerHTML = `<div style="color: var(--color-text-dim); text-align: center; padding: 40px; grid-column: 1/-1;">No se encontraron vídeos para este canal.</div>`;
        return;
    }

    const videosCopy = [...currentChannelVideos];

    if (sortBy === "score") {
        videosCopy.sort((a, b) => (b.score || 0) - (a.score || 0));
    } else if (sortBy === "views") {
        videosCopy.sort((a, b) => (b.views || 0) - (a.views || 0));
    } else if (sortBy === "title") {
        videosCopy.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
    } else {
        // Por fecha por defecto
        videosCopy.sort((a, b) => new Date(b.published_at || b.date || 0) - new Date(a.published_at || a.date || 0));
    }

    container.innerHTML = videosCopy.map(v => {
        const rankLetter = (v.rank || 'D').toUpperCase();
        const rankClass = `rank-${rankLetter.charAt(0).toLowerCase()}`;
        const color = v.color || v.rank_color || '#ff9f43';
        const score = v.score !== undefined ? v.score : 0;
        const hookScore = v.hook_score || 50;
        const publishedDate = v.date || (v.published_at ? v.published_at.slice(0, 10) : 'Reciente');

        return `
            <div class="video-card ${rankClass}" style="border-top: 3px solid ${color}; border-color: ${color}44; box-shadow: 0 6px 20px rgba(0,0,0,0.5);" onclick="window.openVideoDetails('${v.video_id}')">
                <div class="video-thumb-container">
                    ${v.thumbnail ? `<img src="${v.thumbnail}" alt="${v.title}" onerror="this.onerror=null; this.outerHTML='<div style=\\'display:flex; flex-direction:column; align-items:center; gap:8px; opacity:0.7;\\'><i class=\\'fa-solid fa-hourglass-half fa-spin-pulse\\' style=\\'font-size: 28px; color: ${color};\\'></i><span style=\\'font-size: 9px; font-weight: 800; color: ${color};\\'>PROCESANDO...</span></div>';">` : `<i class="fa-solid fa-play" style="font-size: 32px; color: ${color};"></i>`}
                    
                    <div style="position: absolute; top: 10px; right: 10px; background: rgba(12, 12, 16, 0.85); border: 1.5px solid ${color}; color: ${color}; font-weight: 900; font-size: 10px; padding: 4px 12px; border-radius: 20px; backdrop-filter: blur(8px); box-shadow: 0 0 12px ${color}66, inset 0 0 8px ${color}22; letter-spacing: 0.5px; text-shadow: 0 0 6px ${color}; z-index: 6;">
                        RANGO ${rankLetter} • ${score} PTS
                    </div>

                    <span class="video-duration" style="position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.8); color: #fff; font-size: 9px; padding: 2px 6px; border-radius: 4px; font-weight: 700; z-index: 5;">
                        ${v.duration || 'Short'}
                    </span>
                </div>

                <div class="video-score-circle-container" style="background: radial-gradient(circle at 30% 30%, #1e1e24, #0a0a0e); border: 2px solid ${color}; box-shadow: 0 0 15px ${color}88, 0 4px 15px rgba(0,0,0,0.9);">
                    <svg viewBox="0 0 36 36" class="circular-chart">
                        <path class="circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="3" />
                        <path class="circle" stroke="${color}" stroke-dasharray="${Math.max(15, score)}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke-width="3.5" filter="drop-shadow(0 0 4px ${color})" />
                        <text x="18" y="22" class="percentage" fill="${color}" style="font-size: 15px; font-weight: 900; font-family: 'Bebas Neue', 'Inter', sans-serif; text-shadow: 0 0 8px ${color};">${rankLetter}</text>
                    </svg>
                </div>

                <div class="video-info">
                    <h4>${v.title}</h4>
                    
                    <div class="video-metrics-row">
                        <span class="metric-pill"><i class="fa-solid fa-eye" style="color: var(--color-accent);"></i> ${Number(v.views || 0).toLocaleString()} vistas</span>
                        <span class="metric-pill"><i class="fa-solid fa-thumbs-up"></i> ${Number(v.likes || 0).toLocaleString()}</span>
                        <span class="metric-pill"><i class="fa-solid fa-comments"></i> ${Number(v.comments || 0).toLocaleString()}</span>
                    </div>

                    <div class="video-metrics-row" style="margin-top: 4px; justify-content: space-between; font-size: 10px; color: var(--color-text-dim);">
                        <span class="metric-pill"><i class="fa-solid fa-anchor" style="color: #4facfe;"></i> Hook: ${hookScore}/100</span>
                        <span class="metric-pill"><i class="fa-solid fa-calendar-day"></i> ${publishedDate}</span>
                    </div>

                    <div style="display: flex; gap: 8px; margin-top: auto; padding-top: 10px;">
                        <button class="btn btn-sm btn-secondary" style="flex: 1; font-size: 11px; padding: 8px;" onclick="event.stopPropagation(); window.openVideoDetails('${v.video_id}')">
                            <i class="fa-solid fa-circle-info" style="color: var(--color-accent);"></i> Detalle y Transcripción
                        </button>
                        <a href="${v.url || `https://youtube.com/watch?v=${v.video_id}`}" target="_blank" class="btn btn-sm btn-secondary" style="padding: 8px 12px;" onclick="event.stopPropagation();" title="Ver en YouTube">
                            <i class="fa-solid fa-external-link"></i>
                        </a>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

window.openVideoDetails = async (videoId) => {
    const modal = document.getElementById("video-details-modal");
    if (!modal) return;

    const closeBtn = document.getElementById("close-video-details-btn");
    const modalCloseBtn = document.getElementById("modal-video-close-btn");

    const closeModal = () => { modal.style.display = "none"; };

    if (closeBtn) closeBtn.onclick = closeModal;
    if (modalCloseBtn) modalCloseBtn.onclick = closeModal;
    modal.onclick = (e) => { if (e.target === modal) closeModal(); };
    window.onkeydown = (e) => { if (e.key === "Escape") closeModal(); };

    // Buscar vídeo en la lista en memoria
    const video = currentChannelVideos.find(v => v.video_id === videoId) || {};

    const localTitle = video.title || 'Detalles del Video';
    const localDate = video.date || (video.published_at ? video.published_at.slice(0, 10) : 'Reciente');
    const localViews = Number(video.views || 0).toLocaleString();
    const localType = (video.type || 'shorts').toUpperCase();
    const localScore = video.score !== undefined ? video.score : 0;
    const localRank = (video.rank || 'D').toUpperCase();
    const localColor = video.color || video.rank_color || '#ff9f43';

    document.getElementById("modal-video-title").innerHTML = `<i class="fa-solid fa-film" style="color: var(--color-accent);"></i> ${localTitle}`;
    document.getElementById("modal-video-published").innerHTML = `<i class="fa-solid fa-calendar" style="color: var(--color-accent);"></i> Publicado: ${localDate}`;
    document.getElementById("modal-video-views").innerHTML = `<i class="fa-solid fa-eye" style="color: var(--color-accent);"></i> ${localViews} vistas`;
    document.getElementById("modal-video-type").innerHTML = `<i class="fa-solid fa-video" style="color: var(--color-accent);"></i> ${localType}`;

    const badgeEl = document.getElementById("modal-video-rank-badge");
    if (badgeEl) {
        badgeEl.style.borderColor = localColor;
        badgeEl.style.color = localColor;
        badgeEl.style.background = `${localColor}22`;
        badgeEl.style.boxShadow = `0 0 12px ${localColor}66`;
        badgeEl.textContent = `Rango ${localRank} (${localScore}/100)`;
    }

    const tagsEl = document.getElementById("modal-video-tags");
    if (tagsEl) {
        const tags = video.tags || [];
        tagsEl.textContent = tags.length ? tags.map(t => `#${t.replace(/^#/, '')}`).join("  ") : "[Sin etiquetas asociadas]";
    }

    const descEl = document.getElementById("modal-video-description");
    if (descEl) descEl.value = video.description || "Cargando metadatos completos...";

    const transEl = document.getElementById("modal-video-transcript");
    if (transEl) transEl.value = "Cargando transcripción de audio desde YouTube...";

    const urlEl = document.getElementById("modal-video-url");
    if (urlEl) urlEl.href = video.url || `https://youtube.com/watch?v=${videoId}`;

    // Hide generation metadata section initially
    const genMetaSection = document.getElementById("modal-generation-meta-section");
    if (genMetaSection) genMetaSection.style.display = "none";

    modal.style.display = "flex";

    // Petición al backend para obtener transcripción y metadatos amplios
    try {
        const res = await fetch(`${API_BASE}/analytics/video-details/${videoId}`);
        if (res.ok) {
            const data = await res.json();
            
            if (descEl) descEl.value = data.description || video.description || "Sin descripción disponible para este vídeo.";
            if (transEl) transEl.value = data.transcript || "Sin transcripción disponible.";
            
            if (data.date && data.date !== "Reciente") {
                document.getElementById("modal-video-published").innerHTML = `<i class="fa-solid fa-calendar" style="color: var(--color-accent);"></i> Publicado: ${data.date}`;
            }

            if (data.score !== undefined && badgeEl) {
                const finalRank = (data.rank || localRank).toUpperCase();
                const finalColor = data.color || localColor;
                badgeEl.style.borderColor = finalColor;
                badgeEl.style.color = finalColor;
                badgeEl.style.background = `${finalColor}22`;
                badgeEl.style.boxShadow = `0 0 12px ${finalColor}66`;
                badgeEl.textContent = `Rango ${finalRank} (${data.score}/100)`;
            }

            if (data.tags && data.tags.length > 0 && tagsEl) {
                tagsEl.textContent = data.tags.map(t => `#${t.replace(/^#/, '')}`).join("  ");
            }

            // Populate generation metadata
            if (data.generation_metadata && Object.keys(data.generation_metadata).length > 0) {
                if (genMetaSection) genMetaSection.style.display = "flex";
                const g = data.generation_metadata;
                
                document.getElementById("gen-prompt-master").textContent = g.prompt_master || "-";
                document.getElementById("gen-quality").textContent = g.calidad || "-";
                document.getElementById("gen-sub-style").textContent = g.tipo_subtitulos || "-";
                document.getElementById("gen-clips-count").textContent = g.cantidad_clips !== undefined ? g.cantidad_clips : "-";
                
                let durText = "-";
                if (g.duracion_narracion) durText = typeof g.duracion_narracion === 'number' ? `${g.duracion_narracion.toFixed(1)}s` : g.duracion_narracion;
                document.getElementById("gen-narration-dur").textContent = durText;
                document.getElementById("gen-music").textContent = g.cancion || "Ninguna";
                
                let volText = "-";
                if (g.volumen_narracion !== undefined && g.volumen_cancion !== undefined) {
                    volText = `${g.volumen_narracion}% / ${g.volumen_cancion}%`;
                }
                document.getElementById("gen-volumes").textContent = volText;
                
                document.getElementById("gen-script-text").textContent = g.trama || "Sin script generado.";
            } else {
                if (genMetaSection) genMetaSection.style.display = "none";
            }
        }
    } catch (e) {
        console.error("Error al obtener detalles extendidos:", e);
    }
};

function renderViewsChart(history) {
    const canvas = document.getElementById("views-time-chart");
    if (!canvas) return;

    const labels = history.map(h => h.day || h.date || '');
    const viewsData = history.map(h => h.views || 0);

    if (viewsChartInstance) {
        viewsChartInstance.destroy();
    }

    if (window.Chart) {
        viewsChartInstance = new window.Chart(canvas, {
            type: 'line',
            data: {
                labels: labels.length ? labels : ['Día 1', 'Día 5', 'Día 10', 'Día 15', 'Día 20', 'Día 25', 'Día 30'],
                datasets: [{
                    label: 'Vistas Diarias',
                    data: viewsData.length ? viewsData : [1500, 2200, 1800, 3400, 2900, 4100, 4800],
                    borderColor: getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim() || '#e50914',
                    backgroundColor: 'rgba(229, 9, 20, 0.08)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888', font: { size: 10 } } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888', font: { size: 10 } } }
                }
            }
        });
    }
}
