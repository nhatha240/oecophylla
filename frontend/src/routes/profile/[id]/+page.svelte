<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
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

<div class="profile-page">
  <div class="profile-cover"></div>
  <div class="profile-head">
    <div class="avatar s120">{(data.profile.display_name ?? data.profile.username).slice(0, 1).toUpperCase()}</div>
    <div class="profile-meta">
      <h2>
        {data.profile.display_name ?? data.profile.username}
        <Icon name="Verified" size={18} style="color: var(--azure-500)" />
      </h2>
      <div class="handle">@{data.profile.username} · tham gia từ {new Date(data.profile.created_at).toLocaleDateString('vi-VN')}</div>
      <p class="bio">{data.profile.bio ?? 'Người dùng Oecophylla đang xây dựng hồ sơ đọc tin và dấu chân thảo luận của mình.'}</p>
      <div class="chips">
        {#each data.profile.topic_prefs.slice(0, 4) as topic}
          <span class="chip active">{topic}</span>
        {/each}
      </div>
      <div class="profile-stats">
        <div><b>{data.posts.length}</b> <span>bài viết</span></div>
        <div><b>{data.posts.reduce((sum, post) => sum + post.comment_count, 0)}</b> <span>bình luận nhận được</span></div>
        <div><b>{data.posts.reduce((sum, post) => sum + post.like_count, 0)}</b> <span>lượt thích</span></div>
      </div>
    </div>
    <div class="profile-head-actions">
      {#if $user && $user.id !== data.profile.id}
        <button class={`btn ${following ? 'ghost' : 'emerald'}`} on:click={toggleFollow}>
          {following ? 'Đang theo dõi' : '+ Theo dõi'}
        </button>
      {/if}
    </div>
  </div>

  <div class="profile-grid">
    <div>
      <div class="tabs">
        <button class="tab active">Bài viết <span class="count-mini">{data.posts.length}</span></button>
      </div>
      {#each data.posts as p (p.id)}<PostCard post={p} />{/each}
      {#if data.posts.length === 0}<p class="muted">Chưa có bài viết.</p>{/if}
    </div>

    <aside class="profile-aside">
      <div class="taste-card">
        <h4>Hồ sơ sở thích</h4>
        <p class="hint">Các chủ đề được đồng bộ từ hồ sơ người dùng hiện tại.</p>
        <div class="chips">
          {#each data.profile.topic_prefs as topic}
            <span class="chip outline">{topic}</span>
          {/each}
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .chips {
    display: flex;
    gap: 6px;
    margin-top: 10px;
    flex-wrap: wrap;
  }
</style>
