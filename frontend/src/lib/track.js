// Privacy-first analytics client. No events are sent until the user consents
// (LGPD). Session id is a random first-party value in localStorage.
import { getToken } from './api.js';

const CONSENT_KEY = 'mapadeia_consent';
const SESSION_KEY = 'mapadeia_session';

export function hasConsent() {
	return typeof localStorage !== 'undefined' && localStorage.getItem(CONSENT_KEY) === '1';
}

export function setConsent(granted) {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(CONSENT_KEY, granted ? '1' : '0');
}

export function consentAnswered() {
	return typeof localStorage !== 'undefined' && localStorage.getItem(CONSENT_KEY) !== null;
}

function sessionId() {
	let s = localStorage.getItem(SESSION_KEY);
	if (!s) {
		s = crypto.randomUUID();
		localStorage.setItem(SESSION_KEY, s);
	}
	return s;
}

export function track(eventType, payload = {}) {
	if (!hasConsent()) return;
	const headers = { 'Content-Type': 'application/json' };
	const t = getToken();
	if (t) headers.Authorization = `Bearer ${t}`;
	// Fire-and-forget; never block the UI or surface errors.
	fetch('/api/events', {
		method: 'POST',
		headers,
		body: JSON.stringify({ session_id: sessionId(), event_type: eventType, payload })
	}).catch(() => {});
}
