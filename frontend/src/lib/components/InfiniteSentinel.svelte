<script lang="ts">
  import { onMount } from 'svelte';
  export let disabled = false;
  export let onVisible: () => void;
  let el: HTMLDivElement;
  onMount(() => {
    const io = new IntersectionObserver((entries) => {
      if (!disabled && entries.some((e) => e.isIntersecting)) onVisible();
    }, { rootMargin: '400px' });
    if (el) io.observe(el);
    return () => io.disconnect();
  });
</script>
<div bind:this={el} aria-hidden="true" class="h-8"></div>
