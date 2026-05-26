<script lang="ts">
  import type { PageData } from './$types';
  import type { FeedItem, MyInteractions } from '$lib/types';
  import { getFeed, getMyInteractionsBatch } from '$lib/api';
  import FeedList from '$lib/components/FeedList.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';

  export let data: PageData;

  let items: FeedItem[] = data.feed?.items ?? [];
  let cursor: string | null = data.feed?.next_cursor ?? null;
  let meByPost: Record<string, MyInteractions> = data.me ?? {};
  let loading = false;
  let error: string | null = null;

  async function loadMore(): Promise<void> {
    if (loading || !cursor) return;
    loading = true;
    error = null;
    try {
      const next = await getFeed(fetch, cursor, 20);
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
      error = err instanceof Error ? err.message : 'feed_load_failed';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Oecophylla — Feed</title>
</svelte:head>

<section class="mx-auto w-full max-w-2xl px-4 py-6">
  {#if !data.feed}
    <div class="glass-surface p-6 text-center">
      <p>Đăng nhập để xem dòng tin được cá nhân hoá.</p>
      <a class="glass-button-primary mt-4 inline-block" href="/login">Đăng nhập</a>
    </div>
  {:else if items.length === 0}
    <div class="glass-surface p-6 text-center">
      <p>Chưa có bài viết nào để gợi ý.</p>
    </div>
  {:else}
    <FeedList {items} {meByPost} />
    {#if error}
      <p class="text-mono-meta mt-3 text-red-500">{error}</p>
    {/if}
    {#if cursor}
      <InfiniteSentinel disabled={loading} onVisible={loadMore} />
      {#if loading}
        <p class="text-mono-meta text-center mt-3 opacity-70">Đang tải thêm…</p>
      {/if}
    {:else}
      <p class="text-mono-meta text-center mt-6 opacity-60">Hết bài.</p>
    {/if}
  {/if}
</section>
