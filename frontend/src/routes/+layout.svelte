<script lang="ts">
  import '../app.css';
  import { user } from '$lib/stores/auth';
  import Topbar from '$lib/components/Topbar.svelte';
  export let data: { user: import('$lib/types').User | null };
  $: user.set(data.user);
</script>
<div class="min-h-screen flex flex-col">
  <Topbar />
  <main class="flex-1 max-w-3xl w-full mx-auto p-4">
    <slot />
  </main>
</div>
