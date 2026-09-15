import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// Dev: proxy API calls to the local backend so the SPA is same-origin.
		proxy: {
			'/api': 'http://localhost:8000',
			'/auth': 'http://localhost:8000',
			'/users': 'http://localhost:8000'
		}
	}
});
