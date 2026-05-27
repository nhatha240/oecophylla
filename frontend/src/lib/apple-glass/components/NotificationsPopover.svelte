<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Icon from './Icon.svelte';
  import { NOTIFICATIONS } from '../data';

  export let open = false;
  export let onClose: () => void = () => {};

  let cat = 'all';
  let readSet = new Set<string>();

  const cats = [
    { id: 'all', name: 'Tất cả' },
    { id: 'Tương tác', name: 'Tương tác' },
    { id: 'Kiểm duyệt', name: 'Kiểm duyệt' },
    { id: 'Gợi ý', name: 'Gợi ý' }
  ];
  const tonePalette: Record<string, [string, string]> = {
    rose: ['var(--rose-50)', 'var(--rose-500)'],
    emerald: ['var(--emerald-50)', 'var(--emerald-500)'],
    azure: ['var(--azure-50)', 'var(--azure-500)'],
    violet: ['var(--violet-50)', 'var(--violet-500)'],
    amber: ['var(--amber-50)', 'var(--amber-500)']
  };

  $: list = NOTIFICATIONS.filter((item) => cat === 'all' || item.cat === cat);
  $: unreadCount = list.filter((item) => item.unread && !readSet.has(item.id)).length;

  function markRead(id: string) {
    readSet = new Set([...readSet, id]);
  }
</script>

{#if open}
  <button class="notif-pop-scrim" aria-label="Đóng thông báo" on:click={onClose}></button>
  <div class="notif-pop" data-screen-label="Notifications Popover">
    <div class="notif-pop-head">
      <div>
        <div class="notif-pop-title">Thông báo</div>
        <div class="notif-pop-sub">{unreadCount > 0 ? `${unreadCount} thông báo mới` : 'Bạn đã đọc hết'}</div>
      </div>
      <button class="btn ghost sm" on:click={() => (readSet = new Set(list.map((item) => item.id)))}>
        <Icon name="Check" size={12} /> Đánh dấu đã đọc
      </button>
    </div>

    <div class="notif-pop-tabs">
      {#each cats as item}
        <button class={`notif-pop-tab ${cat === item.id ? 'active' : ''}`} on:click={() => (cat = item.id)}>{item.name}</button>
      {/each}
    </div>

    <div class="notif-pop-list">
      {#each list as item (item.id)}
        {@const colors = tonePalette[item.tone]}
        {@const isUnread = item.unread && !readSet.has(item.id)}
        <button class={`notif-item notif-button ${isUnread ? 'unread' : ''}`} on:click={() => markRead(item.id)}>
          {#if isUnread}<span class="unread-dot"></span>{/if}
          <span class="notif-icon" style={`background: ${colors[0]}; color: ${colors[1]}`}><Icon name={item.icon} size={15} /></span>
          <span class="notif-content">
            <span class="notif-msg">{@html item.msg}</span>
            <span class="notif-time"><span>{item.time}</span><span>·</span><span>{item.cat}</span></span>
          </span>
          {#if item.who}<Avatar author={item.who} size="s32" />{/if}
        </button>
      {/each}
    </div>

    <div class="notif-pop-foot">
      <button class="link-button" on:click={onClose}>Cài đặt thông báo</button>
      <span class="t-meta">Cập nhật vừa xong</span>
    </div>
  </div>
{/if}

<style>
  .notif-button,
  .link-button,
  .notif-pop-scrim {
    border: 0;
    color: inherit;
  }
  .notif-button {
    width: 100%;
    text-align: left;
  }
  .link-button {
    background: transparent;
    padding: 0;
  }
</style>
