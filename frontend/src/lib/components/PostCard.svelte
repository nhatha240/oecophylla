<script lang="ts">
  import type { Post, MyInteractions } from '$lib/types';
  import PostActionBar from './PostActionBar.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  export let post: Post;
  export let me: MyInteractions | null = null;

  // Author info — FeedItem extends Post with these fields
  $: authorName =
    ('display_name' in post && (post as any).display_name) ||
    ('username' in post && (post as any).username) ||
    'Người dùng';
  $: authorHandle =
    ('username' in post && (post as any).username) ||
    post.author_id.slice(0, 8);
  $: isCreator = ('role' in post && (post as any).role === 'creator') ||
                 ('author_role' in post && (post as any).author_role === 'creator');
  $: isTrusted = post.safety_score >= 0.8;

  // Initials for avatar
  $: initials = authorName.slice(0, 2).toUpperCase();

  // Deterministic avatar color from author_id
  const COLORS = ['#22c55e','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#ec4899','#14b8a6'];
  $: avatarColor = COLORS[parseInt(post.author_id.replace(/-/g,'').slice(0,8), 16) % COLORS.length];

  // Relative time
  function relTime(iso: string): string {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return 'vừa xong';
    if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} ngày trước`;
    return new Date(iso).toLocaleDateString('vi-VN');
  }

  // Split content into title + excerpt
  $: lines = post.content.split('\n').filter(Boolean);
  $: titleText = lines[0] ?? post.content;
  $: excerptText = lines.length > 1 ? lines.slice(1).join(' ') : '';

  // Topics display labels
  const topicLabels: Record<string, string> = {
    tech: 'Công nghệ', science: 'Khoa học', sports: 'Thể thao',
    politics: 'Chính trị', entertainment: 'Giải trí', health: 'Sức khoẻ',
    business: 'Kinh doanh', culture: 'Văn hoá', education: 'Giáo dục',
    environment: 'Môi trường', ai: 'AI & Học máy', news: 'Tin tức',
  };

  // Recommendation reason from rank
  $: rankReason = ('rank' in post && (post as any).rank?.reason) ? (post as any).rank.reason : '';
  $: rankTopics = post.topics?.slice(0, 2).map(t => topicLabels[t] ?? t).join(' và ') ?? '';

  // Format view count
  function fmtNum(n: number): string {
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return String(n);
  }

  // Has media
  $: hasMedia = post.media_urls?.length > 0;
</script>

<article class="post">
  <!-- Header: avatar + author + badges + menu -->
  <div class="post-head">
    <a href="/profile/{post.author_id}" class="avatar s40" style="background:{avatarColor};text-decoration:none;color:#fff;">
      {initials}
    </a>
    <div class="who" style="flex:1;min-width:0;">
      <div class="name" style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
        <a href="/profile/{post.author_id}" style="text-decoration:none;color:inherit;">{authorName}</a>
        {#if isCreator}
          <span title="Creator được xác minh" style="color:var(--emerald-500);display:inline-flex;align-items:center;">
            <Icon name="Verified" size={14} />
          </span>
        {/if}
      </div>
      <div class="sub">
        <span>@{authorHandle}</span>
        <span>·</span>
        <span>{relTime(post.created_at)}</span>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
      {#if isTrusted}
        <span class="chip outline" style="font-size:11px;padding:2px 8px;display:flex;align-items:center;gap:3px;white-space:nowrap;">
          <Icon name="Shield" size={11} />
          Nguồn đáng tin cậy
        </span>
      {/if}
      <a href="/post/{post.id}" class="icon-btn" title="Xem chi tiết" style="opacity:0.5;">
        <Icon name="More" size={16} />
      </a>
    </div>
  </div>

  <!-- Title -->
  <a class="post-title" href="/post/{post.id}">
    {titleText.length > 160 ? `${titleText.slice(0, 160)}…` : titleText}
  </a>

  <!-- Excerpt -->
  {#if excerptText}
    <p class="post-summary">{excerptText.length > 200 ? `${excerptText.slice(0, 200)}…` : excerptText}</p>
  {/if}

  <!-- Cover image or placeholder -->
  {#if hasMedia}
    <a href="/post/{post.id}" class="post-cover" style="display:block;margin:10px 0;border-radius:10px;overflow:hidden;aspect-ratio:16/9;">
      <img src={post.media_urls[0]} alt="cover" style="width:100%;height:100%;object-fit:cover;" loading="lazy" />
    </a>
  {:else if post.topics?.length}
    <!-- Subtle topic-themed cover placeholder (only for posts with topics) -->
    <!-- omit heavy placeholder, use spacing only -->
  {/if}

  <!-- Tags + Topics chips row + view count -->
  <div class="post-meta-row" style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-top:8px;">
    {#each post.tags.slice(0, 3) as t}
      <a href="/search?q={encodeURIComponent(t)}" class="chip outline" style="font-size:12px;">#{t}</a>
    {/each}
    {#each (post.topics ?? []).slice(0, 2) as topic}
      <a href="/topic/{topic}" class="chip active" style="font-size:12px;">{topicLabels[topic] ?? topic}</a>
    {/each}
    {#if post.view_count > 0}
      <span class="t-meta" style="margin-left:auto;display:flex;align-items:center;gap:4px;white-space:nowrap;font-size:12px;">
        <Icon name="Eye" size={12} />
        {fmtNum(post.view_count)} lượt đọc
      </span>
    {/if}
  </div>

  <!-- Recommendation reason -->
  {#if rankReason || rankTopics}
    <div style="margin-top:8px;padding:8px 10px;background:var(--canvas-100,#f0f9f4);border-radius:8px;font-size:12px;color:var(--ink-500,#6b7280);display:flex;align-items:center;gap:6px;">
      <Icon name="Sparkle" size={12} />
      <span>Được đề xuất vì bạn quan tâm đến {rankTopics || rankReason}.</span>
    </div>
  {/if}

  <PostActionBar {post} {me} />
</article>
