<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { invalidateAll } from '$app/navigation';
  import type { PageData } from './$types';
  import type { FeedItem, MyInteractions, UserPreferences } from '$lib/types';
  import { getFeed, getMyInteractionsBatch, getTrendingTopics, type TrendingTopic } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import Composer from '$lib/components/Composer.svelte';
  import FeedList from '$lib/components/FeedList.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';
  import SuggestedUsers from '$lib/components/SuggestedUsers.svelte';

  export let data: PageData;

  const TOPIC_LABELS: Record<string, string> = {
    tech: 'Công nghệ', science: 'Khoa học', sports: 'Thể thao',
    politics: 'Chính trị', entertainment: 'Giải trí', health: 'Sức khoẻ',
    business: 'Kinh doanh', culture: 'Văn hoá', education: 'Giáo dục',
    environment: 'Môi trường', ai: 'AI & Học máy', news: 'Tin tức',
  };

  const TOPIC_COLORS: Record<string, string> = {
    tech: '#3b82f6', science: '#8b5cf6', sports: '#f59e0b',
    politics: '#ef4444', entertainment: '#ec4899', health: '#22c55e',
    business: '#06b6d4', culture: '#f97316', education: '#6366f1',
    environment: '#14b8a6', ai: '#a855f7', news: '#64748b',
  };

  let items: FeedItem[] = data.feed?.items ?? [];
  let cursor: string | null = data.feed?.next_cursor ?? null;
  let meByPost: Record<string, MyInteractions> = data.me ?? {};
  let loading = false;
  let error: string | null = null;
  let feedMode: 'foryou' | 'following' | 'trending' = data.feedMode ?? 'foryou';
  let prefs: UserPreferences | null = data.prefs ?? null;

  $: topicBars = (() => {
    if (!prefs?.topic_weights) return [];
    const entries = Object.entries(prefs.topic_weights)
      .filter(([slug, w]) => w > 0 && slug !== 'general')
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);
    if (!entries.length) return [];
    const max = entries[0][1];
    return entries.map(([slug, weight]) => ({
      slug,
      label: TOPIC_LABELS[slug] ?? slug,
      color: TOPIC_COLORS[slug] ?? '#94a3b8',
      pct: Math.round((weight / max) * 100),
    }));
  })();
  let localSort: 'default' | 'new' | 'trend' = 'default';
  let trendingTopics: TrendingTopic[] = [];
  let lastUpdate = Date.now();
  let updatedAgo = 'vài giây trước';
  let updateTimer: ReturnType<typeof setInterval> | null = null;
  function fmtAgo(ms: number): string {
    const s = Math.floor((Date.now() - ms) / 1000);
    if (s < 60) return `${s} giây trước`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m} phút trước`;
    const h = Math.floor(m / 60);
    return `${h} giờ trước`;
  }
  function sortBy(mode: 'new' | 'trend'): void {
    localSort = mode;
    if (mode === 'new') {
      items = [...items].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
    } else {
      // Fetch from trending API for real ranking scores
      switchFeed('trending');
    }
  }

  async function switchFeed(mode: 'foryou' | 'following' | 'trending'): Promise<void> {
    if (feedMode === mode) return;
    feedMode = mode;
    items = [];
    cursor = null;
    loading = true;
    error = null;
    try {
      const modeParam = mode === 'following' ? 'following' : mode === 'trending' ? 'trending' : undefined;
      const next = await getFeed(fetch, undefined, 20, modeParam);
      items = next.items;
      cursor = next.next_cursor;
      if (items.length) {
        const ids = items.map((p) => p.id);
        const meBatch = await getMyInteractionsBatch(fetch, ids).catch(() => ({ items: {} }));
        meByPost = meBatch.items;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'feed_load_failed';
    } finally {
      loading = false;
    }
  }

  let newPostCount = 0;
  let isFirstEvent = true;
  let es: EventSource | null = null;

  onMount(() => {
    updatedAgo = fmtAgo(lastUpdate);
    updateTimer = setInterval(() => { updatedAgo = fmtAgo(lastUpdate); }, 10000);
    getTrendingTopics(fetch).then((t) => { trendingTopics = t; }).catch(() => {});
    es = new EventSource('/api/v1/feed/trending/stream');
    es.addEventListener('trending', (e: MessageEvent) => {
      if (isFirstEvent) {
        isFirstEvent = false;
        return;
      }
      try {
        const ids: string[] = JSON.parse(e.data);
        const known = new Set(items.map((p) => p.id));
        const fresh = ids.filter((id) => !known.has(id));
        if (fresh.length > 0) newPostCount += fresh.length;
      } catch { /* ignore parse errors */ }
    });
  });

  onDestroy(() => {
    es?.close();
    if (updateTimer) clearInterval(updateTimer);
  });

  let prefsLoading = false;
  async function refreshPrefs(): Promise<void> {
    if (!data.user?.id || prefsLoading) return;
    prefsLoading = true;
    try {
      const { getUserPreferences } = await import('$lib/api');
      const fresh = await getUserPreferences(fetch, data.user.id);
      if (fresh) prefs = fresh;
    } catch { /* silent */ } finally {
      prefsLoading = false;
    }
  }

  async function loadNew(): Promise<void> {
    newPostCount = 0;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    await invalidateAll();
  }

  async function loadMore(): Promise<void> {
    if (loading || !cursor) return;
    loading = true;
    error = null;
    try {
      const modeParam = feedMode === 'following' ? 'following' : feedMode === 'trending' ? 'trending' : undefined;
      const next = await getFeed(fetch, cursor, 20, modeParam);
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
    {#if newPostCount > 0}
      <button
        class="glass-surface w-full rounded-2xl px-4 py-3 text-sm font-medium text-slate-700 shadow transition-all animate-slide-down flex items-center justify-center gap-2"
        on:click={loadNew}
      >
        <span>✨ {newPostCount > 99 ? '99+' : newPostCount} bài viết mới</span>
        <span class="glass-chip text-xs">Nhấn để tải</span>
      </button>
    {/if}

    {#if data.feed}
      <Composer action="/post/new" />
    {/if}

    <div class="tabs">
      <button class="tab" class:active={feedMode === 'foryou' && localSort === 'default'} on:click={() => { localSort = 'default'; switchFeed('foryou'); }}>
        <Icon name="Sparkle" size={14} /> Dành cho bạn
      </button>
      <button class="tab" class:active={feedMode === 'following'} on:click={() => { localSort = 'default'; switchFeed('following'); }}>
        <Icon name="Users" size={14} /> Đang theo dõi
      </button>
      <button class="tab" class:active={localSort === 'new'} on:click={() => sortBy('new')}>
        <Icon name="Clock" size={14} /> Tin mới
      </button>
      <button class="tab" class:active={localSort === 'trend' || feedMode === 'trending'} on:click={() => sortBy('trend')}>
        <Icon name="Flame" size={14} /> Xu hướng
      </button>
      <a class="tab" href="/saved">
        <Icon name="Bookmark" size={14} /> Đã lưu
      </a>
      <span class="tab-update t-meta">Cập nhật {updatedAgo}</span>
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
      {#if trendingTopics.length > 0}
        {#each trendingTopics as topic, i}
          <a class="trend-item" href="/search?q={encodeURIComponent(topic.slug)}">
            <span class="trend-num">{i + 1}</span>
            <div>
              <div class="trend-title">#{topic.label}</div>
              <div class="trend-meta"><span>{topic.count} bài viết</span><span>·</span><span>xu hướng 24h</span></div>
            </div>
          </a>
        {/each}
      {:else}
        <p class="taste-empty">Đang tải xu hướng…</p>
      {/if}
    </div>

    <div class="rail-card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <h4 style="margin:0;"><Icon name="ChartBar" size={16} className="pin" /> Nhịp đọc của bạn</h4>
        {#if data.user}
          <button
            type="button"
            class="icon-btn"
            title="Làm mới"
            style="opacity:{prefsLoading ? 0.4 : 0.6};"
            disabled={prefsLoading}
            on:click={refreshPrefs}
          ><Icon name="Refresh" size={13} /></button>
        {/if}
      </div>
      {#if topicBars.length > 0}
        <div class="taste-bars">
          {#each topicBars as bar}
            <div class="taste-bar">
              <div class="taste-bar-head">
                <span style="display:flex;align-items:center;gap:5px;">
                  <span style="width:8px;height:8px;border-radius:50%;background:{bar.color};flex-shrink:0;"></span>
                  {bar.label}
                </span>
                <span class="pct">{bar.pct}%</span>
              </div>
              <div class="taste-bar-track">
                <div class="taste-bar-fill" style="width:{bar.pct}%;background:{bar.color};opacity:0.85;"></div>
              </div>
            </div>
          {/each}
        </div>
        <p style="font-size:11px;color:var(--ink-300,#cbd5e1);margin:10px 0 0;text-align:right;">
          Dựa trên {Object.keys(prefs?.topic_weights ?? {}).length} chủ đề bạn đã tương tác
        </p>
      {:else if data.user}
        <p class="taste-empty">Hãy thích, lưu hoặc chia sẻ bài viết — chúng tôi sẽ học sở thích của bạn theo thời gian.</p>
      {:else}
        <p class="taste-empty"><a href="/login" style="color:var(--emerald-600);">Đăng nhập</a> để cá nhân hoá nhịp đọc.</p>
      {/if}
    </div>

    <SuggestedUsers />
  </aside>
</div>
