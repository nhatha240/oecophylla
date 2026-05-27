<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Icon from './Icon.svelte';
  import type { Author } from '../data';

  export let author: Author;
  let followed = false;
</script>

<div class="suggest-item">
  <Avatar {author} size="s32" showVerified />
  <div class="meta">
    <div class="n">{author.name} {#if author.verified}<Icon name="Verified" size={12} style="color: var(--azure-500)" />{/if}</div>
    <div class="s">{author.reason || author.handle}</div>
  </div>
  <button class={`btn ${followed ? 'ghost' : 'primary'} sm`} on:click={() => (followed = !followed)}>
    {followed ? 'Đang theo dõi' : '+ Theo dõi'}
  </button>
</div>
