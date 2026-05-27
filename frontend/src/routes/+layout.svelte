<script lang="ts">
  import '../app.css';
  import { user } from '$lib/stores/auth';
  export let data: { user: import('$lib/types').User | null };
  $: user.set(data.user);
</script>

<slot />
