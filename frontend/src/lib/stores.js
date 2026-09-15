import { writable } from 'svelte/store';

// Global sidebar filters shared across views (mirrors the Streamlit sidebar).
export const filters = writable({
	topics: [], // topic_id[]
	minArticles: 1,
	search: ''
});

// Current user (null when logged out).
export const user = writable(null);
