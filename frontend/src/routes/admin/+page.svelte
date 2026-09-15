<script>
	import { onMount } from 'svelte';
	import { apiGet, apiSend } from '$lib/api.js';
	import { user } from '$lib/stores.js';

	let overview = null;
	let events = [];
	let users = [];
	let eventFilter = '';
	let error = '';
	let tab = 'overview';

	async function loadAll() {
		error = '';
		try {
			overview = await apiGet('/admin/overview');
			await loadEvents();
			const u = await apiGet('/admin/users');
			users = u.users;
		} catch (e) {
			error = 'Acesso negado (é necessário ser superusuário) ou API indisponível.';
		}
	}

	async function loadEvents() {
		const data = await apiGet('/admin/events', { event_type: eventFilter || undefined, limit: 100 });
		events = data.events;
	}

	async function toggleSuperuser(u) {
		await apiSend('POST', `/admin/users/${u.id}/superuser?value=${!u.is_superuser}`);
		await loadAll();
	}

	function fmt(ts) {
		return new Date(ts).toLocaleString('pt-BR');
	}

	onMount(loadAll);
</script>

<h2>🛠️ Painel Administrativo</h2>

{#if error}
	<p class="error">{error}</p>
{:else if !overview}
	<p class="muted">carregando…</p>
{:else}
	<div class="kpis">
		<div class="kpi"><b>{overview.counts.users}</b><span>Usuários</span></div>
		<div class="kpi"><b>{overview.counts.events}</b><span>Eventos</span></div>
		<div class="kpi"><b>{overview.counts.sessions}</b><span>Sessões</span></div>
		<div class="kpi"><b>{overview.counts.saved_searches}</b><span>Buscas salvas</span></div>
		<div class="kpi"><b>{overview.counts.favorites}</b><span>Favoritos</span></div>
		<div class="kpi"><b class="ver">{overview.counts.data_version ?? '—'}</b><span>data_version</span></div>
	</div>

	<div class="tabs">
		<button class:active={tab === 'overview'} on:click={() => (tab = 'overview')}>Resumo</button>
		<button class:active={tab === 'events'} on:click={() => (tab = 'events')}>Eventos</button>
		<button class:active={tab === 'users'} on:click={() => (tab = 'users')}>Usuários</button>
	</div>

	{#if tab === 'overview'}
		<div class="cols">
			<div>
				<h3>Eventos por tipo</h3>
				<table>
					<tbody>
						{#each overview.events_by_type as e}
							<tr><td>{e.event_type}</td><td class="num">{e.n}</td></tr>
						{/each}
						{#if !overview.events_by_type.length}<tr><td class="muted">nenhum evento ainda</td></tr>{/if}
					</tbody>
				</table>
			</div>
			<div>
				<h3>Eventos por dia (14d)</h3>
				<table>
					<tbody>
						{#each overview.events_by_day as d}
							<tr><td>{d.day}</td><td class="num">{d.n}</td></tr>
						{/each}
						{#if !overview.events_by_day.length}<tr><td class="muted">sem dados</td></tr>{/if}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	{#if tab === 'events'}
		<div class="toolbar">
			<input placeholder="Filtrar por tipo…" bind:value={eventFilter} on:input={loadEvents} />
			<button on:click={loadEvents}>Atualizar</button>
		</div>
		<table>
			<thead><tr><th>Quando</th><th>Tipo</th><th>Usuário</th><th>Payload</th></tr></thead>
			<tbody>
				{#each events as ev}
					<tr>
						<td>{fmt(ev.created_at)}</td>
						<td>{ev.event_type}</td>
						<td>{ev.user_email ?? 'anônimo'}</td>
						<td><code>{JSON.stringify(ev.payload)}</code></td>
					</tr>
				{/each}
				{#if !events.length}<tr><td colspan="4" class="muted">nenhum evento</td></tr>{/if}
			</tbody>
		</table>
	{/if}

	{#if tab === 'users'}
		<table>
			<thead><tr><th>E-mail</th><th>Nome</th><th>Instituição</th><th>Criado</th><th>Admin</th></tr></thead>
			<tbody>
				{#each users as u}
					<tr>
						<td>{u.email}</td>
						<td>{u.display_name ?? '—'}</td>
						<td>{u.institution ?? '—'}</td>
						<td>{fmt(u.created_at)}</td>
						<td>
							<button
								class="toggle"
								class:on={u.is_superuser}
								disabled={u.id === $user?.id}
								on:click={() => toggleSuperuser(u)}
								title={u.id === $user?.id ? 'Não é possível alterar a si mesmo' : ''}
							>
								{u.is_superuser ? '✓ admin' : 'promover'}
							</button>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
{/if}

<style>
	.kpis { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }
	.kpi { background: #f5f7fa; border-radius: 8px; padding: 12px 20px; text-align: center; }
	.kpi b { font-size: 24px; display: block; }
	.kpi b.ver { font-size: 13px; font-family: monospace; color: #555; }
	.kpi span { color: #888; font-size: 12px; }
	.tabs { display: flex; gap: 6px; margin-bottom: 12px; }
	.tabs button { padding: 6px 14px; border: 1px solid #ddd; background: #fff; border-radius: 6px; cursor: pointer; }
	.tabs button.active { background: #4a90d9; color: #fff; border-color: #4a90d9; }
	.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; max-width: 800px; }
	.toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
	.toolbar input { padding: 6px 8px; }
	table { width: 100%; border-collapse: collapse; font-size: 13px; }
	th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
	.num { text-align: right; }
	code { font-size: 11px; color: #555; word-break: break-all; }
	.muted { color: #999; }
	.error { color: #c0392b; }
	.toggle { border: 1px solid #ccc; background: #fff; border-radius: 4px; padding: 2px 10px; cursor: pointer; }
	.toggle.on { background: #2ecc71; color: #fff; border-color: #2ecc71; }
	.toggle:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
