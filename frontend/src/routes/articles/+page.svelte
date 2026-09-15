<script>
	import { onMount } from 'svelte';
	import { apiGet } from '$lib/api.js';
	import { track } from '$lib/track.js';

	let q = '';
	let data = { total: 0, items: [] };
	let detail = null;
	let offset = 0;
	const limit = 50;
	let loading = false;
	let timer;

	async function load(reset = true) {
		loading = true;
		if (reset) offset = 0;
		data = await apiGet('/articles', { q, limit, offset });
		loading = false;
		if (q) track('article_search', { q });
	}

	function onInput() {
		clearTimeout(timer);
		timer = setTimeout(() => load(), 300);
	}

	async function open(id) {
		detail = await apiGet(`/articles/${id}`);
	}

	onMount(() => load());
</script>

<h2>Artigos <span class="muted">({data.total})</span></h2>
<input placeholder="Buscar no título ou resumo…" bind:value={q} on:input={onInput} />

{#if loading}
	<p class="muted">carregando…</p>
{:else}
	<table>
		<thead><tr><th>Título</th><th>Evento</th><th>Ano</th><th>Track</th></tr></thead>
		<tbody>
			{#each data.items as a}
				<tr on:click={() => open(a.article_id)} class="clickable">
					<td>{a.title}</td><td>{a.event}</td><td>{a.year}</td><td>{a.track ?? '—'}</td>
				</tr>
			{/each}
		</tbody>
	</table>
	<div class="pager">
		<button disabled={offset === 0} on:click={() => { offset -= limit; load(false); }}>‹</button>
		<span class="muted">{offset + 1}–{Math.min(offset + limit, data.total)}</span>
		<button disabled={offset + limit >= data.total} on:click={() => { offset += limit; load(false); }}>›</button>
	</div>
{/if}

{#if detail}
	<div class="drawer">
		<button class="close" on:click={() => (detail = null)}>✕</button>
		<h3>{detail.title}</h3>
		<p class="muted">{detail.event_name} ({detail.event}) · {detail.year} · {detail.track ?? '—'}</p>
		<p><strong>Autores:</strong> {detail.authors.map((a) => a.display_name).join('; ')}</p>
		{#if detail.abstract}<p>{detail.abstract}</p>{/if}
		{#if detail.pdf_url}<a href={detail.pdf_url} target="_blank" rel="noreferrer">📄 PDF</a>{/if}
		{#if detail.article_url}<a href={detail.article_url} target="_blank" rel="noreferrer">🔗 SOL</a>{/if}
	</div>
{/if}

<style>
	.muted { color: #888; font-size: 13px; font-weight: normal; }
	input { width: 100%; max-width: 500px; padding: 8px; margin-bottom: 12px; box-sizing: border-box; }
	table { width: 100%; border-collapse: collapse; font-size: 14px; }
	th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; }
	.clickable { cursor: pointer; }
	.clickable:hover { background: #f5f7fa; }
	.pager { display: flex; gap: 12px; align-items: center; margin-top: 12px; }
	.drawer {
		position: fixed; top: 0; right: 0; width: min(520px, 92vw); height: 100vh;
		background: #fff; box-shadow: -4px 0 20px rgba(0,0,0,0.15); padding: 20px; overflow-y: auto; z-index: 50;
	}
	.drawer a { margin-right: 12px; }
	.close { position: absolute; top: 12px; right: 12px; border: none; background: none; font-size: 18px; cursor: pointer; }
</style>
