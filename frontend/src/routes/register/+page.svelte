<script lang="ts">
  import AuthForm from '$lib/components/AuthForm.svelte';
  export let form: { error?: string } | null;
</script>
<AuthForm mode="register" error={form?.error ?? null} />
