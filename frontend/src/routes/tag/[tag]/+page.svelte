<script lang="ts">
  import { onMount } from 'svelte';
  import type { PageData } from './$types';
  import type { Post, MyInteractions } from '$lib/types';
  import { getPostsByTag, getMyInteractionsBatch } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import PostCard from '$lib/components/PostCard.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';

  export let data: PageData;

  let items: Post[] = data.posts ?? [];
  let cursor: string | null = data.nextCursor ?? null;
  let meByPost: Record<string, MyInteractions> = {};
  let loading = false;
  let error: string | null = null;

  async function loadMore(): Promise<void> {
    if (loading || !cursor) return;
    loading = true;
    error = null;
    try {
      const next = await getPostsByTag(fetch, data.tag, cursor);
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
  <title>#{data.tag} — Oecophylla</title>
</svelte:head>

<div class="feed-grid">
  <main class="feed-main">
    <div class="crumbs">
      <a href="/" style="color: var(--muted);"><Icon name="ArrowLeft" size={12} style="vertical-align: -2px" /> Quay lại bảng tin</a>
    </div>

    <div style="display: flex; gap: 8px; margin-bottom: 16px; align-items: center;">
      <span class="chip active">#{data.tag}</span>
      <span class="t-meta">{items.length} bài viết</span>
    </div>

    {#if items.length === 0}
      <div class="card card-pad" style="text-align: center; padding: 48px 24px;">
        <h2 class="serif" style="font-size: 24px; margin: 0 0 8px;">Chưa có bài viết với tag #{data.tag}</h2>
        <p class="muted" style="margin: 0;">Hãy quay lại sau hoặc thử tag khác.</p>
      </div>
    {:else}
      <ul class="flex flex-col gap-3">
        {#each items as item (item.id)}
          <li>
            <PostCard post={item} me={meByPost[item.id] ?? null} />
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
</div>
