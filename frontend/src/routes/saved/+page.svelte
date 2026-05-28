<script lang="ts">
  import type { PageData } from './$types';
  import type { SavedPostItem, MyInteractions } from '$lib/types';
  import { getSavedPosts, getMyInteractionsBatch } from '$lib/api';
  import PostCard from '$lib/components/PostCard.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  export let data: PageData;

  let items: SavedPostItem[] = data.saved.items;
  let cursor: string | null = data.saved.next_cursor;
  let meByPost: Record<string, MyInteractions> = data.me;
  let loading = false;
  let error: string | null = null;

  async function loadMore(): Promise<void> {
    if (loading || !cursor) return;
    loading = true;
    error = null;
    try {
      const next = await getSavedPosts(fetch, cursor);
      const seen = new Set(items.map((p) => p.id));
      const fresh = next.items.filter((p) => !seen.has(p.id));
      if (fresh.length) {
        items = [...items, ...fresh];
        const ids = fresh.map((p) => p.id);
        const meBatch = await getMyInteractionsBatch(fetch, ids).catch(() => ({ items: {} }));
        meByPost = { ...meByPost, ...meBatch.items };
      }
      cursor = next.next_cursor;
    } catch (err) {
      error = err instanceof Error ? err.message : 'load_failed';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Đã lưu — Oecophylla</title>
</svelte:head>

<div class="feed-grid">
  <main class="feed-main">
    <div class="flex items-center gap-3 mb-4">
      <a href="/" class="glass-chip text-sm cursor-pointer">&larr; Bảng tin</a>
      <h2 class="text-lg font-semibold text-slate-800">Đã lưu</h2>
    </div>

    {#if items.length === 0}
      <div class="card card-pad" style="text-align: center; padding: 48px 24px;">
        <h2 class="serif" style="font-size: 24px; margin: 0 0 8px;">Chưa lưu bài nào</h2>
        <p class="muted" style="margin: 0;">Nhấn vào biểu tượng lưu trên bất kỳ bài viết nào để đọc lại sau.</p>
      </div>
    {:else}
      <ul class="flex flex-col gap-3">
        {#each items as item (item.id)}
          <li>
            <PostCard post={item} me={meByPost[item.id] ?? null} />
            <div class="text-mono-meta px-5 -mt-1 mb-2 opacity-70">
              @{item.username}
              <span class="glass-chip ml-2">đã lưu</span>
            </div>
          </li>
        {/each}
      </ul>
      {#if error}
        <p class="field err-msg" style="margin-top: 12px;">{error}</p>
      {/if}
      {#if cursor}
        <InfiniteSentinel disabled={loading} onVisible={loadMore} />
        {#if loading}
          <p class="t-meta" style="text-align: center; margin-top: 12px;">Đang tải thêm…</p>
        {/if}
      {:else}
        <p class="t-meta" style="text-align: center; margin-top: 20px;">Hết bài.</p>
      {/if}
    {/if}
  </main>

  <aside class="rail">
    <div class="rail-card">
      <h4><Icon name="Bookmark" size={16} className="pin" /> Bài đã lưu</h4>
      <p class="t-meta">Các bài viết bạn lưu sẽ xuất hiện ở đây. Không giới hạn số lượng.</p>
    </div>
  </aside>
</div>
