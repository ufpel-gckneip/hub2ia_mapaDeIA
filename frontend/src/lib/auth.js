import { apiSend, clearTokens, getToken, setTokens } from './api.js';
import { user } from './stores.js';

export async function login(email, password) {
	// Login expects form-urlencoded (OAuth2 password flow); returns an
	// access + refresh token pair.
	const body = new URLSearchParams({ username: email, password });
	const res = await fetch('/auth/jwt/login', {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body
	});
	if (!res.ok) throw new Error('Credenciais inválidas');
	const data = await res.json();
	setTokens(data);
	await loadMe();
}

export async function register(email, password, extra = {}) {
	await apiSend('POST', '/auth/register', { email, password, ...extra });
	return login(email, password);
}

export async function loadMe() {
	if (!getToken()) {
		user.set(null);
		return null;
	}
	try {
		const me = await apiSend('GET', '/users/me');
		user.set(me);
		return me;
	} catch {
		clearTokens();
		user.set(null);
		return null;
	}
}

export function logout() {
	clearTokens();
	user.set(null);
}
