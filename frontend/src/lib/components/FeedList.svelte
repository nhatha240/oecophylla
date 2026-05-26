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
      <div class="text-mono-meta px-5 -mt-1 mb-2 opacity-70">
        @{item.username}
        {#if item.rank?.source}
          <span class="glass-chip ml-2">{item.rank.source}</span>
        {/if}
      </div>
    </li>
  {/each}
</ul>
