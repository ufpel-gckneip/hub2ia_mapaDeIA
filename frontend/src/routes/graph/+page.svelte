<script>
	import { onMount, onDestroy } from 'svelte';
	import Graph from 'graphology';
	import Sigma from 'sigma';
	import { apiGet, apiSend } from '$lib/api.js';
	import { user, filters } from '$lib/stores.js';
	import { track } from '$lib/track.js';
	import { topicColor, rgbCss } from '$lib/palette.js';

	let containerEl;
	let renderer;
	let g; // graphology graph (component scope, so reducers/search can reach it)
	// Default ≥ 3 keeps the initial payload bounded: the backend thins nodes AND
	// edges in SQL by min_degree (see routers/graph.py), so a lower default would
	// ship most of the ~8.9k-node / ~23k-edge graph on first load.
	let minDegree = 3;
	let loading = true;
	let renderToken = 0; // guards against overlapping/stale slider-triggered renders
	let sliderTimer; // debounce for the min-degree slider
	let stats = { nodes: 0, edges: 0 };
	let detail = null;
	let searchCount = 0;

	// Focus model (shared by hover + sidebar search): `core` = primary nodes,
	// `set` = core plus their neighbors (kept visible). Null = no focus.
	let focusCore = null;
	let focusSet = null;
	let hovering = false;
	let searchCore = new Set();

	function setFocus(core) {
		if (!core || core.size === 0) {
			focusCore = null;
			focusSet = null;
		} else {
			focusCore = core;
			const set = new Set(core);
			for (const n of core) if (g?.hasNode(n)) for (const nb of g.neighbors(n)) set.add(nb);
			focusSet = set;
		}
		renderer?.refresh();
	}

	// Debounce slider moves: rebuild once the user settles, not on every tick,
	// so dragging across values doesn't fire a burst of fetches/rebuilds.
	function scheduleRender() {
		clearTimeout(sliderTimer);
		sliderTimer = setTimeout(render, 200);
	}

	async function render() {
		const token = ++renderToken;
		loading = true;
		// Yield a frame so the "carregando…" state actually paints before the
		// synchronous graphology build + Sigma init below — otherwise a slider
		// change looks like a frozen UI while the main thread is busy.
		await new Promise((r) => requestAnimationFrame(r));

		const data = await apiGet('/graph', { min_degree: minDegree });
		// A newer slider change superseded this request: drop the stale response
		// instead of clobbering the fresh graph (and doing the build work twice).
		if (token !== renderToken) return;

		// Build into a local graph and adopt it only once complete, so a
		// half-built graph is never briefly live for the reducers/search.
		const graph = new Graph({ multi: false, type: 'undirected' });
		for (const n of data.nodes) {
			graph.addNode(String(n.id), {
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
			if (s === t || !graph.hasNode(s) || !graph.hasNode(t) || graph.hasEdge(s, t)) continue;
			graph.addEdge(s, t, { weight: e.weight, size: Math.min(0.6 + e.weight * 0.25, 5) });
		}

		g = graph;
		stats = { nodes: g.order, edges: g.size };
		if (renderer) renderer.kill();

		renderer = new Sigma(g, containerEl, {
			renderLabels: true,
			labelRenderedSizeThreshold: 100, // effectively off unless forced (hover/search)
			defaultEdgeColor: '#5b6b7f',
			minEdgeThickness: 1,
			// Fade everything outside the current focus set; label the core nodes.
			nodeReducer: (node, dataN) => {
				if (!focusSet) return dataN;
				if (focusSet.has(node)) return focusCore.has(node) ? { ...dataN, forceLabel: true } : dataN;
				return { ...dataN, color: '#e8e8e8', label: '' };
			},
			// Show only edges incident to a core node, emphasized.
			edgeReducer: (edge, dataE) => {
				if (!focusCore) return dataE;
				const [s, t] = g.extremities(edge);
				return focusCore.has(s) || focusCore.has(t)
					? { ...dataE, color: '#2c3e50' }
					: { ...dataE, hidden: true };
			}
		});

		renderer.on('enterNode', ({ node }) => {
			hovering = true;
			containerEl.style.cursor = 'pointer';
			setFocus(new Set([node]));
		});
		renderer.on('leaveNode', () => {
			hovering = false;
			containerEl.style.cursor = 'default';
			setFocus(searchCore); // revert to the sidebar-search highlight (if any)
		});
		renderer.on('clickNode', ({ node }) => openDetail(parseInt(node, 10)));

		applySearch($filters.search); // reapply search highlight to the rebuilt graph
		loading = false;
		track('graph_view', { min_degree: minDegree, ...stats });
	}

	// Highlight nodes whose label matches the sidebar "Buscar pesquisador" text.
	function applySearch(term) {
		if (!g || !renderer) return;
		const q = (term || '').trim().toLowerCase();
		if (!q) {
			searchCore = new Set();
			searchCount = 0;
			if (!hovering) setFocus(null);
			return;
		}
		const matches = new Set();
		g.forEachNode((node, attr) => {
			if ((attr.label || '').toLowerCase().includes(q)) matches.add(node);
		});
		searchCore = matches;
		searchCount = matches.size;
		if (!hovering) setFocus(matches);
	}

	// React to the shared sidebar search box.
	$: applySearch($filters.search);

	async function openDetail(id) {
		detail = await apiGet(`/researchers/${id}`);
		track('researcher_view', { id, from: 'graph' });
	}

	async function favorite(id) {
		await apiSend('POST', '/me/favorites', { entity_type: 'researcher', entity_id: id });
	}

	onMount(render);
	onDestroy(() => {
		clearTimeout(sliderTimer);
		renderToken++; // invalidate any in-flight render
		if (renderer) renderer.kill();
	});
</script>

<div class="wrap">
	<div class="bar">
		<strong>Mapa de Coautoria</strong>
		<label>
			Grau mínimo: {minDegree}
			<input type="range" min="1" max="30" bind:value={minDegree} on:input={scheduleRender} />
		</label>
		<span class="muted">
			{#if loading}carregando…{:else}
				{stats.nodes} nós · {stats.edges} arestas
				{#if $filters.search}· <strong>{searchCount}</strong> para “{$filters.search}”{:else}·
					clique num nó para detalhes{/if}
			{/if}
		</span>
	</div>
	<div class="graph" bind:this={containerEl}></div>
</div>

{#if detail}
	<div class="drawer">
		<button class="close" on:click={() => (detail = null)}>✕</button>
		<h3>{detail.display_name}</h3>
		<p class="muted">
			{detail.n_articles} artigos · {detail.first_year}–{detail.last_year} · {detail.topic_name}
		</p>
		{#if $user}
			<button class="fav" on:click={() => favorite(detail.researcher_id)}>☆ Favoritar</button>
		{/if}
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
		background: #fff;
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
		z-index: 1000;
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
	.fav {
		border: 1px solid #ccc;
		background: #fff;
		border-radius: 4px;
		padding: 3px 10px;
		cursor: pointer;
		margin-bottom: 8px;
	}
	.drawer .muted {
		margin-left: 0;
	}
</style>
