<script lang="ts">
  import { goto } from '$app/navigation';
  import type { Notification } from '$lib/types';
  import { markNotificationAsRead } from '$lib/stores/notifications';
  import { showToast } from '$lib/stores/toast';

  export let item: Notification;
  export let onNavigate: () => void = () => {};

  const formatters: Record<Notification['type'], string> = {
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

  $: actorName = item.actor_display_name ?? item.actor_username;
  $: href = item.post_id ? `/post/${item.post_id}` : `/profile/${item.actor_id}`;
  $: relativeTime = formatRelativeTime(item.created_at);

  async function openNotification(): Promise<void> {
    try {
      if (!item.is_read) {
        await markNotificationAsRead(item.id, fetch);
        item = { ...item, is_read: true };
      }
      onNavigate();
      await goto(href);
    } catch {
      showToast('Không mở được thông báo.');
    }
  }
</script>

<button
  class={`glass-surface flex w-full items-start gap-3 rounded-[28px] px-4 py-3 text-left transition hover:-translate-y-0.5 hover:shadow-[0_14px_40px_rgba(17,24,39,0.12)] ${item.is_read ? 'opacity-80' : ''}`}
  on:click={openNotification}
>
  <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[18px] border border-white/60 bg-white/70 text-sm font-semibold text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
    {actorName.slice(0, 1).toUpperCase()}
  </span>
  <span class="min-w-0 flex-1">
    <span class="flex items-start justify-between gap-3">
      <span class="text-sm font-semibold text-slate-900">
        {actorName}
        <span class="font-normal text-slate-600">{formatters[item.type]}</span>
      </span>
      {#if !item.is_read}
        <span class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-[var(--azure-500)]"></span>
      {/if}
    </span>
    {#if item.snippet}
      <span class="mt-1 line-clamp-2 block text-sm text-slate-500">{item.snippet}</span>
    {/if}
    <span class="mt-2 block text-xs uppercase tracking-[0.24em] text-slate-400">{relativeTime}</span>
  </span>
</button>
