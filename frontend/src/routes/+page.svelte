<script>
	import { onMount, onDestroy } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { MapboxOverlay } from '@deck.gl/mapbox';
	import { ScatterplotLayer, ArcLayer, LineLayer } from '@deck.gl/layers';
	import { apiGet, apiSend } from '$lib/api.js';
	import { filters, user } from '$lib/stores.js';
	import { track } from '$lib/track.js';
	import { topicColor } from '$lib/palette.js';

	let mapEl;
	let map;
	let overlay;
	let mapReady = false;

	let viewMode = 'institutions'; // 'institutions' | 'authors'
	let institutions = [];
	let selected = null; // {name, lng, lat, city, state}
	let rawAuthors = []; // authors of `selected`, unpositioned
	let authorPoints = []; // positioned copy (pixel spiral around the hub)
	let stateAgg = [];
	let arcs = [];
	let loading = true;
	let detail = null; // researcher detail drawer

	// Arc controls
	let showArcs = true;
	let arcLevel = 'state';
	let arcMinWeight = 1;
	const ARC_LIMIT = { state: 150, institution: 300, author: 500 };

	const STYLE = 'https://tiles.openfreemap.org/styles/positron';

	async function loadInstitutions(f) {
		loading = true;
		const [inst, agg] = await Promise.all([
			apiGet('/map/institutions', { topic_id: f.topics, min_articles: f.minArticles, q: f.search }),
			apiGet('/map/state-aggregates')
		]);
		institutions = inst.institutions;
		stateAgg = agg.states;
		loading = false;
		updateLayers();
		updateChoropleth();
		track('map_view', { institutions: institutions.length });
	}

	// Fan co-located authors out in a phyllotaxis spiral at a FIXED PIXEL distance
	// from the hub, using screen projection so the spread never blends when you
	// zoom out. Recomputed on every map move/zoom.
	const SPIDER_STEP_PX = 34; // base spacing between neighbours in pixels
	function positionAuthors() {
		if (!map || !selected || !rawAuthors.length) {
			authorPoints = [];
			return;
		}
		const hub = map.project([selected.lng, selected.lat]);
		const golden = 2.399963229;
		authorPoints = rawAuthors.map((a, i) => {
			if (rawAuthors.length === 1) return { ...a, lng: selected.lng, lat: selected.lat };
			const r = SPIDER_STEP_PX * Math.sqrt(i + 1);
			const ang = i * golden;
			const ll = map.unproject([hub.x + r * Math.cos(ang), hub.y + r * Math.sin(ang)]);
			return { ...a, lng: ll.lng, lat: ll.lat };
		});
	}

	async function drillInto(inst, f) {
		selected = inst;
		viewMode = 'authors';
		map.flyTo({ center: [inst.lng, inst.lat], zoom: 11, duration: 800 });
		const data = await apiGet('/map/institution-authors', {
			name: inst.name,
			topic_id: f.topics,
			min_articles: f.minArticles,
			q: f.search
		});
		rawAuthors = data.authors;
		positionAuthors();
		updateLayers();
		track('map_drilldown', { institution: inst.name, authors: rawAuthors.length });
	}

	function backToOverview() {
		viewMode = 'institutions';
		selected = null;
		rawAuthors = [];
		authorPoints = [];
		map.flyTo({ center: [-51.9, -14.2], zoom: 3.4, duration: 800 });
		updateLayers();
	}

	async function openDetail(id) {
		detail = await apiGet(`/researchers/${id}`);
		track('researcher_view', { id });
	}

	async function favorite(id) {
		await apiSend('POST', '/me/favorites', { entity_type: 'researcher', entity_id: id });
	}

	async function loadArcs(level, minWeight) {
		const data = await apiGet('/map/arcs', {
			level,
			min_weight: minWeight,
			limit: ARC_LIMIT[level] ?? 200
		});
		arcs = data.arcs;
		updateLayers();
	}

	function updateLayers() {
		if (!overlay) return;
		const layers = [];

		if (showArcs && arcs.length) {
			const maxW = Math.max(1, ...arcs.map((a) => a.weight));
			layers.push(
				new ArcLayer({
					id: 'coauthorship-arcs',
					data: arcs,
					getSourcePosition: (d) => [d.x1, d.y1],
					getTargetPosition: (d) => [d.x2, d.y2],
					getSourceColor: [231, 76, 60, 110],
					getTargetColor: [142, 68, 173, 110],
					getWidth: (d) => 1 + (d.weight / maxW) * 7,
					pickable: true
				})
			);
		}

		// University markers are ALWAYS shown (so other universities stay visible
		// while drilled in) and always clickable to switch focus.
		const maxN = Math.max(1, ...institutions.map((i) => i.n_researchers));
		layers.push(
			new ScatterplotLayer({
				id: 'institutions',
				data: institutions,
				getPosition: (d) => [d.lng, d.lat],
				getRadius: (d) => 4000 + Math.sqrt(d.n_researchers / maxN) * 45000,
				radiusMinPixels: 5,
				radiusMaxPixels: 48,
				getFillColor: (d) =>
					selected && d.name === selected.name ? [200, 60, 40, 230] : [70, 130, 180, 200],
				stroked: true,
				getLineColor: [255, 255, 255, 220],
				lineWidthMinPixels: 1,
				pickable: true,
				onClick: (info) => info.object && drillInto(info.object, $filters)
			})
		);

		if (viewMode === 'authors' && selected) {
			// Spider legs: author → university hub (drawn under the author dots).
			layers.push(
				new LineLayer({
					id: 'spider-legs',
					data: authorPoints,
					getSourcePosition: (d) => [d.lng, d.lat],
					getTargetPosition: () => [selected.lng, selected.lat],
					getColor: [120, 120, 120, 130],
					getWidth: 1
				})
			);
			layers.push(
				new ScatterplotLayer({
					id: 'authors',
					data: authorPoints,
					getPosition: (d) => [d.lng, d.lat],
					// Fixed pixel size (matches the fixed-pixel spiral spacing).
					radiusUnits: 'pixels',
					getRadius: (d) => 9 + Math.min(d.n_articles, 20) * 0.6,
					getFillColor: (d) => [...topicColor(d.topic_id), 235],
					stroked: true,
					getLineColor: [255, 255, 255, 230],
					lineWidthMinPixels: 1.5,
					pickable: true,
					onClick: (info) => info.object && openDetail(info.object.researcher_id)
				})
			);
		}

		overlay.setProps({
			layers,
			getTooltip: ({ object }) => {
				if (!object) return null;
				if (object.display_name)
					return {
						text: `${object.display_name}\n${object.n_articles} artigos\n(clique para detalhes)`
					};
				if (object.n_researchers != null)
					return {
						text: `${object.name}\n${object.n_researchers} pesquisadores · ${object.n_articles} artigos\n(clique para expandir)`
					};
				if (object.label1)
					return { text: `${object.label1} ↔ ${object.label2}\n${object.weight} coautorias` };
				return null;
			}
		});
	}

	async function updateChoropleth() {
		if (!map || !map.isStyleLoaded()) return;
		let geo;
		try {
			const res = await fetch('/brazil_states.geojson');
			if (!res.ok) return;
			geo = await res.json();
		} catch {
			return;
		}
		const byState = Object.fromEntries(stateAgg.map((s) => [s.state, s]));
		let maxCount = 1;
		for (const feat of geo.features) {
			const c = byState[feat.properties.sigla]?.researchers ?? 0;
			feat.properties.count = c;
			if (c > maxCount) maxCount = c;
		}
		if (map.getSource('states')) {
			map.getSource('states').setData(geo);
		} else {
			map.addSource('states', { type: 'geojson', data: geo });
			map.addLayer({
				id: 'states-fill',
				type: 'fill',
				source: 'states',
				paint: {
					'fill-color': [
						'interpolate',
						['linear'],
						['get', 'count'],
						0,
						'#f0f0f0',
						maxCount,
						'#08519c'
					],
					'fill-opacity': 0.4,
					'fill-outline-color': '#888'
				}
			});
		}
	}

	onMount(() => {
		map = new maplibregl.Map({ container: mapEl, style: STYLE, center: [-51.9, -14.2], zoom: 3.4 });
		overlay = new MapboxOverlay({
			interleaved: false,
			layers: [],
			// Clicking empty map (no marker picked) collapses the expanded view,
			// same as "Voltar". Marker clicks set info.object, so they're unaffected.
			onClick: (info) => {
				if (!info.object && viewMode === 'authors') backToOverview();
			}
		});
		map.addControl(overlay);
		map.on('load', () => (mapReady = true));

		// Keep the author spiral at a fixed screen distance as the view changes.
		let scheduled = false;
		map.on('move', () => {
			if (viewMode !== 'authors' || !selected || scheduled) return;
			scheduled = true;
			requestAnimationFrame(() => {
				scheduled = false;
				positionAuthors();
				updateLayers();
			});
		});
	});

	onDestroy(() => map && map.remove());

	$: if (mapReady) refresh($filters);
	async function refresh(f) {
		await loadInstitutions(f);
		if (selected) await drillInto(selected, f);
	}
	$: if (mapReady) loadArcs(arcLevel, arcMinWeight);
	$: if (mapReady) (showArcs, updateLayers());
</script>

<div class="wrap">
	<div class="bar">
		<strong>Mapa Demográfico</strong>
		<div class="controls">
			<label class="ctl"><input type="checkbox" bind:checked={showArcs} /> Coautoria entre</label>
			<select bind:value={arcLevel} disabled={!showArcs}>
				<option value="state">estados</option>
				<option value="institution">universidades</option>
				<option value="author">autores</option>
			</select>
			<label class="ctl" title="Força mínima da interação">
				força ≥ {arcMinWeight}
				<input type="range" min="1" max="20" bind:value={arcMinWeight} disabled={!showArcs} />
			</label>
		</div>
	</div>

	<div class="statusline">
		{#if viewMode === 'authors' && selected}
			<button class="back" on:click={backToOverview}>← Voltar</button>
			<span
				><strong>{selected.name}</strong> — {authorPoints.length} autores · {selected.city ?? ''}
				{selected.state ?? ''}</span
			>
		{:else}
			<span class="muted">
				{loading ? 'carregando…' : `${institutions.length} universidades`} • tamanho = nº de pesquisadores
				• clique para expandir os autores
			</span>
		{/if}
	</div>

	<div class="map" bind:this={mapEl}></div>
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
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}
	.controls {
		display: flex;
		align-items: center;
		gap: 12px;
		font-size: 13px;
	}
	.ctl {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.controls select {
		padding: 3px 6px;
	}
	.controls input[type='range'] {
		width: 90px;
	}
	.statusline {
		padding: 4px 0 8px;
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 13px;
	}
	.muted {
		color: #888;
	}
	.back {
		border: 1px solid #4a90d9;
		color: #4a90d9;
		background: #fff;
		border-radius: 6px;
		padding: 3px 10px;
		cursor: pointer;
	}
	.map {
		flex: 1;
		min-height: 400px;
		border-radius: 8px;
		overflow: hidden;
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
</style>
