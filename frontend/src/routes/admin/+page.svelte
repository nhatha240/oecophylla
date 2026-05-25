<script lang="ts">
  import { mockReports, mockMetrics } from '$lib/mock/admin';
</script>
<h1 class="text-display-serif text-3xl mb-3">Quản trị (mock)</h1>
<section class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
  {#each Object.entries(mockMetrics) as [k, v]}
    <div class="glass-surface p-4">
      <p class="text-mono-meta">{k}</p>
      <p class="text-2xl text-display-serif">{v}</p>
    </div>
  {/each}
</section>
<section class="glass-surface p-4">
  <h2 class="text-display-serif text-xl mb-3">Báo cáo đang chờ</h2>
  <ul class="divide-y divide-white/40">
    {#each mockReports as r (r.id)}
      <li class="py-3 flex justify-between">
        <span>{r.reason} · {r.post_id}</span>
        <span class="text-mono-meta">{r.status}</span>
      </li>
    {/each}
  </ul>
</section>
