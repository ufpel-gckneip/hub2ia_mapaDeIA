<script>
	import { onMount } from 'svelte';
	import { apiGet } from '$lib/api.js';

	let topics = [];
	let max = 1;

	onMount(async () => {
		const data = await apiGet('/topics');
		topics = data.topics.filter((t) => !t.is_noise);
		max = Math.max(1, ...topics.map((t) => t.researchers));
	});
</script>

<h2>Distribuição por Tópico</h2>
<div class="list">
	{#each topics as t}
		<div class="row">
			<div class="name" title={t.topic_keywords?.join(', ')}>{t.topic_name}</div>
			<div class="bar"><div class="fill" style="width: {(t.researchers / max) * 100}%"></div></div>
			<div class="n">{t.researchers}</div>
		</div>
	{/each}
</div>

<style>
	.list { display: flex; flex-direction: column; gap: 4px; max-width: 800px; }
	.row { display: grid; grid-template-columns: 220px 1fr 50px; align-items: center; gap: 8px; font-size: 13px; }
	.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.bar { background: #eee; border-radius: 4px; height: 16px; }
	.fill { background: #4a90d9; height: 100%; border-radius: 4px; }
	.n { text-align: right; color: #555; }
</style>
