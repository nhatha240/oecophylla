<script lang="ts">
  import { env } from '$env/dynamic/public';
  import type { FeedItem, MyInteractions } from '$lib/types';
  import PostCard from './PostCard.svelte';
  import { viewTracker } from '$lib/actions/viewTracker';
  import { trackRecommendationClick, type RecommendationContext } from '$lib/telemetry/recommendationTelemetry';
  export let items: FeedItem[] = [];
  export let meByPost: Record<string, MyInteractions> = {};

  const telemetryEnabled = env.PUBLIC_RECOMMENDATION_TELEMETRY_ENABLED === 'true';

  function contextFor(item: FeedItem): RecommendationContext {
    return {
      post_id: item.id,
      impression_id: item.impression_id,
      request_id: item.request_id,
      model_version: item.model_version,
      position: item.position,
    };
  }
</script>

<ul class="flex flex-col gap-3">
  {#each items as item (item.id)}
    <li use:viewTracker={{ context: contextFor(item), enabled: telemetryEnabled }}>
      <PostCard
        post={item}
        me={meByPost[item.id] ?? null}
        onOpen={() => telemetryEnabled && trackRecommendationClick(contextFor(item))}
      />
    </li>
  {/each}
</ul>
