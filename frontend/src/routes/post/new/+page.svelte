<script lang="ts">
  import Composer from '$lib/components/Composer.svelte';
  export let form: { error?: string } | null;
</script>
<Composer error={form?.error ?? null} />
