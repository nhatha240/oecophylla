<script lang="ts">
  import { onMount } from 'svelte';
  import type { PageData } from './$types';
  import { listNotifications } from '$lib/api/notifications';
  import { markAllNotificationsAsRead, markNotificationAsRead, notifications } from '$lib/stores/notifications';
  import { notificationActorName, notificationHref, notificationLabel, notificationPreview } from '$lib/notificationPresentation';
  import type { Notification } from '$lib/types';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let data: PageData;
  let items: Notification[] = data.notifications.items;
  let cursor = data.notifications.next_cursor;
  let loading = false;
  let feedback = '';

  onMount(() => notifications.subscribe((state) => {
    if (!state.items.length) return;
    const merged = new Map(items.map((item) => [item.id, item]));
    for (const item of state.items) merged.set(item.id, item);
    items = [...merged.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
  }));

  async function read(id: string) {
    try {
      await markNotificationAsRead(id);
      items = items.map((item) => item.id === id ? { ...item, read: true } : item);
    } catch { feedback = 'Chưa thể đánh dấu đã đọc.'; }
  }
  async function readAll() {
    try {
      await markAllNotificationsAsRead();
      items = items.map((item) => ({ ...item, read: true }));
    } catch { feedback = 'Chưa thể đánh dấu đã đọc.'; }
  }
  async function more() {
    if (!cursor || loading) return;
    loading = true;
    try {
      const next = await listNotifications(fetch, { cursor });
      const seen = new Set(items.map((item) => item.id));
      items = [...items, ...next.items.filter((item) => !seen.has(item.id))];
      cursor = next.next_cursor;
    } catch { feedback = 'Chưa thể tải thêm thông báo.'; }
    finally { loading = false; }
  }
</script>
<svelte:head><title>Thông báo — Oecophylla</title></svelte:head>
<section class="notifications-page">
  <header><div><p class="eyebrow">CẬP NHẬT TỪ CỘNG ĐỒNG</p><h1 class="serif">Thông báo</h1><p>Theo dõi những cuộc trò chuyện và kết nối của bạn.</p></div>{#if items.some((item) => !item.read)}<button class="pill-outline" on:click={readAll}>Đánh dấu đã đọc</button>{/if}</header>
  {#if feedback}<p class="feedback" role="alert">{feedback}</p>{/if}
  {#if items.length}
    <div class="notification-list">
      {#each items as notice (notice.id)}
        <article class:unread={!notice.read}>
          <div class="icon">
            {#if notice.actor?.avatar_url}<img src={notice.actor.avatar_url} alt="" />{:else}<Icon name={notice.kind === 'followed' ? 'Users' : notice.kind === 'liked' ? 'Heart' : 'Comment'} size={19} />{/if}
          </div>
          <div class="notice-body">
            {#if notificationHref(notice)}<a class="notice-link" href={notificationHref(notice) ?? '#'}><strong>{notificationActorName(notice)}</strong> {notificationLabel(notice.kind)}.</a>
            {:else}<p><strong>{notificationActorName(notice)}</strong> {notificationLabel(notice.kind)}.</p>{/if}
            {#if notificationPreview(notice)}<small>{notificationPreview(notice)}</small>{/if}
            <time datetime={notice.created_at}>{new Intl.DateTimeFormat('vi-VN').format(new Date(notice.created_at))}</time>
          </div>
          {#if !notice.read}<button class="read-button" on:click={() => read(notice.id)} aria-label="Đánh dấu đã đọc"><span></span></button>{/if}
        </article>
      {/each}
    </div>
    {#if cursor}<button class="pill-outline more" disabled={loading} on:click={more}>{loading ? 'Đang tải…' : 'Xem thêm'}</button>{/if}
  {:else}<div class="empty"><Icon name="Bell" size={29} /><h2 class="serif">Chưa có thông báo mới</h2><p>Những cập nhật từ cộng đồng sẽ xuất hiện tại đây.</p></div>{/if}
</section>
<style>
  .notifications-page { max-width: 850px; margin: auto; padding: 35px 32px 60px; }
  header { display: flex; justify-content: space-between; align-items: end; gap: 20px; margin-bottom: 25px; }
  h1 { margin: 8px 0; font-size: 35px; font-weight: 500; letter-spacing: -.05em; }
  header p:last-child { margin: 0; color: #70847b; font: 13px 'Lora', serif; }
  .notification-list { display: grid; gap: 9px; }
  article { display: flex; align-items: start; gap: 13px; padding: 17px; border: 1px solid #e6eeea; border-radius: 9px; background: #fff; }
  article.unread { background: #f0f7f3; border-color: #dcece3; }
  .icon { flex: 0 0 38px; display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; background: #e0efe7; color: #22695d; }
  .icon img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
  .notice-body { flex: 1; min-width: 0; }
  .notice-link { display: block; margin-bottom: 6px; color: #436057; font: 13px/1.5 'Lora', serif; text-decoration: none; }
  .notice-link:hover { text-decoration: underline; }
  article p { margin: 0 0 6px; color: #436057; font: 13px/1.5 'Lora', serif; }
  article strong { color: #183d36; }
  article small, article time { display: block; color: #8b9c92; font-size: 10px; }
  article time { margin-top: 7px; }
  .read-button { border: 0; background: transparent; cursor: pointer; }
  .read-button span { display: block; width: 9px; height: 9px; border-radius: 50%; background: #29826f; }
  .more { display: flex; margin: 20px auto; }
  .empty { display: grid; justify-items: center; gap: 12px; padding: 65px 25px; border: 1px solid #e7eeea; border-radius: 10px; background: white; text-align: center; color: #507c70; }
  .empty h2, .empty p { margin: 0; }
  .empty h2 { font-size: 22px; font-weight: 500; }
  .empty p { color: #83958b; font-size: 12px; }
  .feedback { color: #a24044; font-size: 12px; }
  @media (max-width: 720px) { .notifications-page { padding: 22px 14px 35px; } h1 { font-size: 28px; } header { align-items: start; } header button { min-width: 90px; padding: 0 9px; font-size: 10px; } }
</style>
