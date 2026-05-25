<script lang="ts">
  import PostCard from '$lib/components/PostCard.svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import { mockFeed } from '$lib/mock/feed';
</script>
<div class="grid grid-cols-1 md:grid-cols-[1fr_16rem] gap-6">
  <section>
    <p class="text-mono-meta mb-3">(Phase 1 — feed sử dụng dữ liệu mẫu. Phase 2 sẽ kết nối recommendation-api.)</p>
    {#each mockFeed as p (p.id)}<PostCard post={p} />{/each}
  </section>
  <Sidebar />
</div>
