<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from './Icon.svelte';

  export let message = '';
  export let onClose: () => void = () => {};

  onMount(() => {
    const timer = window.setTimeout(onClose, 2200);
    return () => window.clearTimeout(timer);
  });
</script>

<div class="toast"><Icon name="Check" size={14} /> {message}</div>
