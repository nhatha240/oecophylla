<script lang="ts">
  import type { PageData } from './$types';
  import { apiFetch } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let data: PageData;
  let items = data.saved.items;
  let error = '';
  async function remove(id: string) {
    try { await apiFetch(fetch, '/posts/' + id + '/save', { method: 'DELETE' }); items = items.filter((post) => post.id !== id); }
    catch { error = 'Chưa thể bỏ lưu bài viết. Vui lòng thử lại.'; }
  }
</script>
<svelte:head><title>Bài đã lưu — Oecophylla</title></svelte:head>
<section class="saved-page"><p class="eyebrow">THƯ VIỆN CỦA BẠN</p><h1 class="serif">Bài viết đã lưu</h1><p class="intro">Lưu lại những câu chuyện đáng suy ngẫm để đọc lại khi bạn muốn.</p>{#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if items.length}<div class="saved-list">{#each items as post}<article><div><p class="eyebrow">{post.topics?.[0] ?? post.tags?.[0] ?? 'BÀI VIẾT'}</p><a class="serif" href={'/post/' + post.id}>{post.content.slice(0, 160)}{post.content.length > 160 ? '…' : ''}</a><p class="byline">{post.display_name ?? post.username} · {new Intl.DateTimeFormat('vi-VN').format(new Date(post.created_at))}</p></div>{#if post.media_urls?.[0]}<img src={post.media_urls[0]} alt="Ảnh bài viết" loading="lazy" />{/if}<button type="button" aria-label="Bỏ lưu" on:click={() => remove(post.id)}><Icon name="BookmarkFill" size={18} /></button></article>{/each}</div>{:else}<div class="empty"><Icon name="Bookmark" size={28} /><h2 class="serif">Chưa có bài viết đã lưu</h2><p>Khám phá bảng tin và lưu những nội dung bạn muốn đọc lại.</p><a class="pill-primary" href="/">Đến bảng tin</a></div>{/if}
</section>
<style>
  .saved-page { max-width: 920px; margin: auto; padding: 35px 32px 60px; }
  h1 { margin: 9px 0; font-size: 35px; font-weight: 500; letter-spacing: -.05em; }
  .intro { margin: 0 0 26px; color: #71857b; font: 13px 'Lora', serif; }
  .saved-list { display: grid; gap: 11px; }
  article { display: flex; align-items: center; gap: 18px; padding: 19px; border: 1px solid #e7eeea; border-radius: 9px; background: white; }
  article > div { flex: 1; }
  article .eyebrow { margin: 0 0 7px; }
  article a.serif { display: block; font-size: 17px; line-height: 1.4; }
  article a:hover { color: #1e655b; }
  .byline { margin: 10px 0 0; color: #8a9b92; font-size: 10px; }
  article img { width: 100px; height: 76px; object-fit: cover; border-radius: 5px; }
  article button { border: 0; background: transparent; color: #1d5b54; }
  .empty { display: grid; justify-items: center; gap: 12px; padding: 65px 20px; border: 1px solid #e7eeea; border-radius: 10px; background: white; text-align: center; color: #4b796e; }
  .empty h2, .empty p { margin: 0; }
  .empty h2 { color: #234139; font-size: 22px; font-weight: 500; }
  .empty p { color: #7d8e85; font-size: 12px; }
  .error { color: #ad4246; font-size: 12px; }
  @media (max-width: 720px) { .saved-page { padding: 23px 14px 35px; } article { padding: 15px; } article img { display: none; } h1 { font-size: 28px; } }
</style>
