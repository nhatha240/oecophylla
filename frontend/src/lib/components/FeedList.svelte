<script lang="ts">
  import type { FeedItem, MyInteractions } from '$lib/types';
  import PostCard from './PostCard.svelte';
  import { viewTracker } from '$lib/actions/viewTracker';
  export let items: FeedItem[] = [];
  export let meByPost: Record<string, MyInteractions> = {};
</script>

<ul class="flex flex-col gap-3">
  {#each items as item (item.id)}
    <li use:viewTracker={item.id}>
      <PostCard post={item} me={meByPost[item.id] ?? null} />
    </li>
  {/each}
</ul>
