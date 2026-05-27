<script lang="ts">
  import Icon from './Icon.svelte';
  import { TOPICS } from '../data';

  export let kind = 'verified-src';
  export let label = '';
  export let topicId: string | null = null;
  export let outline = false;

  const badgeIcons: Record<string, string> = {
    'verified-src': 'Shield',
    moderated: 'Check',
    pending: 'Clock',
    flagged: 'Flag',
    ai: 'Sparkle'
  };

  $: topic = topicId ? TOPICS.find((item) => item.id === topicId) : null;
</script>

{#if topic}
  <span class={`chip ${outline ? 'outline' : ''}`}>#{topic.name}</span>
{:else}
  <span class={`badge ${kind}`}>
    <Icon name={badgeIcons[kind] || 'Check'} size={11} />
    {label}
  </span>
{/if}
