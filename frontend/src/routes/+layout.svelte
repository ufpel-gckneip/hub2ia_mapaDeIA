<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { apiGet } from '$lib/api.js';
	import { filters, user } from '$lib/stores.js';
	import { loadMe, logout } from '$lib/auth.js';
	import { consentAnswered, setConsent } from '$lib/track.js';

	let topicOptions = [];
	let showConsent = false;

	const nav = [
		{ href: '/', label: '🗺️ Mapa' },
		{ href: '/graph', label: '🕸️ Coautoria' },
		{ href: '/researchers', label: '📋 Pesquisadores' },
		{ href: '/topics', label: '📊 Tópicos' },
		{ href: '/stats', label: '📈 Estatísticas' },
		{ href: '/articles', label: '📄 Artigos' }
	];

	onMount(async () => {
		showConsent = !consentAnswered();
		await loadMe();
		try {
			const data = await apiGet('/topics');
			topicOptions = data.topics.filter((t) => !t.is_noise);
		} catch (e) {
			console.error(e);
		}
	});

	function toggleTopic(id) {
		filters.update((f) => {
			const topics = f.topics.includes(id)
				? f.topics.filter((x) => x !== id)
				: [...f.topics, id];
			return { ...f, topics };
		});
	}

	function answerConsent(granted) {
		setConsent(granted);
		showConsent = false;
	}
</script>

<div class="shell">
	<aside class="sidebar">
		<h1>🧠 Mapa de IA</h1>
		<p class="muted">Pesquisadores brasileiros de IA</p>

		<label>Buscar pesquisador</label>
		<input placeholder="Nome…" bind:value={$filters.search} />

		<label>Mínimo de artigos: {$filters.minArticles}</label>
		<input type="range" min="1" max="20" bind:value={$filters.minArticles} />

		<label>Tópicos</label>
		<div class="topics">
			{#each topicOptions as t}
				<button
					class="chip"
					class:active={$filters.topics.includes(t.topic_id)}
					on:click={() => toggleTopic(t.topic_id)}
					title={`${t.researchers} pesquisadores`}
				>
					{t.topic_name}
				</button>
			{/each}
		</div>

		<div class="account">
			{#if $user}
				<span class="muted">{$user.email}</span>
				<button class="link" on:click={logout}>Sair</button>
			{:else}
				<a href="/login">Entrar / Registrar</a>
			{/if}
		</div>
	</aside>

	<main>
		<nav>
			{#each nav as n}
				<a href={n.href} class:active={$page.url.pathname === n.href}>{n.label}</a>
			{/each}
			{#if $user?.is_superuser}
				<a href="/admin" class:active={$page.url.pathname === '/admin'}>🛠️ Admin</a>
			{/if}
		</nav>
		<div class="content">
			<slot />
		</div>
	</main>
</div>

{#if showConsent}
	<div class="consent">
		<span>
			Usamos cookies de sessão para análise de uso (anônima). Você concorda? (LGPD)
		</span>
		<div>
			<button on:click={() => answerConsent(true)}>Aceitar</button>
			<button class="ghost" on:click={() => answerConsent(false)}>Recusar</button>
		</div>
	</div>
{/if}

<style>
	:global(body) {
		margin: 0;
		font-family: system-ui, sans-serif;
		color: #1a1a1a;
	}
	.shell {
		display: flex;
		height: 100vh;
	}
	.sidebar {
		width: 280px;
		flex-shrink: 0;
		padding: 16px;
		border-right: 1px solid #e5e5e5;
		overflow-y: auto;
		background: #fafafa;
	}
	.sidebar h1 {
		font-size: 20px;
		margin: 0;
	}
	.muted {
		color: #888;
		font-size: 13px;
	}
	label {
		display: block;
		margin: 14px 0 4px;
		font-weight: 600;
		font-size: 13px;
	}
	input[type='text'],
	input:not([type]) {
		width: 100%;
		padding: 6px 8px;
		box-sizing: border-box;
	}
	input[type='range'] {
		width: 100%;
	}
	.topics {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		max-height: 40vh;
		overflow-y: auto;
	}
	.chip {
		border: 1px solid #ccc;
		background: #fff;
		border-radius: 12px;
		padding: 2px 8px;
		font-size: 11px;
		cursor: pointer;
	}
	.chip.active {
		background: #4a90d9;
		color: #fff;
		border-color: #4a90d9;
	}
	.account {
		margin-top: 20px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	main {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	nav {
		display: flex;
		gap: 4px;
		padding: 8px 12px;
		border-bottom: 1px solid #e5e5e5;
		flex-wrap: wrap;
	}
	nav a {
		padding: 6px 12px;
		border-radius: 6px;
		text-decoration: none;
		color: #333;
		font-size: 14px;
	}
	nav a.active {
		background: #4a90d9;
		color: #fff;
	}
	.content {
		flex: 1;
		overflow: auto;
		padding: 16px;
		min-height: 0;
	}
	.link {
		background: none;
		border: none;
		color: #4a90d9;
		cursor: pointer;
		text-align: left;
		padding: 0;
	}
	.consent {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		background: #222;
		color: #fff;
		padding: 12px 16px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		font-size: 14px;
	}
	.consent button {
		margin-left: 8px;
		padding: 6px 14px;
		cursor: pointer;
	}
	.consent .ghost {
		background: transparent;
		color: #fff;
		border: 1px solid #666;
	}
</style>
