// ShortNexus Studio - Módulo de Mapa Viral (Grafo Vis.js) e Auditoría IA
import { API_BASE } from './api.js';

let networkInstance = null;

async function ensureVisLoaded() {
    if (window.vis) return;
    return new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'js/vendor/vis-network.min.js';
        script.onload = () => resolve();
        script.onerror = () => resolve();
        document.head.appendChild(script);
    });
}

export async function initViralMapModule(channelName) {
    if (!channelName) return;
    try {
        await ensureVisLoaded();
        const res = await fetch(`${API_BASE}/analytics/viral-graph/${channelName}?video_type=shorts`);
        if (!res.ok) return;
        const graphData = await res.json();

        renderViralGraphNetwork(graphData);
        renderViralDiagnostic(graphData);
    } catch (e) {
        console.error("Error cargando grafo de viralidad:", e);
    }
}

function renderViralGraphNetwork(graphData) {
    const container = document.getElementById("viral-network-container");
    if (!container || !window.vis) return;

    // Asegurar estilo y altura adecuada del contenedor
    container.style.height = "520px";
    container.style.width = "100%";
    container.style.borderRadius = "12px";
    container.style.background = "rgba(0, 0, 0, 0.4)";
    container.style.border = "1px solid var(--color-border)";

    const rawNodes = graphData.nodes || [];
    const rawEdges = graphData.edges || [];

    const groupColors = ['#e50914', '#ffff00', '#00f2fe', '#4facfe', '#00ff87', '#ff0844', '#f857a6'];

    const formattedNodes = rawNodes.map((n, idx) => {
        const color = groupColors[(n.group || idx) % groupColors.length];
        return {
            id: n.id,
            label: n.label,
            value: Math.max(10, Math.min(40, (n.value || 1) * 3)),
            color: {
                background: color,
                border: '#ffffff',
                highlight: { background: '#ffffff', border: color }
            },
            font: { size: 12, color: '#ffffff', face: 'Outfit, sans-serif' },
            title: n.title || n.label
        };
    });

    const nodes = new window.vis.DataSet(formattedNodes);
    const edges = new window.vis.DataSet(rawEdges);

    const data = { nodes, edges };
    const options = {
        nodes: {
            shape: 'dot',
            borderWidth: 2,
            shadow: true
        },
        edges: {
            width: 1.5,
            color: { color: 'rgba(255,255,255,0.2)', highlight: '#ffff00' },
            smooth: { type: 'continuous' }
        },
        physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -40,
                centralGravity: 0.01,
                springLength: 120,
                springConstant: 0.08
            },
            maxVelocity: 50,
            timestep: 0.5,
            stabilization: { iterations: 150 }
        },
        interaction: {
            hover: true,
            zoomView: true,
            dragView: true
        }
    };

    if (networkInstance) {
        networkInstance.destroy();
    }

    networkInstance = new window.vis.Network(container, data, options);

    networkInstance.once("stabilizationIterationsDone", () => {
        networkInstance.fit();
    });
}

function renderViralDiagnostic(graphData) {
    const diagContainer = document.getElementById("viral-diagnostic-container");
    if (!diagContainer) return;

    const wordData = graphData.word_data || [];
    if (wordData.length === 0) {
        diagContainer.innerHTML = `<p class="text-dim" style="font-size: 11px;">El mapa necesita más vídeos publicados para generar patrones de retención.</p>`;
        return;
    }

    const topKeywords = wordData.slice(0, 4).map(w => `<strong style="color: var(--color-accent);">${w.word}</strong>`).join(', ');

    diagContainer.innerHTML = `
        <div style="font-size: 11px; color: #fff; background: rgba(255,255,255,0.04); padding: 10px; border-radius: 8px; border: 1px solid var(--color-border);">
            <div style="font-weight: 700; color: var(--color-accent); margin-bottom: 4px;"><i class="fa-solid fa-fire"></i> Pilares de Alta Retención</div>
            <div>Las palabras con mayor CTR e impacto de retención en tu canal son: ${topKeywords}.</div>
        </div>
        <div style="font-size: 11px; color: var(--color-text-dim); background: rgba(0,0,0,0.3); padding: 10px; border-radius: 8px;">
            <i class="fa-solid fa-bullseye"></i> Haz clic en "Auditar con IA" para obtener un análisis de oportunidades de contenido en base a estos pilares.
        </div>
    `;
}

export async function generateViralAuditReport(channelName) {
    const container = document.getElementById("viral-ai-insights-container");
    if (!container) return;

    container.style.display = "block";
    container.innerHTML = `<div style="text-align: center; padding: 15px; color: var(--color-accent);"><i class="fa-solid fa-spinner fa-spin"></i> Generando informe estocástico con Groq IA...</div>`;

    try {
        const res = await fetch(`${API_BASE}/analytics/viral-audit/${channelName}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ video_type: "shorts" })
        });
        const data = await res.json();

        if (res.ok && data.report) {
            container.innerHTML = `<div style="white-space: pre-wrap; font-family: inherit;">${data.report}</div>`;
        } else {
            container.innerHTML = `<div style="color: #ff4d4d;">${data.detail || 'Error al conectar con la API de IA.'}</div>`;
        }
    } catch (e) {
        container.innerHTML = `<div style="color: #ff4d4d;">Error al generar auditoría.</div>`;
    }
}

window.loadViralAiInsights = function() {
    const channelSelect = document.getElementById("global-channel-dropdown");
    const ch = channelSelect ? channelSelect.value : null;
    if (ch) generateViralAuditReport(ch);
};
