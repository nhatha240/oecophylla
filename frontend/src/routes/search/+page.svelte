<script lang="ts">
  import { goto, invalidateAll } from '$app/navigation';
  import { page } from '$app/stores';
  import type { PageData } from './$types';
  import type { SearchPost, Profile, FeedItem } from '$lib/types';
  import { searchPosts, searchUsers } from '$lib/api';
  import PostCard from '$lib/components/PostCard.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  export let data: PageData;

  // ── local state ───────────────────────────────────────────────────
  let q = data.q;
  let activeType: 'post' | 'user' = (data.type as 'post' | 'user') ?? 'post';
  let activeFilter = data.filter ?? 'all';
  let loading = false;

  // Re-sync when server re-runs the load (URL navigation)
  $: {
    q = data.q;
    activeType = (data.type as 'post' | 'user') ?? 'post';
    activeFilter = data.filter ?? 'all';
  }
  $: posts = (data.posts?.items ?? []) as SearchPost[];
  $: postCursor = data.posts?.next_cursor ?? null;
  $: users = (data.users?.items ?? []) as Profile[];
  let debounceTimer: ReturnType<typeof setTimeout>;

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

  // growth pcts are illustrative — derived from topic post counts relative to max
  $: topicCards = (() => {
    const topics = data.trendingTopics ?? [];
    if (!topics.length) return [];
    const maxCount = topics[0]?.count ?? 1;
    return topics.slice(0, 6).map((t, i) => ({
      slug: t.slug,
      label: TOPIC_LABELS[t.slug] ?? t.label,
      color: TOPIC_COLORS[t.slug] ?? '#64748b',
      count: t.count,
      // Simulate growth: top topics have higher growth %
      growth: Math.round(10 + ((topics.length - i) / topics.length) * 55),
    }));
  })();

  const FILTERS = [
    { id: 'all',     label: 'Tất cả' },
    { id: 'trusted', label: 'Đáng tin cậy' },
    { id: 'popular', label: 'Phổ biến nhất' },
    { id: 'long',    label: 'Bài dài' },
  ];

  // ── search interaction ────────────────────────────────────────────
  function onInput(): void {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const params = new URLSearchParams($page.url.searchParams);
      if (q.trim()) params.set('q', q.trim()); else params.delete('q');
      params.set('type', activeType);
      goto(`/search?${params}`, { replaceState: true, keepFocus: true });
    }, 300);
  }

  async function switchType(t: 'post' | 'user'): Promise<void> {
    const params = new URLSearchParams();
    if (q.trim()) params.set('q', q.trim());
    params.set('type', t);
    await goto(`/search?${params}`, { keepFocus: true, noScroll: true });
    await invalidateAll();
  }

  async function loadMore(): Promise<void> {
    if (loading || !postCursor || activeType !== 'post') return;
    loading = true;
    try {
      const next = await searchPosts(fetch, q, postCursor);
      const seen = new Set(posts.map((p) => p.id));
      const fresh = next.items.filter((p) => !seen.has(p.id));
      if (fresh.length) posts = [...posts, ...fresh];
      postCursor = next.next_cursor;
    } catch { /* silent */ } finally {
      loading = false;
    }
  }

  function searchTopic(slug: string): void {
    goto(`/search?q=${encodeURIComponent(slug)}&type=post`);
  }

  // Avatar color helper
  const COLORS = ['#22c55e','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#ec4899','#14b8a6'];
  function avatarColor(id: string): string {
    return COLORS[parseInt(id.replace(/-/g,'').slice(0,8), 16) % COLORS.length];
  }
</script>

<svelte:head>
  <title>Khám phá — Oecophylla</title>
</svelte:head>

<div class="feed-grid">
  <!-- ── MAIN CONTENT ─────────────────────────────────────────────── -->
  <main class="feed-main">

    {#if data.mode === 'explore'}
      <!-- Hero header -->
      <div style="margin-bottom:24px;">
        <h1 style="font-size:clamp(22px,4vw,32px);font-weight:800;letter-spacing:-0.03em;color:var(--ink-900,#0f172a);margin:0 0 6px;">
          Tin tức, ý tưởng và cộng đồng
          <em style="color:var(--emerald-600,#16a34a);font-style:normal;"> phù hợp với bạn</em>
        </h1>
        <p style="font-size:14px;color:var(--ink-400,#94a3b8);margin:0;">
          Tìm kiếm sâu hơn theo chủ đề, tác giả hoặc nội dung bài viết.
        </p>
      </div>
    {/if}

    <!-- Search bar -->
    <div class="card card-pad" style="padding:12px 16px;margin-bottom:16px;display:flex;align-items:center;gap:10px;">
      <span style="color:var(--ink-300,#cbd5e1);flex-shrink:0;"><Icon name="Search" size={18} /></span>
      <input
        type="text"
        bind:value={q}
        on:input={onInput}
        placeholder={data.mode === 'explore' ? 'Thử "AI", "khởi nghiệp", "@tên người dùng"…' : 'Tìm bài viết, tác giả, chủ đề…'}
        style="flex:1;border:none;outline:none;background:transparent;font-size:15px;color:var(--ink-900,#0f172a);"
      />
      {#if q}
        <button
          type="button"
          style="border:none;background:none;cursor:pointer;color:var(--ink-300,#cbd5e1);padding:0;"
          on:click={() => { q = ''; goto('/search'); }}
        ><Icon name="X" size={14} /></button>
      {/if}
    </div>

    <!-- Filter row -->
    <div class="filter-row">
      <!-- Type segmented control (only in search mode) -->
      {#if data.mode === 'search'}
        <div class="type-seg">
          <button class:seg-active={activeType === 'post'} on:click={() => switchType('post')}>Bài viết</button>
          <button class:seg-active={activeType === 'user'} on:click={() => switchType('user')}>Người dùng</button>
        </div>
        <div class="filter-divider"></div>
      {/if}

      <!-- Filter pills -->
      {#each FILTERS as f}
        <button
          class="fpill"
          class:fpill-active={activeFilter === f.id}
          on:click={() => (activeFilter = f.id)}
        >{f.label}</button>
      {/each}
    </div>

    <!-- ── EXPLORE MODE ─────────────────────────────────────────── -->
    {#if data.mode === 'explore'}

      <!-- Trending topics grid -->
      {#if topicCards.length > 0}
        <div style="margin-bottom:28px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <h2 style="font-size:16px;font-weight:700;color:var(--ink-900,#0f172a);margin:0;display:flex;align-items:center;gap:6px;">
              <Icon name="Flame" size={16} />
              Chủ đề đang tăng trưởng
            </h2>
            <a href="/search?q=&type=post" style="font-size:12px;color:var(--emerald-600,#16a34a);text-decoration:none;font-weight:600;">Xem tất cả</a>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;">
            {#each topicCards as t}
              <button
                class="card card-pad"
                style="padding:14px;text-align:left;cursor:pointer;border:none;transition:box-shadow 0.15s;"
                on:click={() => searchTopic(t.slug)}
                on:mouseenter={(e) => (e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.10)')}
                on:mouseleave={(e) => (e.currentTarget.style.boxShadow = '')}
              >
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
                  <span style="font-size:9px;font-weight:700;letter-spacing:0.08em;color:var(--ink-300,#cbd5e1);text-transform:uppercase;">Chủ đề</span>
                </div>
                <div style="font-size:15px;font-weight:700;color:var(--ink-900,#0f172a);margin-bottom:4px;line-height:1.3;">
                  {t.label}
                </div>
                <div style="font-size:12px;color:var(--ink-400,#94a3b8);margin-bottom:8px;">
                  {t.count} bài viết
                </div>
                <div style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:999px;background:{t.color}18;font-size:11px;font-weight:600;color:{t.color};">
                  ↑ +{t.growth}%
                </div>
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Featured posts -->
      {#if data.featuredPosts?.length}
        <div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <h2 style="font-size:16px;font-weight:700;color:var(--ink-900,#0f172a);margin:0;display:flex;align-items:center;gap:6px;">
              <Icon name="Sparkle" size={16} />
              Bài viết nổi bật
            </h2>
            <a href="/" style="font-size:12px;color:var(--emerald-600,#16a34a);text-decoration:none;font-weight:600;">Về bảng tin</a>
          </div>
          <div style="display:flex;flex-direction:column;gap:0;">
            {#each data.featuredPosts as post}
              <PostCard {post} />
            {/each}
          </div>
        </div>
      {:else}
        <div class="card card-pad" style="text-align:center;padding:48px 24px;">
          <div style="font-size:32px;margin-bottom:8px;">🔍</div>
          <p style="color:var(--ink-400,#94a3b8);font-size:14px;margin:0;">
            Nhập từ khoá để tìm kiếm bài viết, tác giả hoặc chủ đề.
          </p>
        </div>
      {/if}

    <!-- ── SEARCH RESULTS MODE ──────────────────────────────────── -->
    {:else if activeType === 'post'}
      {#if posts.length === 0}
        <div class="card card-pad" style="text-align:center;padding:48px 24px;">
          <div style="font-size:32px;margin-bottom:8px;">🔍</div>
          <p style="color:var(--ink-400,#94a3b8);font-size:14px;margin:0;">
            Không tìm thấy bài viết nào cho "<strong>{q}</strong>"
          </p>
        </div>
      {:else}
        {#each posts as post (post.id)}
          <article class="post">
            <div class="post-head">
              <a href="/profile/{post.author_id}" class="avatar s40" style="background:{avatarColor(post.author_id)};text-decoration:none;color:#fff;">
                {post.author_id.slice(0, 1).toUpperCase()}
              </a>
              <div class="who" style="flex:1;min-width:0;">
                <div class="name">@{post.author_id.slice(0, 8)}</div>
                <div class="sub">
                  <span>{new Date(post.created_at).toLocaleDateString('vi-VN')}</span>
                  {#if post.rank > 0}
                    <span class="chip outline" style="font-size:10px;padding:1px 6px;">điểm {post.rank.toFixed(2)}</span>
                  {/if}
                </div>
              </div>
            </div>
            <a class="post-title" href="/post/{post.id}">
              {post.content.length > 160 ? `${post.content.slice(0, 160)}…` : post.content}
            </a>
            <div class="post-meta-row" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">
              {#each post.tags.slice(0, 3) as t}
                <a href="/search?q={encodeURIComponent(t)}" class="chip outline" style="font-size:12px;">#{t}</a>
              {/each}
              {#each post.topics.slice(0, 2) as topic}
                <a href="/topic/{topic}" class="chip active" style="font-size:12px;">{TOPIC_LABELS[topic] ?? topic}</a>
              {/each}
            </div>
          </article>
        {/each}
        {#if postCursor}
          <InfiniteSentinel disabled={loading} onVisible={loadMore} />
          {#if loading}<p class="t-meta" style="text-align:center;margin-top:12px;">Đang tải thêm…</p>{/if}
        {/if}
      {/if}

    {:else}
      <!-- User search results -->
      {#if users.length === 0}
        <div class="card card-pad" style="text-align:center;padding:48px 24px;">
          <div style="font-size:32px;margin-bottom:8px;">👤</div>
          <p style="color:var(--ink-400,#94a3b8);font-size:14px;margin:0;">
            Không tìm thấy người dùng nào cho "<strong>{q}</strong>"
          </p>
        </div>
      {:else}
        <div style="display:flex;flex-direction:column;gap:8px;">
          {#each users as u (u.id)}
            <a href="/profile/{u.id}" class="card card-pad" style="display:flex;align-items:center;gap:14px;padding:14px 16px;text-decoration:none;transition:box-shadow 0.15s;"
              on:mouseenter={(e) => (e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.08)')}
              on:mouseleave={(e) => (e.currentTarget.style.boxShadow = '')}>
              <div class="avatar s40" style="background:{avatarColor(u.id)};color:#fff;flex-shrink:0;">
                {(u.display_name ?? u.username).slice(0, 1).toUpperCase()}
              </div>
              <div style="flex:1;min-width:0;">
                <div style="font-weight:700;font-size:14px;color:var(--ink-900,#0f172a);display:flex;align-items:center;gap:4px;">
                  {u.display_name ?? u.username}
                  {#if u.role === 'creator'}
                    <Icon name="Verified" size={13} />
                  {/if}
                </div>
                <div style="font-size:12px;color:var(--ink-400,#94a3b8);">@{u.username}</div>
                {#if u.bio}
                  <p style="font-size:12px;color:var(--ink-500,#6b7280);margin:4px 0 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{u.bio}</p>
                {/if}
              </div>
              {#if u.role === 'creator'}
                <span class="chip outline" style="font-size:11px;white-space:nowrap;flex-shrink:0;">Creator</span>
              {/if}
            </a>
          {/each}
        </div>
      {/if}
    {/if}

  </main>

  <!-- ── RIGHT SIDEBAR ───────────────────────────────────────────── -->
  <aside class="rail">

    <!-- Chủ đề dành cho bạn -->
    <div class="rail-card">
      <h4 style="margin:0 0 12px;display:flex;align-items:center;gap:6px;">
        <Icon name="Compass" size={16} className="pin" /> Chủ đề khám phá
      </h4>
      <div style="display:flex;flex-direction:column;gap:4px;">
        {#each topicCards.slice(0, 8) as t}
          <button
            style="display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:10px;border:none;background:transparent;cursor:pointer;text-align:left;width:100%;transition:background 0.12s;"
            on:click={() => searchTopic(t.slug)}
            on:mouseenter={(e) => (e.currentTarget.style.background = 'var(--canvas-100,#f0f9f4)')}
            on:mouseleave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <span style="width:8px;height:8px;border-radius:50%;background:{t.color};flex-shrink:0;"></span>
            <span style="flex:1;font-size:13px;color:var(--ink-700,#334155);">+ {t.label}</span>
            <span style="font-size:11px;color:{t.color};font-weight:600;">↑{t.growth}%</span>
          </button>
        {/each}
        {#if topicCards.length === 0}
          {#each Object.entries(TOPIC_LABELS).slice(0, 6) as [slug, label]}
            <button
              style="display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:10px;border:none;background:transparent;cursor:pointer;text-align:left;width:100%;transition:background 0.12s;"
              on:click={() => searchTopic(slug)}
              on:mouseenter={(e) => (e.currentTarget.style.background = 'var(--canvas-100,#f0f9f4)')}
              on:mouseleave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <span style="width:8px;height:8px;border-radius:50%;background:{TOPIC_COLORS[slug] ?? '#64748b'};flex-shrink:0;"></span>
              <span style="flex:1;font-size:13px;color:var(--ink-700,#334155);">+ {label}</span>
            </button>
          {/each}
        {/if}
      </div>
    </div>

    <!-- Nguồn tin đáng tin cậy -->
    {#if data.creators?.length}
      <div class="rail-card">
        <h4 style="margin:0 0 12px;display:flex;align-items:center;gap:6px;">
          <Icon name="Shield" size={16} className="pin" /> Nguồn tin đáng tin cậy
        </h4>
        <div style="display:flex;flex-direction:column;gap:10px;">
          {#each data.creators as creator}
            <a href="/profile/{creator.id}" style="display:flex;align-items:center;gap:10px;text-decoration:none;">
              <div class="avatar s32" style="background:{avatarColor(creator.id)};color:#fff;flex-shrink:0;width:32px;height:32px;border-radius:10px;font-size:12px;display:flex;align-items:center;justify-content:center;font-weight:700;">
                {(creator.display_name ?? creator.username).slice(0, 1).toUpperCase()}
              </div>
              <div style="flex:1;min-width:0;">
                <div style="font-size:13px;font-weight:600;color:var(--ink-900,#0f172a);display:flex;align-items:center;gap:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                  <span style="overflow:hidden;text-overflow:ellipsis;">{creator.display_name ?? creator.username}</span>
                  <Icon name="Verified" size={12} />
                </div>
                <div style="font-size:11px;color:var(--ink-400,#94a3b8);">@{creator.username}</div>
              </div>
            </a>
          {/each}
        </div>
        <a href="/search?q=&type=user" style="display:block;margin-top:12px;font-size:12px;color:var(--emerald-600,#16a34a);text-decoration:none;text-align:center;font-weight:600;">
          Xem tất cả creator →
        </a>
      </div>
    {/if}

    <!-- Thống kê hệ thống (luôn hiện) -->
    <div class="rail-card">
      <h4 style="margin:0 0 12px;display:flex;align-items:center;gap:6px;">
        <Icon name="ChartBar" size={16} className="pin" /> Thống kê nền tảng
      </h4>
      <div style="display:flex;flex-direction:column;gap:8px;">
        {#each topicCards as t}
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <span style="font-size:12px;color:var(--ink-600,#475569);display:flex;align-items:center;gap:5px;">
              <span style="width:6px;height:6px;border-radius:50%;background:{t.color};flex-shrink:0;display:inline-block;"></span>
              {t.label}
            </span>
            <span style="font-size:12px;font-weight:600;color:var(--ink-700,#334155);">{t.count} bài</span>
          </div>
        {/each}
        {#if topicCards.length === 0}
          <p style="font-size:12px;color:var(--ink-300,#cbd5e1);text-align:center;margin:8px 0;">Đang tải thống kê…</p>
        {/if}
      </div>
    </div>

  </aside>
</div>

<style>
  /* ── Filter row ─────────────────────────────────────────────────── */
  .filter-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 20px;
  }

  /* Segmented control (Bài viết / Người dùng) */
  .type-seg {
    display: inline-flex;
    background: rgba(255, 255, 255, 0.50);
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    border: 1px solid rgba(255, 255, 255, 0.65);
    border-radius: 999px;
    padding: 3px;
    gap: 2px;
    box-shadow:
      0 1px 4px rgba(0, 0, 0, 0.06),
      inset 0 1px 0 rgba(255, 255, 255, 0.85);
  }

  .type-seg button {
    padding: 6px 15px;
    border-radius: 999px;
    border: none;
    background: transparent;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-400, #94a3b8);
    cursor: pointer;
    transition: all 0.18s cubic-bezier(0.4, 0.1, 0.2, 1);
    white-space: nowrap;
  }

  .type-seg button:hover:not(.seg-active) {
    color: var(--ink-700, #334155);
    background: rgba(255, 255, 255, 0.5);
  }

  .type-seg button.seg-active {
    background: #fff;
    color: var(--ink-900, #0f172a);
    font-weight: 600;
    box-shadow:
      0 1px 5px rgba(0, 0, 0, 0.12),
      inset 0 1px 0 rgba(255, 255, 255, 0.95);
  }

  /* Thin divider between type seg and filter pills */
  .filter-divider {
    width: 1px;
    height: 20px;
    background: rgba(0, 0, 0, 0.08);
    margin: 0 2px;
    flex-shrink: 0;
  }

  /* Individual filter pills */
  .fpill {
    display: inline-flex;
    align-items: center;
    padding: 6px 14px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    background: rgba(255, 255, 255, 0.45);
    backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-500, #6b7280);
    cursor: pointer;
    transition: all 0.18s cubic-bezier(0.4, 0.1, 0.2, 1);
    box-shadow:
      0 1px 3px rgba(0, 0, 0, 0.05),
      inset 0 1px 0 rgba(255, 255, 255, 0.75);
    white-space: nowrap;
  }

  .fpill:hover:not(.fpill-active) {
    background: rgba(255, 255, 255, 0.72);
    color: var(--ink-800, #1e293b);
    box-shadow:
      0 2px 8px rgba(0, 0, 0, 0.08),
      inset 0 1px 0 rgba(255, 255, 255, 0.9);
  }

  .fpill-active {
    background: linear-gradient(150deg, rgba(0, 200, 130, 0.22), rgba(0, 166, 107, 0.12));
    border-color: rgba(0, 166, 107, 0.38);
    color: var(--emerald-700, #15803d);
    font-weight: 600;
    box-shadow:
      0 2px 8px rgba(0, 166, 107, 0.12),
      inset 0 1px 0 rgba(255, 255, 255, 0.65);
  }
</style>
