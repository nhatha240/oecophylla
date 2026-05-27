<script lang="ts">
  import type { PageData } from './$types';
  import type { FeedItem, MyInteractions } from '$lib/types';
  import { getFeed, getMyInteractionsBatch } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import Composer from '$lib/components/Composer.svelte';
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

<div class="feed-grid">
  <main class="feed-main">
    {#if data.feed}
      <Composer action="/post/new" />
    {/if}

    <div class="tabs">
      <button class="tab active"><Icon name="Sparkle" size={14} /> Dành cho bạn</button>
      <button class="tab"><Icon name="Users" size={14} /> Đang theo dõi</button>
      <button class="tab"><Icon name="Clock" size={14} /> Tin mới</button>
    </div>

    {#if !data.feed}
      <div class="card card-pad" style="text-align: center; padding: 48px 24px;">
        <h2 class="serif" style="font-size: 28px; margin: 0 0 8px;">Bảng tin Apple Glass đang chờ bạn</h2>
        <p class="muted" style="margin: 0 auto; max-width: 480px;">Đăng nhập để xem dòng tin được cá nhân hoá, theo dõi chủ đề quan tâm và lưu bài viết để đọc lại.</p>
        <a class="btn emerald" style="margin-top: 18px;" href="/login">Đăng nhập</a>
      </div>
    {:else if items.length === 0}
      <div class="card card-pad" style="text-align: center; padding: 48px 24px;">
        <h2 class="serif" style="font-size: 24px; margin: 0 0 8px;">Chưa có bài viết nào để gợi ý</h2>
        <p class="muted" style="margin: 0;">Hãy thử đăng bài đầu tiên hoặc theo dõi thêm chủ đề để làm giàu bảng tin.</p>
      </div>
    {:else}
      <FeedList {items} {meByPost} />
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
      <h4><Icon name="Flame" size={16} className="pin" /> Đang thịnh hành</h4>
      {#each ['AI có trách nhiệm', 'Báo chí số', 'Kinh tế Việt Nam'] as trend, i}
        <div class="trend-item">
          <span class="trend-num">{i + 1}</span>
          <div>
            <div class="trend-title">#{trend}</div>
            <div class="trend-meta"><span>chủ đề</span><span>·</span><span>đọc nhiều hôm nay</span></div>
          </div>
        </div>
      {/each}
    </div>

    <div class="rail-card">
      <h4><Icon name="ChartBar" size={16} className="pin" /> Nhịp đọc của bạn</h4>
      <div class="taste-bars">
        <div class="taste-bar">
          <div class="taste-bar-head"><span>Công nghệ</span><span class="pct">82%</span></div>
          <div class="taste-bar-track"><div class="taste-bar-fill" style="width: 82%;"></div></div>
        </div>
        <div class="taste-bar">
          <div class="taste-bar-head"><span>AI</span><span class="pct">67%</span></div>
          <div class="taste-bar-track"><div class="taste-bar-fill" style="width: 67%;"></div></div>
        </div>
        <div class="taste-bar">
          <div class="taste-bar-head"><span>Xã hội</span><span class="pct">39%</span></div>
          <div class="taste-bar-track"><div class="taste-bar-fill" style="width: 39%;"></div></div>
        </div>
      </div>
    </div>
  </aside>
</div>
