<script>
	import { onMount } from 'svelte';
	import { apiGet } from '$lib/api.js';

	let s = null;
	onMount(async () => (s = await apiGet('/stats')));

	function bars(rows, key) {
		const max = Math.max(1, ...rows.map((r) => r.n));
		return rows.map((r) => ({ label: r[key], n: r.n, pct: (r.n / max) * 100 }));
	}
</script>

<h2>Estatísticas Gerais</h2>
{#if s}
	<div class="kpis">
		<div class="kpi"><b>{s.totals.researchers.toLocaleString()}</b><span>Pesquisadores</span></div>
		<div class="kpi"><b>{s.totals.articles.toLocaleString()}</b><span>Artigos</span></div>
		<div class="kpi"><b>{s.totals.events}</b><span>Eventos</span></div>
		<div class="kpi"><b>{s.totals.topics}</b><span>Tópicos</span></div>
	</div>

	<div class="cols">
		<div>
			<h3>Artigos por Ano</h3>
			{#each bars(s.by_year, 'year') as b}
				<div class="row">
					<span>{b.label}</span>
					<div class="bar"><div style="width:{b.pct}%"></div></div>
					<em>{b.n}</em>
				</div>
			{/each}
		</div>
		<div>
			<h3>Artigos por Evento</h3>
			{#each bars(s.by_event, 'event') as b}
				<div class="row">
					<span>{b.label}</span>
					<div class="bar"><div style="width:{b.pct}%"></div></div>
					<em>{b.n}</em>
				</div>
			{/each}
		</div>
	</div>
{:else}
	<p class="muted">carregando…</p>
{/if}

<style>
	.kpis {
		display: flex;
		gap: 16px;
		margin-bottom: 24px;
	}
	.kpi {
		background: #f5f7fa;
		border-radius: 8px;
		padding: 16px 24px;
		text-align: center;
	}
	.kpi b {
		font-size: 26px;
		display: block;
	}
	.kpi span {
		color: #888;
		font-size: 13px;
	}
	.cols {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 32px;
		max-width: 900px;
	}
	.row {
		display: grid;
		grid-template-columns: 60px 1fr 40px;
		gap: 8px;
		align-items: center;
		font-size: 12px;
		margin: 2px 0;
	}
	.bar {
		background: #eee;
		height: 14px;
		border-radius: 3px;
	}
	.bar div {
		background: #f5793b;
		height: 100%;
		border-radius: 3px;
	}
	em {
		text-align: right;
		color: #555;
		font-style: normal;
	}
	.muted {
		color: #888;
	}
</style>
