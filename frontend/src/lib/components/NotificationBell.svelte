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
    let unsubscribe = () => {};
    let disposed = false;

    void (async () => {
      await initNotifications(fetch);
      if (!disposed) {
        unsubscribe = subscribeSSE(fetch);
      }
    })();

    return () => {
      disposed = true;
      unsubscribe();
    };
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
  <div style="position:relative;">
    <button
      class="icon-btn"
      style="position:relative;"
      title="Thông báo"
      aria-haspopup="dialog"
      aria-expanded={open}
      on:click={() => (open = !open)}
    >
      <Icon name="Bell" size={18} />
      {#if $notifications.unread > 0}
        <span style="
          position:absolute; top:-4px; right:-5px;
          min-width:17px; height:17px; padding:0 4px;
          background:var(--rose-500,#f43f5e);
          color:#fff; font-size:10px; font-weight:700; line-height:17px;
          border-radius:999px; text-align:center; white-space:nowrap;
        ">
          {$notifications.unread > 9 ? '9+' : $notifications.unread}
        </span>
      {/if}
    </button>

    {#if open}
      <!-- Backdrop -->
      <button
        style="position:fixed;inset:0;z-index:30;background:transparent;border:none;cursor:default;"
        aria-label="Đóng thông báo"
        on:click={() => (open = false)}
      ></button>

      <!-- Popup panel -->
      <div style="
        position:absolute; right:0; top:calc(100% + 10px); z-index:40;
        width:min(90vw,360px);
        background:rgba(255,255,255,0.92);
        backdrop-filter:blur(20px) saturate(1.8);
        -webkit-backdrop-filter:blur(20px) saturate(1.8);
        border:1px solid rgba(255,255,255,0.6);
        border-radius:20px;
        box-shadow:0 8px 40px rgba(15,23,42,0.14), 0 1px 3px rgba(15,23,42,0.06);
        overflow:hidden;
      ">
        <!-- Header -->
        <div style="
          display:flex; align-items:center; justify-content:space-between;
          padding:16px 18px 12px;
          border-bottom:1px solid var(--hairline,rgba(0,0,0,0.07));
        ">
          <div>
            <div style="font-size:16px;font-weight:700;color:var(--ink-900,#0f172a);letter-spacing:-0.01em;">Thông báo</div>
            <div style="font-size:12px;margin-top:2px;color:var(--ink-400,#94a3b8);">
              {#if $notifications.unavailable}
                Dịch vụ chưa sẵn sàng
              {:else if $notifications.unread > 0}
                {$notifications.unread} chưa đọc
              {:else}
                Đã đọc hết
              {/if}
            </div>
          </div>
          <button
            on:click={readAll}
            disabled={$notifications.items.length === 0}
            style="
              padding:5px 12px; border-radius:999px;
              background:var(--emerald-100,#d1fae5);
              color:var(--emerald-700,#047857);
              font-size:12px; font-weight:600;
              border:none; cursor:pointer;
              opacity:{$notifications.items.length === 0 ? 0.4 : 1};
              transition:opacity 0.15s;
            "
          >Đọc hết</button>
        </div>

        <!-- Body -->
        <div style="max-height:320px; overflow-y:auto; padding:8px 0;">
          {#if $notifications.loading}
            <div style="padding:32px 16px;text-align:center;font-size:13px;color:var(--ink-400,#94a3b8);">
              Đang tải…
            </div>
          {:else if $notifications.items.length === 0}
            <div style="padding:36px 16px;text-align:center;">
              <div style="font-size:28px;margin-bottom:8px;">🔔</div>
              <div style="font-size:13px;color:var(--ink-400,#94a3b8);">
                {$notifications.unavailable ? 'Thông báo sẽ xuất hiện khi service hoàn tất.' : 'Chưa có thông báo mới.'}
              </div>
            </div>
          {:else}
            {#each $notifications.items as item (item.id)}
              <NotificationItem {item} onNavigate={() => (open = false)} />
            {/each}
          {/if}
        </div>

        <!-- Footer -->
        <div style="
          display:flex; align-items:center; justify-content:space-between;
          padding:8px 18px;
          border-top:1px solid var(--hairline,rgba(0,0,0,0.07));
          font-size:10px; letter-spacing:0.08em; text-transform:uppercase;
          color:var(--ink-300,#cbd5e1);
        ">
          <span style="display:flex;align-items:center;gap:5px;">
            <span style="
              width:6px;height:6px;border-radius:50%;flex-shrink:0;
              background:{$notifications.connected ? 'var(--emerald-500,#22c55e)' : 'var(--ink-300,#cbd5e1)'};
              box-shadow:{$notifications.connected ? '0 0 0 3px rgba(34,197,94,0.2)' : 'none'};
            "></span>
            {$notifications.connected ? 'Trực tiếp' : 'Đang kết nối'}
          </span>
          <a href="/notifications" on:click={() => (open = false)} style="color:var(--emerald-600,#16a34a);text-decoration:none;font-weight:600;">Xem tất cả</a>
        </div>
      </div>
    {/if}
  </div>
{/if}
