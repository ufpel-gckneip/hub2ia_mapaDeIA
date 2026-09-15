// Thin API client. Same-origin in prod (Caddy proxies /api,/auth,/users);
// Vite dev-proxies to the backend. JWT is kept in localStorage.

const TOKEN_KEY = 'mapadeia_token';

export function getToken() {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
	if (token) localStorage.setItem(TOKEN_KEY, token);
	else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra = {}) {
	const t = getToken();
	return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

/** Build a query string, expanding arrays into repeated params. */
export function qs(params) {
	const p = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v == null || v === '' || (Array.isArray(v) && v.length === 0)) continue;
		if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
		else p.append(k, v);
	}
	const s = p.toString();
	return s ? `?${s}` : '';
}

export async function apiGet(path, params = {}) {
	const res = await fetch(`/api${path}${qs(params)}`, { headers: authHeaders() });
	if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
	return res.json();
}

export async function apiSend(method, path, body, { auth = false } = {}) {
	const base = path.startsWith('/auth') || path.startsWith('/users') ? '' : '/api';
	const res = await fetch(`${base}${path}`, {
		method,
		headers: authHeaders({ 'Content-Type': 'application/json' }),
		body: body == null ? undefined : JSON.stringify(body)
	});
	if (!res.ok) throw new Error(`${method} ${path} → ${res.status}`);
	if (res.status === 204) return null;
	return res.json().catch(() => null);
}
