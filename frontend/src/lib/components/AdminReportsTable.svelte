<script lang="ts">
  import { invalidateAll } from '$app/navigation';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import { resolveReport as apiResolveReport, ApiException } from '$lib/api';
  import { showToast } from '$lib/stores/toast';
  import type { AdminReport, ModerationAction } from '$lib/types';

  export let items: AdminReport[] = [];
  export let nextCursor: string | null = null;
  export let error: string | null = null;
  export let limit = 20;

  let notes: Record<string, string> = {};
  let resolving: string | null = null;
  let confirmBanFor: string | null = null;

  const actions: Array<{ id: ModerationAction; label: string; tone: string }> = [
    { id: 'dismiss', label: 'Bỏ qua', tone: 'glass-chip' },
    { id: 'hide_post', label: 'Ẩn bài', tone: 'glass-chip' },
    { id: 'warn_author', label: 'Cảnh báo', tone: 'glass-chip' },
    { id: 'ban_author', label: 'Khóa tác giả', tone: 'glass-button-primary' }
  ];

  async function handleResolve(id: string, action: ModerationAction): Promise<void> {
    resolving = id;
    try {
      await apiResolveReport(fetch, id, action, notes[id]?.trim());
      showToast('Đã cập nhật báo cáo.');
      confirmBanFor = null;
      await invalidateAll();
    } catch (err) {
      showToast(err instanceof ApiException ? `Lỗi ${err.status}: ${err.code}` : 'Không xử lý được báo cáo.');
    } finally {
      resolving = null;
    }
  }
</script>

<section class="glass-surface rounded-[36px] px-5 py-5">
  <div class="mb-4 flex items-center justify-between gap-4">
    <div>
      <h2 class="text-display-serif text-2xl text-slate-900">Reports</h2>
      <p class="text-sm text-slate-500">Các báo cáo chờ xử lý từ moderation-service.</p>
    </div>
    <span class="glass-chip text-xs">{items.length} hàng</span>
  </div>

  {#if error}
    <div class="rounded-[28px] border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-red-600">
      {error}
    </div>
  {:else if items.length === 0}
    <div class="glass-surface rounded-[28px] px-4 py-8 text-center text-sm text-slate-500">
      Không còn báo cáo pending.
    </div>
  {:else}
    <div class="space-y-4">
      {#each items as report (report.id)}
        <article class="glass-surface rounded-[30px] px-4 py-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="glass-chip text-[11px] uppercase tracking-[0.24em]">{report.reason}</span>
                <span class="text-xs uppercase tracking-[0.24em] text-slate-400">{new Date(report.created_at).toLocaleString('vi-VN')}</span>
              </div>
              <p class="mt-3 text-sm font-medium text-slate-800">{report.post_snippet ?? `Post ${report.post_id}`}</p>
              <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
                <span>Reporter: {report.reporter_username ?? report.reporter_id ?? 'ẩn danh'}</span>
              </div>
            </div>
            <a class="glass-chip text-xs" href={`/post/${report.post_id}`}>Xem bài</a>
          </div>

          <textarea
            class="mt-4 min-h-[5.5rem] w-full rounded-[24px] border border-white/60 bg-white/70 px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-[var(--azure-300)] focus:bg-white"
            bind:value={notes[report.id]}
            placeholder="Ghi chú nội bộ (tuỳ chọn)"
          ></textarea>

          <div class="mt-4 flex flex-wrap gap-2">
            {#each actions as action}
              <button
                class={action.tone}
                type="button"
                disabled={resolving === report.id}
                on:click={() => (action.id === 'ban_author' ? (confirmBanFor = report.id) : handleResolve(report.id, action.id))}
              >
                {action.label}
              </button>
            {/each}
          </div>

          {#if confirmBanFor === report.id}
            <div class="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[22px] border border-[rgba(244,114,182,0.2)] bg-[rgba(255,255,255,0.82)] px-4 py-3 text-sm text-slate-600">
              <span>Xác nhận khóa tác giả của báo cáo này?</span>
              <span class="flex gap-2">
                <button class="glass-chip" type="button" on:click={() => (confirmBanFor = null)}>Huỷ</button>
                <button class="glass-button-primary" type="button" on:click={() => handleResolve(report.id, 'ban_author')}>
                  <Icon name="Shield" size={14} /> Xác nhận khóa
                </button>
              </span>
            </div>
          {/if}
        </article>
      {/each}
    </div>
  {/if}

  {#if nextCursor}
    <div class="mt-4 flex justify-end">
      <a class="glass-chip" href={`/admin?reports_cursor=${encodeURIComponent(nextCursor)}&limit=${limit}`}>Trang tiếp</a>
    </div>
  {/if}
</section>
