<script lang="ts">
  import Avatar from './Avatar.svelte';
  import FollowSuggestion from './FollowSuggestion.svelte';
  import Icon from './Icon.svelte';
  import PostCard from './PostCard.svelte';
  import { AUTHORS, POSTS, SUGGEST_FOLLOW, TASTE, TRENDING, type Post } from '../data';

  export let onOpenPost: (post: Post) => void = () => {};
  export let toast: (message: string) => void = () => {};

  let tab = 'for-you';
  let composer = '';
  let composerOpen = false;
  let liked = new Set<string>(['p3']);
  let saved = new Set<string>(['p4']);

  const tabs = [
    { id: 'for-you', name: 'Dành cho bạn', icon: 'Sparkle' },
    { id: 'follow', name: 'Đang theo dõi', icon: 'Users' },
    { id: 'new', name: 'Tin mới', icon: 'Clock' },
    { id: 'trend', name: 'Xu hướng', icon: 'Flame' },
    { id: 'saved', name: 'Đã lưu', icon: 'Bookmark' }
  ];

  $: sensitive = /chính trị|tin giả|fake/i.test(composer);
  $: posts =
    tab === 'saved'
      ? POSTS.filter((post) => saved.has(post.id))
      : tab === 'new'
        ? [...POSTS].reverse()
        : tab === 'trend'
          ? [...POSTS].sort((a, b) => b.stats.shares - a.stats.shares)
          : POSTS;

  function toggleLike(id: string) {
    liked = new Set(liked);
    if (liked.has(id)) liked.delete(id);
    else {
      liked.add(id);
      toast('Đã thêm vào bài bạn thích.');
    }
  }

  function toggleSave(id: string) {
    saved = new Set(saved);
    if (saved.has(id)) {
      saved.delete(id);
      toast('Đã bỏ lưu.');
    } else {
      saved.add(id);
      toast('Đã lưu vào bộ sưu tập của bạn.');
    }
  }
</script>

<div class="feed-grid" data-screen-label="04 Home Feed">
  <main class="feed-main">
    <div class="composer">
      <Avatar author={AUTHORS[0]} size="s40" />
      <div class="right">
        <textarea
          placeholder="Bạn muốn chia sẻ tin tức hoặc góc nhìn gì hôm nay?"
          rows={composerOpen || composer ? 3 : 1}
          bind:value={composer}
          on:focus={() => (composerOpen = true)}
        ></textarea>
        {#if (composerOpen || composer) && composer.length > 12}
          <div class="composer-suggest">
            <span class="t-meta" style="margin-right: 4px; align-self: center">Gợi ý chủ đề:</span>
            <span class="chip outline">#Công nghệ</span>
            <span class="chip outline">#AI</span>
            <span class="chip outline">#Báo chí số</span>
            <span class="chip"><Icon name="Plus" size={11} /> Thêm</span>
          </div>
        {/if}
        {#if sensitive}
          <div class="sensitive-hint">
            <Icon name="AlertTriangle" size={14} style="margin-top: 2px" />
            <div>
              <b style="display: block; margin-bottom: 2px">Nội dung này có thể cần kiểm duyệt trước khi hiển thị công khai.</b>
              Hãy đảm bảo bạn dẫn nguồn rõ ràng và tránh ngôn từ kích động. Đây chỉ là gợi ý, bài viết vẫn được lưu.
            </div>
          </div>
        {/if}
        <div class="composer-foot">
          <div class="composer-actions">
            <button class="icon-btn" title="Thêm ảnh"><Icon name="Image" size={16} /></button>
            <button class="icon-btn" title="Thêm liên kết"><Icon name="Link" size={16} /></button>
            <button class="icon-btn" title="Thêm chủ đề"><Icon name="Tag" size={16} /></button>
            <button class="icon-btn" title="Đăng vào nhóm"><Icon name="Group" size={16} /></button>
          </div>
          <span class="t-meta" style="margin-left: auto">{composer.length > 0 ? `${composer.length} ký tự` : 'Hiển thị công khai · có kiểm duyệt'}</span>
          <button class="btn emerald sm" disabled={!composer.trim()}>Đăng <Icon name="Send" size={12} /></button>
        </div>
      </div>
    </div>

    <div class="tabs">
      {#each tabs as item}
        <button class={`tab ${tab === item.id ? 'active' : ''}`} on:click={() => (tab = item.id)}>
          <Icon name={item.icon} size={14} /> {item.name}
          {#if item.id === 'saved'}<span class="count-mini">{saved.size}</span>{/if}
        </button>
      {/each}
      <span style="margin-left: auto; display: inline-flex; align-items: center; gap: 4px; padding: 0 8px; color: var(--muted)">
        <Icon name="Refresh" size={13} />
        <span class="t-meta">Cập nhật 12 giây trước</span>
      </span>
    </div>

    {#if tab === 'saved' && posts.length === 0}
      <div class="card card-pad" style="text-align: center; padding: 48px 24px">
        <Icon name="Bookmark" size={28} className="muted" />
        <h4 class="serif" style="margin: 12px 0 4px; font-size: 18px; font-weight: 500">Chưa có bài viết nào được lưu</h4>
        <p class="muted" style="margin: 0">Lưu bài để đọc lại sau, dù khi không có mạng.</p>
      </div>
    {/if}

    {#each posts as post (post.id)}
      <PostCard
        {post}
        liked={liked.has(post.id)}
        saved={saved.has(post.id)}
        onLike={() => toggleLike(post.id)}
        onSave={() => toggleSave(post.id)}
        onOpen={() => onOpenPost(post)}
      />
    {/each}

    {#if tab !== 'saved'}
      <button class="btn ghost" style="width: 100%; justify-content: center; margin-top: 8px"><Icon name="Plus" size={14} /> Xem thêm bài</button>
    {/if}
  </main>

  <aside class="rail">
    <div class="rail-card">
      <h4><Icon name="Flame" size={16} className="pin" /> Đang thịnh hành</h4>
      {#each TRENDING as trend, i}
        <div class="trend-item">
          <span class="trend-num">{i + 1}</span>
          <div>
            <div class="trend-title">#{trend.tag}</div>
            <div class="trend-meta">
              <span>{trend.topic}</span><span>·</span><span>{trend.posts} bài</span>
              <span style="color: var(--emerald-500); font-weight: 600">{trend.delta}</span>
            </div>
          </div>
        </div>
      {/each}
    </div>

    <div class="rail-card">
      <h4><Icon name="Users" size={16} className="pin" /> Có thể bạn thích</h4>
      {#each SUGGEST_FOLLOW as author (author.id)}
        <FollowSuggestion {author} />
      {/each}
      <button class="btn ghost sm" style="width: 100%; margin-top: 12px">Xem thêm gợi ý</button>
    </div>

    <div class="rail-card">
      <h4><Icon name="ChartBar" size={16} className="pin" /> Sở thích đọc của bạn</h4>
      <p class="t-meta" style="margin: -6px 0 14px">Dựa trên 30 ngày đọc gần nhất.</p>
      <div class="taste-bars">
        {#each TASTE as taste}
          <div class="taste-bar">
            <div class="taste-bar-head"><span>{taste.topic}</span><span class="pct">{taste.pct}%</span></div>
            <div class="taste-bar-track"><div class="taste-bar-fill" style={`width: ${taste.pct}%`}></div></div>
          </div>
        {/each}
      </div>
      <button class="btn ghost sm" style="width: 100%; margin-top: 14px"><Icon name="Settings" size={12} /> Tinh chỉnh sở thích</button>
    </div>

    <div class="t-meta" style="text-align: center; line-height: 1.7">
      <a href="/">Điều khoản</a> · <a href="/">Bảo mật</a> · <a href="/">Cookie</a> · <a href="/">Trợ giúp</a><br />
      © 2026 Oecophylla
    </div>
  </aside>
</div>
