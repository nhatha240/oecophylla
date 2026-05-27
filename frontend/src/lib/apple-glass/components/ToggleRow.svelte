<script lang="ts">
  export let value = false;
  export let name = '';
  export let desc = '';
</script>

<div class="toggle-row">
  <div><div class="name">{name}</div><div class="desc">{desc}</div></div>
  <button class={`switch ${value ? 'on' : ''}`} on:click={() => (value = !value)} aria-label="toggle"></button>
</div>
