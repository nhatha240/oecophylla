<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import PostCard from '$lib/components/PostCard.svelte';
  import { user } from '$lib/stores/auth';
  import { ApiException, apiFetch } from '$lib/api';
  import { showToast } from '$lib/stores/toast';
  import type { Profile } from '$lib/types';

  export let data: { profile: Profile; posts: import('$lib/types').Post[] };

  const ALL_TOPICS = ['tech', 'science', 'sports', 'politics', 'entertainment', 'health', 'business', 'culture', 'education', 'environment'];

  let following = data.profile.is_following ?? false;
  let activeTab: 'posts' | 'followers' | 'following' = 'posts';
  let followers: Profile[] = [];
  let followingList: Profile[] = [];
  let followersLoaded = false;
  let followingLoaded = false;
  let loadingTab = false;

  // Edit profile state
  let editing = false;
  let editDisplayName = '';
  let editBio = '';
  let editAvatarUrl = '';
  let editTopicPrefs: string[] = [];
  let saving = false;

  $: isOwner = $user && $user.id === data.profile.id;

  async function toggleFollow() {
    try {
      if (following) await apiFetch(fetch, `/users/${data.profile.id}/follow`, { method: 'DELETE' });
      else           await apiFetch(fetch, `/users/${data.profile.id}/follow`, { method: 'POST' });
      following = !following;
    } catch (e) {
      if (e instanceof ApiException && e.status === 400) showToast('Không thể theo dõi chính mình.');
      else showToast('Không cập nhật được trạng thái theo dõi.');
    }
  }

  async function switchTab(tab: 'posts' | 'followers' | 'following') {
    activeTab = tab;
    if (tab === 'followers' && !followersLoaded) {
      loadingTab = true;
      try {
        followers = await apiFetch<Profile[]>(fetch, `/users/${data.profile.id}/followers?limit=50`);
        followersLoaded = true;
      } catch {
        showToast('Không thể tải danh sách người theo dõi.');
      } finally {
        loadingTab = false;
      }
    } else if (tab === 'following' && !followingLoaded) {
      loadingTab = true;
      try {
        followingList = await apiFetch<Profile[]>(fetch, `/users/${data.profile.id}/following?limit=50`);
        followingLoaded = true;
      } catch {
        showToast('Không thể tải danh sách đang theo dõi.');
      } finally {
        loadingTab = false;
      }
    }
  }

  function startEdit() {
    editDisplayName = data.profile.display_name ?? '';
    editBio = data.profile.bio ?? '';
    editAvatarUrl = data.profile.avatar_url ?? '';
    editTopicPrefs = [...data.profile.topic_prefs];
    editing = true;
  }

  function cancelEdit() {
    editing = false;
  }

  function toggleTopic(topic: string) {
    if (editTopicPrefs.includes(topic)) {
      editTopicPrefs = editTopicPrefs.filter(t => t !== topic);
    } else {
      editTopicPrefs = [...editTopicPrefs, topic];
    }
  }

  async function saveProfile() {
    saving = true;
    try {
      const updated = await apiFetch<Profile>(fetch, `/users/${data.profile.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          display_name: editDisplayName || null,
          bio: editBio || null,
          avatar_url: editAvatarUrl || null,
          topic_prefs: editTopicPrefs,
        }),
      });
      data.profile = { ...data.profile, ...updated };
      editing = false;
      showToast('Đã cập nhật hồ sơ.');
    } catch {
      showToast('Không thể cập nhật hồ sơ.');
    } finally {
      saving = false;
    }
  }

  function handleAvatarError(e: Event) {
    (e.target as HTMLImageElement).style.display = 'none';
    const fallback = (e.target as HTMLImageElement).nextElementSibling as HTMLElement;
    if (fallback) fallback.style.display = 'flex';
  }
</script>

<div class="profile-page">
  <div class="profile-cover"></div>
  <div class="profile-head">
    <div class="avatar s120">
      {#if data.profile.avatar_url}
        <img
          src={data.profile.avatar_url}
          alt={data.profile.display_name ?? data.profile.username}
          class="avatar-img"
          on:error={handleAvatarError}
        />
      {/if}
      <span class="avatar-fallback" style={data.profile.avatar_url ? 'display:none' : ''}>
        {(data.profile.display_name ?? data.profile.username).slice(0, 1).toUpperCase()}
      </span>
    </div>
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
        <button class="stat-link" on:click={() => switchTab('followers')}>
          <b>{followersLoaded ? followers.length : '—'}</b> <span>người theo dõi</span>
        </button>
        <button class="stat-link" on:click={() => switchTab('following')}>
          <b>{followingLoaded ? followingList.length : '—'}</b> <span>đang theo dõi</span>
        </button>
      </div>
    </div>
    <div class="profile-head-actions">
      {#if isOwner}
        <button class="btn ghost" on:click={startEdit}>Chỉnh sửa hồ sơ</button>
      {:else if $user}
        <button class={`btn ${following ? 'ghost' : 'emerald'}`} on:click={toggleFollow}>
          {following ? 'Đang theo dõi' : '+ Theo dõi'}
        </button>
      {/if}
    </div>
  </div>

  {#if editing}
    <div class="edit-panel">
      <h3>Chỉnh sửa hồ sơ</h3>
      <div class="edit-field">
        <label for="edit-name">Tên hiển thị</label>
        <input id="edit-name" type="text" bind:value={editDisplayName} placeholder="Tên hiển thị" maxlength="100" />
      </div>
      <div class="edit-field">
        <label for="edit-bio">Giới thiệu</label>
        <textarea id="edit-bio" bind:value={editBio} placeholder="Mô tả bản thân..." rows="3" maxlength="500"></textarea>
      </div>
      <div class="edit-field">
        <label for="edit-avatar">URL ảnh đại diện</label>
        <input id="edit-avatar" type="url" bind:value={editAvatarUrl} placeholder="https://..." />
      </div>
      <div class="edit-field">
        <span class="edit-label">Chủ đề quan tâm</span>
        <div class="topic-grid">
          {#each ALL_TOPICS as topic}
            <button
              class="chip-toggle"
              class:active={editTopicPrefs.includes(topic)}
              on:click={() => toggleTopic(topic)}
            >{topic}</button>
          {/each}
        </div>
      </div>
      <div class="edit-actions">
        <button class="btn emerald" on:click={saveProfile} disabled={saving}>
          {saving ? 'Đang lưu...' : 'Lưu thay đổi'}
        </button>
        <button class="btn ghost" on:click={cancelEdit}>Hủy</button>
      </div>
    </div>
  {/if}

  <div class="profile-grid">
    <div>
      <div class="tabs">
        <button class="tab" class:active={activeTab === 'posts'} on:click={() => switchTab('posts')}>
          Bài viết <span class="count-mini">{data.posts.length}</span>
        </button>
        <button class="tab" class:active={activeTab === 'followers'} on:click={() => switchTab('followers')}>
          Người theo dõi
        </button>
        <button class="tab" class:active={activeTab === 'following'} on:click={() => switchTab('following')}>
          Đang theo dõi
        </button>
      </div>

      {#if activeTab === 'posts'}
        {#each data.posts as p (p.id)}<PostCard post={p} />{/each}
        {#if data.posts.length === 0}<p class="muted">Chưa có bài viết.</p>{/if}
      {:else if activeTab === 'followers'}
        {#if loadingTab}
          <p class="muted">Đang tải...</p>
        {:else if followers.length === 0}
          <p class="muted">Chưa có người theo dõi.</p>
        {:else}
          <div class="user-list">
            {#each followers as f (f.id)}
              <a href="/profile/{f.id}" class="user-card">
                <div class="avatar s40">
                  {#if f.avatar_url}
                    <img src={f.avatar_url} alt={f.display_name ?? f.username} class="avatar-img" on:error={handleAvatarError} />
                  {/if}
                  <span class="avatar-fallback" style={f.avatar_url ? 'display:none' : ''}>
                    {(f.display_name ?? f.username).slice(0, 1).toUpperCase()}
                  </span>
                </div>
                <div class="user-card-info">
                  <div class="user-card-name">{f.display_name ?? f.username}</div>
                  <div class="user-card-handle">@{f.username}</div>
                </div>
              </a>
            {/each}
          </div>
        {/if}
      {:else if activeTab === 'following'}
        {#if loadingTab}
          <p class="muted">Đang tải...</p>
        {:else if followingList.length === 0}
          <p class="muted">Chưa theo dõi ai.</p>
        {:else}
          <div class="user-list">
            {#each followingList as f (f.id)}
              <a href="/profile/{f.id}" class="user-card">
                <div class="avatar s40">
                  {#if f.avatar_url}
                    <img src={f.avatar_url} alt={f.display_name ?? f.username} class="avatar-img" on:error={handleAvatarError} />
                  {/if}
                  <span class="avatar-fallback" style={f.avatar_url ? 'display:none' : ''}>
                    {(f.display_name ?? f.username).slice(0, 1).toUpperCase()}
                  </span>
                </div>
                <div class="user-card-info">
                  <div class="user-card-name">{f.display_name ?? f.username}</div>
                  <div class="user-card-handle">@{f.username}</div>
                </div>
              </a>
            {/each}
          </div>
        {/if}
      {/if}
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

  .avatar {
    position: relative;
    overflow: hidden;
  }

  .avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 50%;
    position: absolute;
    inset: 0;
  }

  .avatar-fallback {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .stat-link {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    font: inherit;
    color: inherit;
    transition: opacity 0.15s;
  }

  .stat-link:hover {
    opacity: 0.7;
  }

  /* Edit panel */
  .edit-panel {
    max-width: 640px;
    margin: 0 auto 24px;
    padding: 20px 24px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(12px);
  }

  .edit-panel h3 {
    margin: 0 0 16px;
    font-size: 1.1rem;
  }

  .edit-field {
    margin-bottom: 14px;
  }

  .edit-field label,
  .edit-label {
    display: block;
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.6);
    margin-bottom: 6px;
  }

  .edit-field input,
  .edit-field textarea {
    width: 100%;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(255, 255, 255, 0.04);
    color: inherit;
    font: inherit;
    font-size: 0.95rem;
    outline: none;
    transition: border-color 0.2s;
    box-sizing: border-box;
  }

  .edit-field input:focus,
  .edit-field textarea:focus {
    border-color: var(--azure-500, #3b82f6);
  }

  .edit-field textarea {
    resize: vertical;
  }

  .topic-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .chip-toggle {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: transparent;
    color: inherit;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .chip-toggle.active {
    background: var(--azure-500, #3b82f6);
    border-color: var(--azure-500, #3b82f6);
    color: #fff;
  }

  .chip-toggle:hover:not(.active) {
    border-color: rgba(255, 255, 255, 0.3);
  }

  .edit-actions {
    display: flex;
    gap: 10px;
    margin-top: 16px;
  }

  /* User list */
  .user-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .user-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    text-decoration: none;
    color: inherit;
    transition: background 0.15s;
  }

  .user-card:hover {
    background: rgba(255, 255, 255, 0.08);
  }

  .user-card-info {
    flex: 1;
    min-width: 0;
  }

  .user-card-name {
    font-weight: 600;
    font-size: 0.95rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .user-card-handle {
    font-size: 0.82rem;
    color: rgba(255, 255, 255, 0.5);
  }

  .muted {
    text-align: center;
    padding: 32px 0;
    color: rgba(255, 255, 255, 0.4);
  }
</style>
