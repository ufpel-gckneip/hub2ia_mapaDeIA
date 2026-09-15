// ESLint 9 "flat config" for the SvelteKit SPA.
//   npm run lint   → eslint .
// Layers, in order:
//   1. eslint recommended JS rules
//   2. eslint-plugin-svelte recommended rules (parses .svelte files)
//   3. eslint-config-prettier + svelte's prettier preset — turn OFF formatting
//      rules so Prettier owns formatting and the two never fight.
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default [
	js.configs.recommended,
	...svelte.configs['flat/recommended'],
	prettier,
	...svelte.configs['flat/prettier'],
	{
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			// Browser code + a little Node (config files).
			globals: { ...globals.browser, ...globals.node }
		},
		rules: {
			// Svelte compiler diagnostics (a11y hints, unused-CSS) are surfaced as
			// warnings, not lint-blocking errors. The dedicated accessibility pass
			// (TODO #13) resolves them; true compile *errors* still fail the build.
			'svelte/valid-compile': 'warn'
		}
	},
	{
		// Generated / vendored output — never lint these.
		ignores: ['build/', '.svelte-kit/', 'dist/', 'node_modules/', 'static/']
	}
];
