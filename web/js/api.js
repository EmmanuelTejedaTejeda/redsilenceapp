// ShortNexus Studio - Módulo de Cliente API REST
export const API_BASE = "http://localhost:8000/api";

export async function fetchApi(endpoint, options = {}) {
    const url = (typeof endpoint === 'string' && endpoint.startsWith('/')) ? `${API_BASE}${endpoint}` : `${API_BASE}/${endpoint}`;
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Error HTTP: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`[API ERROR] en ${endpoint}:`, error);
        throw error;
    }
}
