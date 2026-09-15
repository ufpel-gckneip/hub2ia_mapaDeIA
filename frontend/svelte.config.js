import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// SPA mode: prerender the shell, fall back to index.html for client routing.
		adapter: adapter({ fallback: 'index.html' }),
		prerender: { entries: [] }
	}
};

export default config;
