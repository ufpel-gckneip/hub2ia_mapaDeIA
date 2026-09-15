<script>
	import { apiGet } from '$lib/api.js';
	import { filters, user } from '$lib/stores.js';
	import { apiSend } from '$lib/api.js';
	import { track } from '$lib/track.js';

	let data = { total: 0, items: [] };
	let offset = 0;
	const limit = 50;
	let detail = null;
	let loading = false;

	async function load(reset = true) {
		loading = true;
		if (reset) offset = 0;
		const f = $filters;
		data = await apiGet('/researchers', {
			topic_id: f.topics,
			min_articles: f.minArticles,
			q: f.search,
			limit,
			offset
		});
		loading = false;
	}

	async function openDetail(id) {
		detail = await apiGet(`/researchers/${id}`);
		track('researcher_view', { id });
	}

	async function favorite(id) {
		await apiSend('POST', '/me/favorites', { entity_type: 'researcher', entity_id: id });
	}

	// Reload when filters change.
	$: ($filters, load());
</script>

<h2>Pesquisadores <span class="muted">({data.total})</span></h2>

{#if loading}
	<p class="muted">carregando…</p>
{:else}
	<table>
		<thead>
			<tr><th>Nome</th><th>Artigos</th><th>Período</th><th>Tópico</th><th>UF</th><th></th></tr>
		</thead>
		<tbody>
			{#each data.items as r}
				<tr>
					<td
						><button class="link" on:click={() => openDetail(r.researcher_id)}
							>{r.display_name}</button
						></td
					>
					<td>{r.n_articles}</td>
					<td>{r.first_year}–{r.last_year}</td>
					<td>{r.topic_name}</td>
					<td>{r.state ?? '—'}</td>
					<td>
						{#if $user}
							<button class="link" title="Favoritar" on:click={() => favorite(r.researcher_id)}
								>☆</button
							>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>

	<div class="pager">
		<button
			disabled={offset === 0}
			on:click={() => {
				offset -= limit;
				load(false);
			}}>‹ Anterior</button
		>
		<span class="muted">{offset + 1}–{Math.min(offset + limit, data.total)}</span>
		<button
			disabled={offset + limit >= data.total}
			on:click={() => {
				offset += limit;
				load(false);
			}}>Próximo ›</button
		>
	</div>
{/if}

{#if detail}
	<div class="drawer">
		<button class="close" on:click={() => (detail = null)}>✕</button>
		<h3>{detail.display_name}</h3>
		<p class="muted">
			{detail.n_articles} artigos · {detail.first_year}–{detail.last_year} · {detail.topic_name}
		</p>
		{#if detail.institutions?.length}
			<p><strong>Instituições:</strong> {detail.institutions.map((i) => i.full_name).join('; ')}</p>
		{/if}
		<h4>Artigos</h4>
		<ul>
			{#each detail.articles as a}
				<li>{a.year} · {a.event} · {a.title}</li>
			{/each}
		</ul>
	</div>
{/if}

<style>
	.muted {
		color: #888;
		font-weight: normal;
		font-size: 13px;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 14px;
	}
	th,
	td {
		text-align: left;
		padding: 6px 8px;
		border-bottom: 1px solid #eee;
	}
	.link {
		background: none;
		border: none;
		color: #4a90d9;
		cursor: pointer;
		padding: 0;
		text-align: left;
	}
	.pager {
		display: flex;
		gap: 12px;
		align-items: center;
		margin-top: 12px;
	}
	.drawer {
		position: fixed;
		top: 0;
		right: 0;
		width: min(480px, 90vw);
		height: 100vh;
		background: #fff;
		box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
		padding: 20px;
		overflow-y: auto;
		z-index: 50;
	}
	.close {
		position: absolute;
		top: 12px;
		right: 12px;
		border: none;
		background: none;
		font-size: 18px;
		cursor: pointer;
	}
</style>
