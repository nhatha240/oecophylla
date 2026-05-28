<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto, invalidateAll } from '$app/navigation';
  import type { PageData } from './$types';
  import type { SearchPost, Profile } from '$lib/types';
  import { searchPosts, searchUsers } from '$lib/api';
  import PostCard from '$lib/components/PostCard.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  export let data: PageData;

  let q = data.q;
  let activeType: 'post' | 'user' = (data.type as 'post' | 'user') ?? 'post';
  let posts: SearchPost[] = data.posts?.items ?? [];
  let postCursor: string | null = data.posts?.next_cursor ?? null;
  let users: Profile[] = data.users?.items ?? [];
  let loading = false;
  let debounceTimer: ReturnType<typeof setTimeout>;

  $: currentQ = $page.url.searchParams.get('q') ?? '';
  $: currentType = ($page.url.searchParams.get('type') ?? 'post') as 'post' | 'user';

  $: if (currentQ !== q) {
    q = currentQ;
  }
  $: if (currentType !== activeType) {
    activeType = currentType;
  }

  function onInput() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const params = new URLSearchParams($page.url.searchParams);
      params.set('q', q);
      params.set('type', activeType);
      goto(`/search?${params}`, { replaceState: true, keepFocus: true });
    }, 300);
  }

  async function switchType(t: 'post' | 'user') {
    const params = new URLSearchParams();
    if (q.trim()) params.set('q', q.trim());
    params.set('type', t);
    await goto(`/search?${params}`, { keepFocus: true, noScroll: true });
    await invalidateAll();
  }

  async function loadMore() {
    if (loading || !postCursor || activeType !== 'post') return;
    loading = true;
    try {
      const next = await searchPosts(fetch, currentQ, postCursor);
      const seen = new Set(posts.map((p) => p.id));
      const fresh = next.items.filter((p) => !seen.has(p.id));
      if (fresh.length) posts = [...posts, ...fresh];
      postCursor = next.next_cursor;
    } catch {
      /* silent */
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Tìm kiếm — Oecophylla</title>
</svelte:head>

<div class="feed-grid">
  <main class="feed-main">
    <div class="glass-surface rounded-2xl p-4 mb-4">
      <div class="flex items-center gap-3">
        <span class="text-slate-400"><Icon name="Search" size={18} /></span>
        <input
          type="text"
          bind:value={q}
          on:input={onInput}
          placeholder="Tìm bài viết, tác giả, chủ đề…"
          class="w-full bg-transparent outline-none text-slate-800 placeholder:text-slate-400"
        />
      </div>
    </div>

    <div class="flex gap-2 mb-4">
      <button
        class="glass-chip text-sm cursor-pointer"
        class:bg-slate-800={activeType === 'post'}
        class:text-white={activeType === 'post'}
        on:click={() => switchType('post')}
      >
        Bài viết
      </button>
      <button
        class="glass-chip text-sm cursor-pointer"
        class:bg-slate-800={activeType === 'user'}
        class:text-white={activeType === 'user'}
        on:click={() => switchType('user')}
      >
        Người dùng
      </button>
    </div>

    {#if !currentQ.trim()}
      <div class="card card-pad text-center py-12">
        <p class="text-slate-400">Nhập từ khoá để tìm kiếm</p>
      </div>
    {:else if activeType === 'post'}
      {#if posts.length === 0}
        <div class="card card-pad text-center py-12">
          <p class="text-slate-500">Không tìm thấy kết quả</p>
        </div>
      {:else}
        <ul class="flex flex-col gap-3">
          {#each posts as post (post.id)}
            <li>
              <article class="post">
                <div class="post-head">
                  <div class="avatar s40">
                    {post.author_id.slice(0, 1).toUpperCase()}
                  </div>
                  <div class="who">
                    <div class="name">@{post.author_id.slice(0, 8)}</div>
                    <div class="sub">
                      <span>{new Date(post.created_at).toLocaleString('vi-VN')}</span>
                      {#if post.rank > 0}
                        <span class="glass-chip text-xs ml-2">điểm {post.rank.toFixed(2)}</span>
                      {/if}
                    </div>
                  </div>
                </div>
                <a class="post-title" href={`/post/${post.id}`}>
                  {post.content.length > 140 ? `${post.content.slice(0, 140)}…` : post.content}
                </a>
                <div class="post-meta-row">
                  {#each post.tags as t}
                    <span class="chip outline">#{t}</span>
                  {/each}
                  {#each post.topics.slice(0, 2) as topic}
                    <span class="chip active">{topic}</span>
                  {/each}
                </div>
              </article>
            </li>
          {/each}
        </ul>
        {#if postCursor}
          <InfiniteSentinel disabled={loading} onVisible={loadMore} />
          {#if loading}
            <p class="t-meta text-center mt-3">Đang tải thêm…</p>
          {/if}
        {/if}
      {/if}
    {:else}
      {#if users.length === 0}
        <div class="card card-pad text-center py-12">
          <p class="text-slate-500">Không tìm thấy kết quả</p>
        </div>
      {:else}
        <ul class="flex flex-col gap-3">
          {#each users as user (user.id)}
            <li>
              <a href={`/profile/${user.id}`} class="glass-surface rounded-2xl p-4 flex items-center gap-4 hover:shadow-lg transition-shadow">
                {#if user.avatar_url}
                  <img
                    src={user.avatar_url}
                    alt={user.display_name ?? user.username}
                    class="avatar s48"
                    on:error={(e) => {
                      const el = e.currentTarget as HTMLImageElement;
                      el.style.display = 'none';
                      const fallback = el.nextElementSibling as HTMLElement;
                      if (fallback) fallback.style.display = 'flex';
                    }}
                  />
                  <div class="avatar s48" style="display:none">
                    {(user.display_name ?? user.username).slice(0, 1).toUpperCase()}
                  </div>
                {:else}
                  <div class="avatar s48">
                    {(user.display_name ?? user.username).slice(0, 1).toUpperCase()}
                  </div>
                {/if}
                <div class="flex-1 min-w-0">
                  <div class="font-semibold text-slate-800 truncate">
                    {user.display_name ?? user.username}
                  </div>
                  <div class="text-sm text-slate-400 truncate">@{user.username}</div>
                  {#if user.bio}
                    <p class="text-sm text-slate-500 mt-1 truncate">{user.bio}</p>
                  {/if}
                </div>
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  </main>

  <aside class="rail">
    <div class="rail-card">
      <h4><Icon name="Compass" size={16} className="pin" /> Gợi ý tìm kiếm</h4>
      <p class="text-sm text-slate-500 mt-2">Thử tìm theo tên người dùng, chủ đề, hoặc nội dung bài viết.</p>
    </div>
  </aside>
</div>
