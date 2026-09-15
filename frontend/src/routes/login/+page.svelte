<script>
	import { goto } from '$app/navigation';
	import { login, register } from '$lib/auth.js';

	let mode = 'login';
	let email = '';
	let password = '';
	let displayName = '';
	let institution = '';
	let error = '';
	let busy = false;

	async function submit() {
		error = '';
		busy = true;
		try {
			if (mode === 'login') {
				await login(email, password);
			} else {
				await register(email, password, { display_name: displayName, institution });
			}
			goto('/');
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}
</script>

<div class="card">
	<h2>{mode === 'login' ? 'Entrar' : 'Criar conta'}</h2>
	<form on:submit|preventDefault={submit}>
		<input type="email" placeholder="E-mail" bind:value={email} required />
		<input type="password" placeholder="Senha" bind:value={password} required />
		{#if mode === 'register'}
			<input placeholder="Nome (opcional)" bind:value={displayName} />
			<input placeholder="Instituição (opcional)" bind:value={institution} />
		{/if}
		{#if error}<p class="error">{error}</p>{/if}
		<button disabled={busy}>{busy ? '…' : mode === 'login' ? 'Entrar' : 'Registrar'}</button>
	</form>
	<button class="link" on:click={() => (mode = mode === 'login' ? 'register' : 'login')}>
		{mode === 'login' ? 'Não tem conta? Registre-se' : 'Já tem conta? Entrar'}
	</button>
</div>

<style>
	.card {
		max-width: 360px;
		margin: 40px auto;
		padding: 24px;
		border: 1px solid #e5e5e5;
		border-radius: 8px;
	}
	form {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	input {
		padding: 8px;
	}
	button {
		padding: 8px;
		cursor: pointer;
	}
	.link {
		background: none;
		border: none;
		color: #4a90d9;
		margin-top: 12px;
	}
	.error {
		color: #c0392b;
		font-size: 13px;
	}
</style>
