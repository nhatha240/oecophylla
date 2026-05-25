<script lang="ts">
  import MobileShell from '$lib/components/MobileShell.svelte';
  import { mockFeed } from '$lib/mock/feed';
  import PostCard from '$lib/components/PostCard.svelte';
</script>
<h1 class="text-display-serif text-2xl mb-3">Mobile preview</h1>
{#each mockFeed.slice(0, 3) as p (p.id)}<PostCard post={p} />{/each}
<MobileShell />
