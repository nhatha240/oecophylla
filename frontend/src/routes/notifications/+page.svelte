<script lang="ts">
  import type { PageData } from './$types';
  import { listNotifications, markAllNotificationsRead, markNotificationRead } from '$lib/api/notifications';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let data: PageData;
  let items = data.notifications.items;
  let cursor = data.notifications.next_cursor;
  let loading = false;
  let feedback = '';
  function label(type: string) { return ({ liked: 'đã thích bài viết của bạn', commented: 'đã bình luận về bài viết của bạn', comment_replied: 'đã trả lời bình luận của bạn', followed: 'đã theo dõi bạn', post_hidden: 'bài viết đã được ẩn', author_warned: 'tài khoản nhận cảnh báo', author_banned: 'tài khoản đã bị hạn chế', report_dismissed: 'báo cáo đã được xử lý' } as Record<string,string>)[type] ?? 'có cập nhật mới'; }
  async function read(id: string) { try { await markNotificationRead(fetch, id); items = items.map((n) => n.id === id ? { ...n, is_read: true } : n); } catch { feedback = 'Chưa thể đánh dấu đã đọc.'; } }
  async function readAll() { try { await markAllNotificationsRead(fetch); items = items.map((n) => ({ ...n, is_read: true })); } catch { feedback = 'Chưa thể đánh dấu đã đọc.'; } }
  async function more() { if (!cursor || loading) return; loading = true; try { const next = await listNotifications(fetch, { cursor }); items = [...items, ...next.items]; cursor = next.next_cursor; } catch { feedback = 'Chưa thể tải thêm thông báo.'; } finally { loading = false; } }
</script>
<svelte:head><title>Thông báo — Oecophylla</title></svelte:head>
<section class="notifications-page"><header><div><p class="eyebrow">CẬP NHẬT TỪ CỘNG ĐỒNG</p><h1 class="serif">Thông báo</h1><p>Theo dõi những cuộc trò chuyện và kết nối của bạn.</p></div>{#if items.some((n) => !n.is_read)}<button class="pill-outline" on:click={readAll}>Đánh dấu đã đọc</button>{/if}</header>{#if feedback}<p class="feedback" role="alert">{feedback}</p>{/if}{#if items.length}<div class="notification-list">{#each items as notice}<article class:unread={!notice.is_read}><div class="icon"><Icon name={notice.type === 'followed' ? 'Users' : notice.type === 'liked' ? 'Heart' : 'Comment'} size={19} /></div><div><p><strong>{notice.actor_display_name ?? notice.actor_username}</strong> {label(notice.type)}.</p>{#if notice.snippet}<small>{notice.snippet}</small>{/if}<time>{new Intl.DateTimeFormat('vi-VN').format(new Date(notice.created_at))}</time></div>{#if !notice.is_read}<button on:click={() => read(notice.id)} aria-label="Đánh dấu đã đọc"><span></span></button>{/if}</article>{/each}</div>{#if cursor}<button class="pill-outline more" disabled={loading} on:click={more}>{loading ? 'Đang tải…' : 'Xem thêm'}</button>{/if}{:else}<div class="empty"><Icon name="Bell" size={29} /><h2 class="serif">Chưa có thông báo mới</h2><p>Những cập nhật từ cộng đồng sẽ xuất hiện tại đây.</p></div>{/if}</section>
<style>
  .notifications-page { max-width: 850px; margin: auto; padding: 35px 32px 60px; }
  header { display: flex; justify-content: space-between; align-items: end; gap: 20px; margin-bottom: 25px; }
  h1 { margin: 8px 0; font-size: 35px; font-weight: 500; letter-spacing: -.05em; }
  header p:last-child { margin: 0; color: #70847b; font: 13px 'Lora', serif; }
  .notification-list { display: grid; gap: 9px; }
  article { display: flex; align-items: start; gap: 13px; padding: 17px; border: 1px solid #e6eeea; border-radius: 9px; background: #fff; }
  article.unread { background: #f0f7f3; border-color: #dcece3; }
  .icon { flex: 0 0 38px; display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; background: #e0efe7; color: #22695d; }
  article > div:nth-child(2) { flex: 1; }
  article p { margin: 0 0 6px; color: #436057; font: 13px/1.5 'Lora', serif; }
  article strong { color: #183d36; }
  article small, article time { display: block; color: #8b9c92; font-size: 10px; }
  article time { margin-top: 7px; }
  article button { border: 0; background: transparent; }
  article button span { display: block; width: 9px; height: 9px; border-radius: 50%; background: #29826f; }
  .more { display: flex; margin: 20px auto; }
  .empty { display: grid; justify-items: center; gap: 12px; padding: 65px 25px; border: 1px solid #e7eeea; border-radius: 10px; background: white; text-align: center; color: #507c70; }
  .empty h2, .empty p { margin: 0; }
  .empty h2 { font-size: 22px; font-weight: 500; }
  .empty p { color: #83958b; font-size: 12px; }
  .feedback { color: #a24044; font-size: 12px; }
  @media (max-width: 720px) { .notifications-page { padding: 22px 14px 35px; } h1 { font-size: 28px; } header { align-items: start; } header button { min-width: 90px; padding: 0 9px; font-size: 10px; } }
</style>
