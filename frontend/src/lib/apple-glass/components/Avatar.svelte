<script lang="ts">
  import Icon from './Icon.svelte';
  import type { Author } from '../data';

  export let author: Author | null = null;
  export let size = 's40';
  export let square = false;
  export let showVerified = false;

  $: initials = author
    ? author.name
        .split(' ')
        .slice(-2)
        .map((part) => part[0])
        .join('')
        .toUpperCase()
    : '';
</script>

{#if author}
  <span class={`avatar ${size} ${square ? 'sq' : ''} t-${author.tint || 'emerald'}`}>
    {initials}
    {#if showVerified && author.verified}
      <span class="verified" title="Đã xác minh">
        <Icon name="Check" size={9} />
      </span>
    {/if}
  </span>
{/if}
