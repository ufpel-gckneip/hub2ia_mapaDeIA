// Thin API client. Same-origin in prod (Caddy proxies /api,/auth,/users);
// Vite dev-proxies to the backend. Tokens are kept in localStorage: a short-lived
// access token (sent as Bearer) and a longer-lived refresh token. On a 401 we
// transparently refresh the access token once and retry (see authedFetch).

const TOKEN_KEY = 'mapadeia_token';
const REFRESH_KEY = 'mapadeia_refresh';

export function getToken() {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
	if (token) localStorage.setItem(TOKEN_KEY, token);
	else localStorage.removeItem(TOKEN_KEY);
}

export function getRefreshToken() {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token) {
	if (token) localStorage.setItem(REFRESH_KEY, token);
	else localStorage.removeItem(REFRESH_KEY);
}

/** Store both tokens from a login response ({access_token, refresh_token}). */
export function setTokens({ access_token, refresh_token }) {
	setToken(access_token);
	setRefreshToken(refresh_token);
}

/** Clear all auth tokens. */
export function clearTokens() {
	setToken(null);
	setRefreshToken(null);
}

function authHeaders(extra = {}) {
	const t = getToken();
	return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

// De-duplicate concurrent refreshes: many requests may 401 at once, but only one
// network refresh should run; the rest await the same promise.
let refreshInFlight = null;

async function refreshAccessToken() {
	const rt = getRefreshToken();
	if (!rt) return false;
	if (!refreshInFlight) {
		refreshInFlight = fetch('/auth/jwt/refresh', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ refresh_token: rt })
		})
			.then(async (res) => {
				if (!res.ok) {
					clearTokens();
					return false;
				}
				const data = await res.json();
				setToken(data.access_token);
				return true;
			})
			.catch(() => false)
			.finally(() => {
				refreshInFlight = null;
			});
	}
	return refreshInFlight;
}

/** fetch that retries once after refreshing the access token on a 401. */
async function authedFetch(url, opts = {}) {
	const headers = authHeaders(opts.headers ?? {});
	let res = await fetch(url, { ...opts, headers });
	if (res.status === 401 && (await refreshAccessToken())) {
		res = await fetch(url, { ...opts, headers: authHeaders(opts.headers ?? {}) });
	}
	return res;
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
	const res = await authedFetch(`/api${path}${qs(params)}`);
	if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
	return res.json();
}

export async function apiSend(method, path, body) {
	const base = path.startsWith('/auth') || path.startsWith('/users') ? '' : '/api';
	const res = await authedFetch(`${base}${path}`, {
		method,
		headers: { 'Content-Type': 'application/json' },
		body: body == null ? undefined : JSON.stringify(body)
	});
	if (!res.ok) throw new Error(`${method} ${path} → ${res.status}`);
	if (res.status === 204) return null;
	return res.json().catch(() => null);
}
