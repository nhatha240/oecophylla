<script lang="ts">
  import Avatar from '../components/Avatar.svelte';
  import Icon from '../components/Icon.svelte';
  import { AUTHORS } from '../data';

  export let page = 'overview';
  export let onNav: (page: string) => void = () => {};
  export let onExit: () => void = () => {};

  const items = [
    { sec: 'Bảng điều khiển' },
    { id: 'overview', name: 'Tổng quan', icon: 'ChartBar' },
    { id: 'posts', name: 'Quản lý bài viết', icon: 'FileText' },
    { id: 'flagged', name: 'Bài bị gắn cờ', icon: 'Flag', count: 14 },
    { id: 'mod', name: 'Kiểm duyệt nội dung', icon: 'Shield', count: 28 },
    { sec: 'Cộng đồng' },
    { id: 'users', name: 'Quản lý người dùng', icon: 'Users' },
    { id: 'groups', name: 'Quản lý nhóm', icon: 'Group' },
    { id: 'topics', name: 'Chủ đề / Metadata', icon: 'Tag' },
    { id: 'reports', name: 'Báo cáo người dùng', icon: 'AlertTriangle', count: 6 },
    { sec: 'Hệ thống' },
    { id: 'rec', name: 'Hiệu quả đề xuất', icon: 'Activity' },
    { id: 'logs', name: 'Nhật ký hệ thống', icon: 'Database' }
  ];
</script>

<div class="admin-shell" data-screen-label="09 Admin">
  <aside class="admin-sidebar">
    <button class="brand admin-brand" on:click={onExit}><div class="brand-mark" style="background: var(--emerald-500)">O</div><div class="brand-name">Oecophy<em>lla</em></div></button>
    <div class="admin-sidebar-tag"><Icon name="Shield" size={12} /> Khu vực Quản trị</div>
    <nav class="nav">
      {#each items as item, i}
        {#if item.sec}
          <div class="nav-section">{item.sec}</div>
        {:else}
          <button class={`nav-item ${page === item.id ? 'active' : ''}`} on:click={() => onNav(item.id ?? 'overview')}>
            <Icon name={item.icon ?? 'Dot'} size={16} /><span>{item.name}</span>{#if item.count}<span class="count">{item.count}</span>{/if}
          </button>
        {/if}
      {/each}
    </nav>
    <div class="sidebar-foot">
      <button class="nav-item" on:click={onExit}><Icon name="ArrowLeft" size={16} /><span>Trở về Oecophylla</span></button>
      <div class="profile-card" style="margin-top: 8px"><Avatar author={AUTHORS[5]} size="s32" /><div style="min-width: 0; flex: 1"><div class="name" style="color: var(--paper)">Bùi Khánh Linh</div><div class="handle">Senior Moderator</div></div></div>
    </div>
  </aside>
  <main class="admin-main"><slot /></main>
</div>

<style>
  .admin-brand { border: 0; color: inherit; width: 100%; text-align: left; }
</style>
