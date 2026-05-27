<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import NotificationItem from '$lib/components/NotificationItem.svelte';
  import {
    initNotifications,
    markAllNotificationsAsRead,
    notifications,
    subscribeSSE
  } from '$lib/stores/notifications';
  import { showToast } from '$lib/stores/toast';

  export let enabled = false;

  let open = false;

  onMount(() => {
    if (!enabled) return;
    initNotifications(fetch);
    const unsubscribe = subscribeSSE();
    return unsubscribe;
  });

  async function readAll(): Promise<void> {
    try {
      await markAllNotificationsAsRead(fetch);
    } catch {
      showToast('Không đánh dấu đã đọc được.');
    }
  }
</script>

{#if enabled}
  <div class="relative">
    <button
      class="icon-btn relative"
      title="Thông báo"
      aria-haspopup="dialog"
      aria-expanded={open}
      on:click={() => (open = !open)}
    >
      <Icon name="Bell" size={18} />
      {#if $notifications.unread > 0}
        <span class="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--rose-500)] px-1 text-[11px] font-semibold text-white">
          {$notifications.unread > 9 ? '9+' : $notifications.unread}
        </span>
      {/if}
    </button>

    {#if open}
      <button class="fixed inset-0 z-30 bg-transparent" aria-label="Đóng thông báo" on:click={() => (open = false)}></button>
      <section class="glass-surface absolute right-0 z-40 mt-3 flex w-[min(92vw,24rem)] flex-col gap-3 rounded-[32px] px-4 py-4 shadow-[0_28px_80px_rgba(15,23,42,0.16)]">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h3 class="text-display-serif text-xl text-slate-900">Thông báo</h3>
            <p class="text-sm text-slate-500">
              {#if $notifications.unavailable}
                Dịch vụ chưa sẵn sàng.
              {:else if $notifications.unread > 0}
                {$notifications.unread} mục chưa đọc
              {:else}
                Bạn đã đọc hết
              {/if}
            </p>
          </div>
          <button class="glass-chip text-xs" on:click={readAll} disabled={$notifications.items.length === 0}>Đọc hết</button>
        </div>

        <div class="max-h-[24rem] space-y-3 overflow-y-auto pr-1">
          {#if $notifications.loading}
            <p class="px-2 py-6 text-center text-sm text-slate-500">Đang tải thông báo…</p>
          {:else if $notifications.items.length === 0}
            <div class="glass-surface rounded-[26px] px-4 py-6 text-center text-sm text-slate-500">
              {$notifications.unavailable ? 'Thông báo sẽ xuất hiện khi service hoàn tất.' : 'Chưa có thông báo mới.'}
            </div>
          {:else}
            {#each $notifications.items as item (item.id)}
              <NotificationItem {item} onNavigate={() => (open = false)} />
            {/each}
          {/if}
        </div>

        <div class="flex items-center justify-between px-1 text-xs uppercase tracking-[0.24em] text-slate-400">
          <span>{$notifications.connected ? 'Đang đồng bộ trực tiếp' : 'Chờ kết nối trực tiếp'}</span>
          <span>{enabled ? 'Apple Glass' : ''}</span>
        </div>
      </section>
    {/if}
  </div>
{/if}
