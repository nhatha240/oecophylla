<script lang="ts">
  import PostCard from '$lib/components/PostCard.svelte';
  import { user } from '$lib/stores/auth';
  import { ApiException, apiFetch } from '$lib/api';
  export let data: { profile: import('$lib/types').Profile; posts: import('$lib/types').Post[] };
  let following = false;
  async function toggleFollow() {
    try {
      if (following) await apiFetch(fetch, `/users/${data.profile.id}/follow`, { method: 'DELETE' });
      else           await apiFetch(fetch, `/users/${data.profile.id}/follow`, { method: 'POST' });
      following = !following;
    } catch (e) { if (e instanceof ApiException && e.status === 400) alert('Không thể follow chính mình'); }
  }
</script>

<section class="glass-surface p-6 mb-4">
  <h1 class="text-display-serif text-3xl">{data.profile.display_name ?? data.profile.username}</h1>
  <p class="text-mono-meta">@{data.profile.username} · từ {new Date(data.profile.created_at).toLocaleDateString('vi-VN')}</p>
  {#if data.profile.bio}<p class="mt-2">{data.profile.bio}</p>{/if}
  {#if $user && $user.id !== data.profile.id}
    <button class="glass-pill mt-3" on:click={toggleFollow}>{following ? 'Đang theo dõi' : 'Theo dõi'}</button>
  {/if}
</section>

{#each data.posts as p (p.id)}<PostCard post={p} />{/each}
{#if data.posts.length === 0}<p class="text-ink-500">Chưa có bài viết.</p>{/if}
