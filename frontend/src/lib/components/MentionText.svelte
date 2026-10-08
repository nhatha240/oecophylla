<script lang="ts">
  import { splitMentions } from '$lib/mentions';
  export let text = '';
  $: parts = splitMentions(text);
</script>

{#each parts as part}
  {#if 'username' in part}<a class="mention" href={'/search?q=' + encodeURIComponent(part.username)}>@{part.username}</a>{:else}{part.text}{/if}
{/each}

<style>
  .mention { color: #16695d; font-weight: 600; text-decoration: underline; text-underline-offset: 2px; }
</style>
