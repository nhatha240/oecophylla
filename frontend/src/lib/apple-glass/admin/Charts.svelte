<script lang="ts">
  export let kind: 'area' | 'bars' | 'donut' = 'area';
  export let data: number[] = [];
  export let secondary: number[] = [];
  export let height = 180;
  export let items: { label: string; value: number; display?: string; color?: string }[] = [];
  export let max = 0;

  const width = 600;
  $: values = [...data, ...secondary];
  $: chartMax = Math.max(...values, 1);
  $: points = data.map((v, i) => [i * (width / Math.max(data.length - 1, 1)), height - (v / chartMax) * (height - 30) - 10]);
  $: path = points.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  $: area = points.length ? `${path} L${points[points.length - 1][0]} ${height} L0 ${height} Z` : '';
  $: secondaryPoints = secondary.map((v, i) => [i * (width / Math.max(secondary.length - 1, 1)), height - (v / chartMax) * (height - 30) - 10]);
  $: secondaryPath = secondaryPoints.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  $: barMax = max || Math.max(...items.map((item) => item.value), 1);
</script>

{#if kind === 'area'}
  <svg viewBox={`0 0 ${width} ${height}`} width="100%" {height} style="display: block">
    <defs><linearGradient id="ag1" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="var(--emerald-50)" stop-opacity="0.9" /><stop offset="100%" stop-color="var(--emerald-50)" stop-opacity="0.1" /></linearGradient></defs>
    {#each [0.25, 0.5, 0.75] as line}<line x1="0" x2={width} y1={height * line} y2={height * line} stroke="var(--hairline)" stroke-dasharray="2 4" />{/each}
    <path d={area} fill="url(#ag1)" />
    <path d={path} fill="none" stroke="var(--emerald-500)" stroke-width="2" />
    {#if secondary.length}<path d={secondaryPath} fill="none" stroke="var(--muted-2)" stroke-width="2" stroke-dasharray="4 4" />{/if}
  </svg>
{:else if kind === 'bars'}
  <div class="bars">
    {#each items as item}
      <div>
        <div class="bar-head"><span>{item.label}</span><span>{item.display ?? item.value}</span></div>
        <div class="bar-track"><div class="bar-fill" style={`width: ${(item.value / barMax) * 100}%; background: ${item.color || 'var(--emerald-500)'}`}></div></div>
      </div>
    {/each}
  </div>
{:else}
  <div class="donut"><div><b>12.4K</b><span>bài hôm nay</span></div></div>
{/if}

<style>
  .bars { display: flex; flex-direction: column; gap: 12px; }
  .bar-head { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }
  .bar-head span:first-child { font-weight: 500; }
  .bar-head span:last-child { color: var(--muted); }
  .bar-track { height: 6px; background: var(--surface-2); border-radius: 99px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 99px; transition: width 0.4s ease; }
  .donut { width: 150px; height: 150px; border-radius: 50%; background: conic-gradient(var(--emerald-500) 0 32%, var(--azure-500) 32% 54%, var(--amber-500) 54% 72%, var(--violet-500) 72% 86%, var(--rose-500) 86% 94%, var(--muted-2) 94%); display: grid; place-items: center; }
  .donut > div { width: 96px; height: 96px; border-radius: 50%; background: var(--surface); display: grid; place-items: center; align-content: center; }
  .donut b { font: 500 22px var(--font-serif); }
  .donut span { font-size: 10px; color: var(--muted); }
</style>
