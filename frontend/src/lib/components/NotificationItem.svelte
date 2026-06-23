<script lang="ts">
  import { goto } from '$app/navigation';
  import type { Notification } from '$lib/types';
  import {
    getNotificationActorInitial,
    getNotificationActorName,
    getNotificationHref,
    getNotificationSnippet,
    getNotificationType,
    isNotificationRead
  } from '$lib/notifications/normalize';
  import { markNotificationAsRead } from '$lib/stores/notifications';
  import { showToast } from '$lib/stores/toast';

  export let item: Notification;
  export let onNavigate: () => void = () => {};

  const formatters: Record<string, string> = {
    liked: 'đã thích bài viết của bạn',
    commented: 'đã bình luận về bài viết của bạn',
    comment_replied: 'đã trả lời bình luận của bạn',
    followed: 'đã theo dõi bạn',
    post_hidden: 'đã ẩn bài viết của bạn',
    author_warned: 'đã cảnh báo tài khoản của bạn',
    author_banned: 'đã khóa tài khoản của bạn',
    report_dismissed: 'đã xử lý báo cáo của bạn'
  };

  function formatRelativeTime(value: string): string {
    const diffSeconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
    const abs = Math.abs(diffSeconds);
    if (abs < 3600) return new Intl.RelativeTimeFormat('vi-VN', { numeric: 'auto' }).format(Math.round(diffSeconds / 60), 'minute');
    if (abs < 86400) return new Intl.RelativeTimeFormat('vi-VN', { numeric: 'auto' }).format(Math.round(diffSeconds / 3600), 'hour');
    return new Intl.RelativeTimeFormat('vi-VN', { numeric: 'auto' }).format(Math.round(diffSeconds / 86400), 'day');
  }

  $: notificationType = getNotificationType(item);
  $: isRead = isNotificationRead(item);
  $: actorName = getNotificationActorName(item);
  $: actorInitial = getNotificationActorInitial(item);
  $: href = getNotificationHref(item);
  $: snippet = getNotificationSnippet(item);
  $: relativeTime = formatRelativeTime(item.created_at);

  async function openNotification(): Promise<void> {
    try {
      if (!isRead) {
        await markNotificationAsRead(item.id, fetch);
        item = { ...item, is_read: true, read: true };
      }
      onNavigate();
      await goto(href);
    } catch {
      showToast('Không mở được thông báo.');
    }
  }
</script>

<button
  class={`glass-surface flex w-full items-start gap-3 rounded-[28px] px-4 py-3 text-left transition hover:-translate-y-0.5 hover:shadow-[0_14px_40px_rgba(17,24,39,0.12)] ${isRead ? 'opacity-80' : ''}`}
  on:click={openNotification}
>
  <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[18px] border border-white/60 bg-white/70 text-sm font-semibold text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
    {actorInitial}
  </span>
  <span class="min-w-0 flex-1">
    <span class="flex items-start justify-between gap-3">
      <span class="text-sm font-semibold text-slate-900">
        {actorName}
        <span class="font-normal text-slate-600">{formatters[notificationType] ?? 'đã gửi thông báo cho bạn'}</span>
      </span>
      {#if !isRead}
        <span class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-[var(--azure-500)]"></span>
      {/if}
    </span>
    {#if snippet}
      <span class="mt-1 line-clamp-2 block text-sm text-slate-500">{snippet}</span>
    {/if}
    <span class="mt-2 block text-xs uppercase tracking-[0.24em] text-slate-400">{relativeTime}</span>
  </span>
</button>
