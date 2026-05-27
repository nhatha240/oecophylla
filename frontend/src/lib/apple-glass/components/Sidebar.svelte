<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Icon from './Icon.svelte';
  import { AUTHORS } from '../data';

  export let active = 'feed';
  export let counts: Record<string, number> = {};
  export let onNav: (screen: string) => void = () => {};

  const items = [
    { id: 'feed', name: 'Trang chủ', icon: 'Home' },
    { id: 'explore', name: 'Khám phá', icon: 'Compass' },
    { id: 'follow', name: 'Theo dõi', icon: 'Users' },
    { id: 'group', name: 'Nhóm', icon: 'Group' },
    { id: 'saved', name: 'Đã lưu', icon: 'Bookmark' },
    { id: 'notif', name: 'Thông báo', icon: 'Bell' },
    { id: 'profile', name: 'Hồ sơ', icon: 'User' }
  ];

  const groups = [
    ['AI có trách nhiệm', 'var(--emerald-500)'],
    ['Kinh tế Việt Nam', 'var(--azure-500)'],
    ['Báo chí số', 'var(--amber-500)']
  ];
</script>

<aside class="sidebar">
  <button class="brand brand-button" on:click={() => onNav('landing')}>
    <div class="brand-mark">O</div>
    <div class="brand-name">Oecophy<em>lla</em></div>
  </button>
  <nav class="nav">
    {#each items as it (it.id)}
      <button class={`nav-item ${active === it.id ? 'active' : ''}`} on:click={() => onNav(it.id)}>
        <Icon name={it.icon} size={18} />
        <span class="top-inner-edge"></span>
        <span class="bottom-inner-edge"></span>
        <span class="top-glow"></span>
        <span class="liquid-core"></span>
        <span>{it.name}</span>
        {#if counts[it.id]}
          <span class="count">{counts[it.id]}</span>
        {/if}
      </button>
    {/each}
    <div class="nav-section">Của bạn</div>
    {#each groups as group}
      <button class="nav-item" on:click={() => onNav('group')}>
        <span style={`width: 10px; height: 10px; border-radius: 3px; background: ${group[1]}`}></span>
        {group[0]}
      </button>
    {/each}
  </nav>
  <div class="sidebar-foot">
    <button class="profile-card profile-button" on:click={() => onNav('profile')}>
      <Avatar author={AUTHORS[0]} size="s32" />
      <div style="min-width: 0; flex: 1">
        <div class="name">Nguyễn Quỳnh Anh</div>
        <div class="handle">@quynhanh</div>
      </div>
      <Icon name="Settings" size={16} className="muted" />
    </button>
  </div>
</aside>

<style>
  .brand-button,
  .profile-button {
    border: 0;
    width: 100%;
    text-align: left;
    color: inherit;
  }
</style>
