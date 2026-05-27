function resolveApiBase() {
    const fallbackOrigin = "http://127.0.0.1:8001";
    const { protocol, origin } = window.location;

    // Use same-origin API whenever the frontend is served over HTTP(S).
    if (protocol === "http:" || protocol === "https:") {
        return `${origin}/api`;
    }

    return `${fallbackOrigin}/api`;
}

const API_BASE = resolveApiBase();
const AUTH_STORAGE_KEY = "seas_auth_token";

let authToken = localStorage.getItem(AUTH_STORAGE_KEY) || "";

function buildApiUrl(path) {
    return `${API_BASE}${path}`;
}

function withAuthHeaders(headers = {}) {
    const nextHeaders = { ...headers };
    if (authToken) nextHeaders.Authorization = `Bearer ${authToken}`;
    return nextHeaders;
}

async function fetchJson(path, options = {}) {
    let response;
    try {
        response = await fetch(buildApiUrl(path), {
            ...options,
            headers: withAuthHeaders(options.headers || {}),
        });
    } catch (error) {
        throw new Error("Backend server se connection nahi ho pa raha. Check karo ki app run ho rahi hai.");
    }
    if (response.status === 401 && authToken) {
        await handleLogout(false);
        throw new Error("Session expired. Please login again.");
    }
    if (!response.ok) {
        let detail = `Request failed with status ${response.status}`;
        try {
            const payload = await response.json();
            if (Array.isArray(payload.detail)) {
                detail = payload.detail
                    .map((item) => item.msg || item.message || "Invalid input")
                    .join(", ");
            } else {
                detail = payload.detail || detail;
            }
        } catch (error) {
            // Keep fallback detail.
        }
        throw new Error(detail);
    }
    return response.json();
}

function storeSession(token) {
    authToken = token;
    localStorage.setItem(AUTH_STORAGE_KEY, token);
}

function clearSession() {
    authToken = "";
    localStorage.removeItem(AUTH_STORAGE_KEY);
}
