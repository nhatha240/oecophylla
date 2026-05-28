<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import NotificationItem from '$lib/components/NotificationItem.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import {
    notifications,
    initNotifications,
    markAllNotificationsAsRead,
    subscribeSSE
  } from '$lib/stores/notifications';

  let cleanup: (() => void) | null = null;

  onMount(async () => {
    await initNotifications(fetch);
    cleanup = subscribeSSE(fetch);
  });

  onDestroy(() => {
    cleanup?.();
  });

  async function handleMarkAll() {
    await markAllNotificationsAsRead(fetch);
  }
</script>

<svelte:head>
  <title>Thông báo — Oecophylla</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-4 py-6 pb-24 lg:pb-8">
  <div class="mb-6 flex items-center justify-between">
    <h1 class="font-serif text-2xl font-medium tracking-tight">Thông báo</h1>
    {#if $notifications.items.length > 0 && $notifications.unread > 0}
      <button
        class="inline-flex items-center gap-1.5 rounded-full border border-white/60 bg-white/70 px-3.5 py-1.5 text-xs font-semibold text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] transition hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(17,24,39,0.1)]"
        on:click={handleMarkAll}
      >
        <Icon name="Check" size={14} />
        Đọc hết
      </button>
    {/if}
  </div>

  {#if $notifications.loading}
    <div class="flex flex-col items-center justify-center py-20 text-slate-400">
      <div class="mb-3 h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-transparent"></div>
      <span class="text-sm">Đang tải thông báo...</span>
    </div>
  {:else if $notifications.items.length === 0}
    <div class="glass-surface flex flex-col items-center justify-center rounded-[28px] px-6 py-16 text-center">
      <div class="mb-4 flex h-14 w-14 items-center justify-center rounded-[20px] border border-white/60 bg-white/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
        <Icon name="Bell" size={24} />
      </div>
      <p class="text-sm font-medium text-slate-600">Chưa có thông báo nào</p>
      <p class="mt-1 text-xs text-slate-400">Khi có người thích, bình luận hoặc theo dõi bạn, thông báo sẽ xuất hiện ở đây.</p>
    </div>
  {:else}
    <div class="flex flex-col gap-2">
      {#each $notifications.items as item (item.id)}
        <NotificationItem {item} />
      {/each}
    </div>
  {/if}
</div>
