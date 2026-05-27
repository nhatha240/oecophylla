<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Badge from './Badges.svelte';
  import Icon from './Icon.svelte';
  import { POSTS, topicName } from '../data';

  export let onBack: () => void = () => {};
  const navs = [
    ['home', 'Trang chủ', 'Home'],
    ['expl', 'Khám phá', 'Compass'],
    ['post', 'Đăng', 'Plus'],
    ['notif', 'Thông báo', 'Bell'],
    ['me', 'Hồ sơ', 'User']
  ];
  const post = POSTS[0];
</script>

<div data-screen-label="10 Mobile" class="mobile-preview-page">
  <div class="admin-h">
    <div><h2 class="serif mobile-heading">Xem trên di động</h2><div class="sub mobile-sub">Bottom navigation với 5 mục chính. Composer mở dạng modal toàn màn hình.</div></div>
    <button class="btn ghost sm" on:click={onBack}><Icon name="ArrowLeft" size={13} /> Quay lại desktop</button>
  </div>
  <div class="phone-grid">
    <div>
      <div class="t-eyebrow phone-label">Home feed</div>
      <div class="mobile-frame">
        <div class="mobile-statusbar"><span>9:41</span><span>●●●● 5G ▮▮▮▯</span></div>
        <div class="mobile-content">
          <div class="phone-scroll">
            {@render PhoneTop()}
            <div class="phone-tabs">{#each ['Dành cho bạn','Đang theo dõi','Tin mới','Xu hướng','Đã lưu'] as item, i}<button class:active={i === 0}>{item}</button>{/each}</div>
            <div class="phone-cards">{#each POSTS.slice(0, 3) as p}<article class="card phone-card"><div class="phone-author"><Avatar author={p.author} size="s32" showVerified /><div><div class="phone-name">{p.author.name}</div><div class="t-meta">{p.time} · {topicName(p.tags[0])}</div></div><Badge kind={p.moderation} label={p.moderationLabel} /></div><div class="phone-title">{p.title}</div><div class="phone-summary">{p.summary}</div>{#if p.image}<div class="ph-img phone-img">ẢNH</div>{/if}<div class="recommend-line"><Icon name="Sparkle" size={11} /> {p.reason}</div></article>{/each}</div>
          </div>
          {@render BottomNav()}
        </div>
      </div>
    </div>
    <div>
      <div class="t-eyebrow phone-label">Trang chi tiết bài viết</div>
      <div class="mobile-frame">
        <div class="mobile-statusbar"><span>9:41</span><span>●●●● 5G ▮▮▮▯</span></div>
        <div class="mobile-content">
          <div class="phone-scroll">
            <div class="phone-top"><button class="icon-btn"><Icon name="ArrowLeft" size={16} /></button><div class="phone-titlebar">Bài viết</div><button class="icon-btn"><Icon name="Bookmark" size={16} /></button><button class="icon-btn"><Icon name="Share" size={16} /></button></div>
            <div class="phone-article"><div style="display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap"><Badge kind="verified-src" label="Nguồn đáng tin cậy" /><span class="t-meta"><Icon name="Clock" size={11} /> 8 phút đọc</span></div><h1>{post.title}</h1><p>{post.summary}</p><div class="phone-author article-author"><Avatar author={post.author} size="s40" showVerified /><div><div class="phone-name">{post.author.name}</div><div class="t-meta">{post.author.handle} · {post.time}</div></div><button class="btn emerald sm">Theo dõi</button></div><div class="ph-img phone-hero">ẢNH MINH HỌA</div><p class="article-body">Trong sáu tháng qua, nhóm đánh giá độc lập của Đại học Bách khoa Hà Nội đã thử nghiệm 12 mô hình ngôn ngữ lớn phổ biến với một bộ dữ liệu kiểm thử riêng…</p></div>
          </div>
          {@render BottomNav()}
        </div>
      </div>
    </div>
  </div>
</div>

{#snippet PhoneTop()}
  <div class="phone-top"><div class="brand-mark phone-mark">O</div><div class="phone-brand">Oecophy<em>lla</em></div><button class="icon-btn"><Icon name="Search" size={16} /></button><button class="icon-btn"><Icon name="Bell" size={16} /><span class="dot"></span></button></div>
{/snippet}

{#snippet BottomNav()}
  <div class="mobile-bottomnav">{#each navs as nav}<button class={`mb-item ${nav[0] === 'home' ? 'active' : ''}`}>{#if nav[0] === 'post'}<div class="mb-post"><Icon name={nav[2]} size={16} /></div>{:else}<Icon name={nav[2]} size={18} /><span>{nav[1]}</span>{/if}</button>{/each}</div>
{/snippet}

<style>
  .mobile-preview-page { padding: 40px 32px 80px; max-width: 1100px; margin: 0 auto; }
  .mobile-heading { font-weight: 500; font-size: 28px; letter-spacing: -0.015em; margin: 0; }
  .mobile-sub { color: var(--muted); font-size: 13px; margin-top: 4px; }
  .phone-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 32px; justify-items: center; margin-top: 24px; }
  .phone-label { text-align: center; margin-bottom: 14px; }
  .phone-scroll { height: 100%; overflow: auto; background: var(--paper); padding-bottom: 74px; }
  .phone-top { padding: 12px 18px; background: var(--paper); display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--hairline); position: sticky; top: 0; z-index: 2; }
  .phone-mark { width: 26px; height: 26px; border-radius: 8px; font-size: 16px; }
  .phone-brand { font: 500 17px var(--font-serif); letter-spacing: -0.01em; margin-right: auto; }
  .phone-brand em { font-style: normal; color: var(--emerald-500); }
  .phone-tabs { display: flex; gap: 4px; padding: 8px 14px; overflow-x: auto; border-bottom: 1px solid var(--hairline); }
  .phone-tabs button { font: 600 12px var(--font-ui); color: var(--ink-2); background: var(--surface-2); border: 0; padding: 7px 12px; border-radius: 99px; white-space: nowrap; }
  .phone-tabs .active { color: var(--paper); background: var(--ink); }
  .phone-cards { padding: 14px; display: flex; flex-direction: column; gap: 12px; }
  .phone-card { padding: 16px; }
  .phone-author { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .phone-name { font-weight: 600; font-size: 13px; }
  .phone-title { font: 500 16px/1.25 var(--font-serif); letter-spacing: -0.01em; margin-bottom: 6px; }
  .phone-summary { font-size: 12.5px; color: var(--ink-2); line-height: 1.45; margin-bottom: 10px; display: -webkit-box; line-clamp: 2; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .phone-img { aspect-ratio: 16/9; border-radius: 10px; margin-bottom: 10px; }
  .phone-titlebar { flex: 1; font: 500 13px var(--font-ui); text-align: center; }
  .phone-article { padding: 20px 20px 40px; }
  .phone-article h1 { font: 500 24px/1.15 var(--font-serif); letter-spacing: -0.02em; margin: 0 0 10px; }
  .phone-article p { font: italic 500 14px/1.45 var(--font-serif); color: var(--muted); margin: 0 0 16px; }
  .article-author { padding: 12px 0; border-top: 1px solid var(--hairline); border-bottom: 1px solid var(--hairline); }
  .phone-hero { aspect-ratio: 16/9; border-radius: 10px; margin: 16px 0; }
  .phone-article .article-body { font: 15px/1.6 var(--font-serif); color: var(--ink-2); }
</style>
