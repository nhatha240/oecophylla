<script lang="ts">
  export let size = 34;
</script>

<span class="brand-logo" style:--mark-size={size + 'px'}>
  <img src="/brand/mark.svg" alt="" width={size} height={size} />
  <span>Oecophylla</span>
</span>

<style>
  .brand-logo { display: inline-flex; align-items: center; gap: calc(var(--mark-size) * .18); color: #092f2e; white-space: nowrap; }
  img { width: var(--mark-size); height: var(--mark-size); object-fit: contain; }
  span span { font: 600 calc(var(--mark-size) * .72)/1 'Lora', Georgia, serif; letter-spacing: -.065em; }
</style>
