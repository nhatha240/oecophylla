<script lang="ts">
  import type { PageData } from './$types';
  import { followUser, unfollowUser } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let data: PageData;
  let q = data.q;
  let tab: 'people' | 'posts' = 'people';
  let followed: Record<string, boolean> = {};
  let busy: Record<string, boolean> = {};
  let actionError = '';
  async function toggleFollow(id: string, initial = false) {
    if (busy[id]) return;
    busy = { ...busy, [id]: true }; actionError = '';
    const on = followed[id] ?? initial;
    try { if (on) await unfollowUser(fetch, id); else await followUser(fetch, id); followed = { ...followed, [id]: !on }; }
    catch { actionError = 'Không thể cập nhật theo dõi. Vui lòng thử lại.'; }
    finally { busy = { ...busy, [id]: false }; }
  }
</script>

<svelte:head><title>Khám phá — Oecophylla</title></svelte:head>
<div class="explore-page">
  <div class="explore-hero"><p class="eyebrow">CỘNG ĐỒNG · KẾT NỐI · CÙNG PHÁT TRIỂN</p><h1 class="serif">Khám phá những góc nhìn<br />tạo nên điều tốt đẹp hơn.</h1><p>Tìm kiếm, theo dõi và đồng hành cùng những người có chung mối quan tâm.</p></div>
  <form class="explore-search" method="GET"><Icon name="Search" size={18} /><input name="q" bind:value={q} placeholder="Tìm kiếm bài viết, chủ đề hoặc người dùng..." aria-label="Từ khóa tìm kiếm" /><button class="pill-primary" type="submit">Tìm kiếm</button></form>
  <div class="explore-tabs"><button class:active={tab === 'people'} on:click={() => tab = 'people'}>Con người ({data.users.length})</button><button class:active={tab === 'posts'} on:click={() => tab = 'posts'}>Bài viết ({data.posts.length})</button></div>
  {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
  {#if tab === 'people'}
    <div class="section-heading"><h2 class="serif">{data.q ? 'Người dùng phù hợp' : 'Gợi ý người dùng'}</h2><p>Những người thú vị có thể bạn muốn kết nối.</p></div>
    {#if data.users.length}
      <div class="people-grid">{#each data.users as person}
        <article class="person-card"><a class="avatar" href={'/profile/' + person.id}>{#if person.avatar_url}<img src={person.avatar_url} alt="" />{:else}{(person.display_name ?? person.username).slice(0, 1).toUpperCase()}{/if}</a><a class="name serif" href={'/profile/' + person.id}>{person.display_name ?? person.username}</a><span class="handle">@{person.username}</span><p>{person.bio ?? 'Cùng khám phá những câu chuyện đáng suy ngẫm.'}</p><button class={followed[person.id] ?? ('is_following' in person && person.is_following) ? 'pill-outline' : 'pill-primary'} disabled={busy[person.id]} on:click={() => toggleFollow(person.id, 'is_following' in person && !!person.is_following)}>{followed[person.id] ?? ('is_following' in person && person.is_following) ? 'Đang theo dõi' : 'Theo dõi'}</button></article>
      {/each}</div>
    {:else}<p class="empty">Chưa tìm thấy người dùng phù hợp.</p>{/if}
  {:else}
    <div class="section-heading"><h2 class="serif">Bài viết</h2><p>{data.q ? 'Kết quả tìm kiếm cho “' + data.q + '”' : 'Nhập từ khóa để tìm bài viết.'}</p></div>
    {#if data.posts.length}<div class="results">{#each data.posts as post}<a class="result-card" href={'/post/' + post.id}><span class="eyebrow">{post.topics?.[0] ?? 'BÀI VIẾT'}</span><h3 class="serif">{post.content.slice(0, 150)}{post.content.length > 150 ? '…' : ''}</h3><small>{new Intl.DateTimeFormat('vi-VN').format(new Date(post.created_at))} · {post.view_count} lượt xem</small></a>{/each}</div>{:else}<p class="empty">Chưa có bài viết phù hợp.</p>{/if}
  {/if}
</div>

<style>
  .explore-page { max-width: 1150px; margin: auto; padding: 28px 35px 60px; }
  .explore-hero { min-height: 180px; padding: 27px 30px; border-radius: 10px; background: linear-gradient(90deg, #ffffff 20%, #ffffffe0 55%, #ffffff00), url('/brand/city.jpg') center 64%/cover; }
  .explore-hero h1 { margin: 12px 0 8px; font-size: clamp(27px, 3vw, 39px); line-height: 1.22; letter-spacing: -.05em; font-weight: 500; }
  .explore-hero p:last-child { max-width: 510px; margin: 0; color: #61756e; font: 13px/1.6 'Lora', serif; }
  .explore-search { display: flex; align-items: center; gap: 10px; margin: 17px 0 22px; padding: 8px 10px 8px 16px; border: 1px solid #e6eeea; border-radius: 10px; background: white; color: #4a746b; }
  .explore-search input { flex: 1; min-width: 0; border: 0; outline: 0; color: #183c36; background: transparent; font-size: 12px; }
  .explore-tabs { display: flex; gap: 8px; margin-bottom: 22px; }
  .explore-tabs button { padding: 9px 18px; border: 0; border-radius: 30px; background: #f3f6f4; color: #60736c; font-size: 12px; }
  .explore-tabs button.active { background: #1d5b54; color: white; }
  .section-heading h2 { margin: 0; font-size: 22px; font-weight: 500; }
  .section-heading p { margin: 3px 0 16px; color: #7e8d87; font: 12px 'Lora', serif; }
  .people-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; }
  .person-card { display: flex; flex-direction: column; align-items: center; padding: 22px 15px 16px; border: 1px solid #e7eeea; border-radius: 9px; background: white; text-align: center; }
  .avatar { display: grid; place-items: center; width: 72px; height: 72px; overflow: hidden; border-radius: 50%; background: #dcece5; color: #1e5b54; font: 600 31px 'Lora', serif; }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .name { margin-top: 12px; font-size: 14px; font-weight: 600; }
  .handle { margin-top: 2px; color: #8ca09a; font-size: 10px; }
  .person-card p { flex: 1; margin: 13px 0 16px; color: #6e807a; font: italic 11px/1.5 'Lora', serif; }
  .person-card button { width: 100%; }
  .results { display: grid; gap: 10px; }
  .result-card { display: block; padding: 18px 20px; border: 1px solid #e7eeea; border-radius: 9px; background: white; }
  .result-card:hover { border-color: #a4c6bb; }
  .result-card h3 { margin: 7px 0; font-size: 17px; font-weight: 500; }
  .result-card small { color: #8a9a94; }
  .empty { padding: 30px; border-radius: 9px; background: white; color: #7a8c85; font-size: 13px; }
  .error { color: #aa4343; font-size: 12px; }
  @media (max-width: 1100px) { .people-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
  @media (max-width: 720px) { .explore-page { padding: 15px 14px 28px; } .explore-hero { min-height: 170px; padding: 22px; } .explore-hero h1 { font-size: 25px; } .explore-hero h1 br { display: none; } .explore-search .pill-primary { padding: 0 13px; } }
</style>
