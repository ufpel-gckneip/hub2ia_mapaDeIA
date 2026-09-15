<script>
	import { onMount, onDestroy } from 'svelte';
	import Graph from 'graphology';
	import Sigma from 'sigma';
	import { apiGet } from '$lib/api.js';
	import { track } from '$lib/track.js';
	import { topicColor, rgbCss } from '$lib/palette.js';

	let containerEl;
	let renderer;
	let minDegree = 3;
	let loading = true;
	let stats = { nodes: 0, edges: 0 };

	async function render() {
		loading = true;
		const data = await apiGet('/graph', { min_degree: minDegree });
		const g = new Graph({ multi: false, type: 'undirected' });

		for (const n of data.nodes) {
			g.addNode(String(n.id), {
				x: n.x ?? Math.random(),
				y: n.y ?? Math.random(),
				size: Math.max(2, Math.min(Math.sqrt(n.degree) * 1.5, 20)),
				label: n.label,
				color: rgbCss(topicColor(n.topic_id))
			});
		}
		for (const e of data.edges) {
			const s = String(e.source);
			const t = String(e.target);
			if (s === t || !g.hasNode(s) || !g.hasNode(t) || g.hasEdge(s, t)) continue;
			g.addEdge(s, t, { weight: e.weight, size: Math.min(0.2 + e.weight * 0.15, 3) });
		}

		stats = { nodes: g.order, edges: g.size };
		if (renderer) renderer.kill();
		renderer = new Sigma(g, containerEl, {
			renderLabels: false,
			labelRenderedSizeThreshold: 12,
			defaultEdgeColor: '#ddd'
		});
		renderer.on('clickNode', ({ node }) => track('graph_node_click', { id: node }));
		loading = false;
		track('graph_view', { min_degree: minDegree, ...stats });
	}

	onMount(render);
	onDestroy(() => renderer && renderer.kill());
</script>

<div class="wrap">
	<div class="bar">
		<strong>Mapa de Coautoria</strong>
		<label>
			Grau mínimo: {minDegree}
			<input type="range" min="1" max="30" bind:value={minDegree} on:change={render} />
		</label>
		<span class="muted">
			{loading ? 'carregando…' : `${stats.nodes} nós · ${stats.edges} arestas`}
		</span>
	</div>
	<div class="graph" bind:this={containerEl}></div>
</div>

<style>
	.wrap {
		height: 100%;
		display: flex;
		flex-direction: column;
	}
	.bar {
		display: flex;
		gap: 20px;
		align-items: center;
		padding-bottom: 8px;
	}
	label {
		font-size: 13px;
		display: flex;
		gap: 8px;
		align-items: center;
	}
	.muted {
		color: #888;
		font-size: 13px;
		margin-left: auto;
	}
	.graph {
		flex: 1;
		min-height: 400px;
		border: 1px solid #e5e5e5;
		border-radius: 8px;
	}
</style>
