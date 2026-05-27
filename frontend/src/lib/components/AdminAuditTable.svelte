<script lang="ts">
  import type { AdminAuditLog } from '$lib/types';

  export let items: AdminAuditLog[] = [];
  export let nextCursor: string | null = null;
  export let available = true;
  export let actorId = '';
  export let action = '';
  export let limit = 20;
</script>

<section class="glass-surface rounded-[36px] px-5 py-5">
  <div class="mb-4 flex items-start justify-between gap-4">
    <div>
      <h2 class="text-display-serif text-2xl text-slate-900">Audit</h2>
      <p class="text-sm text-slate-500">
        {available ? 'Cursor feed của các hành động moderation.' : 'Audit log sẽ xuất hiện khi backend Phase 3 xong.'}
      </p>
    </div>
    <span class="glass-chip text-xs">{items.length} hàng</span>
  </div>

  <form class="mb-5 grid gap-3 md:grid-cols-[1fr_1fr_auto]" method="get">
    <input
      class="rounded-[22px] border border-white/60 bg-white/70 px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-[var(--azure-300)] focus:bg-white"
      name="actor_id"
      placeholder="Lọc theo actor_id"
      value={actorId}
    />
    <input
      class="rounded-[22px] border border-white/60 bg-white/70 px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-[var(--azure-300)] focus:bg-white"
      name="action"
      placeholder="Lọc theo action"
      value={action}
    />
    <button class="glass-button-primary justify-center" type="submit">Lọc</button>
    <input type="hidden" name="limit" value={limit} />
  </form>

  {#if items.length === 0}
    <div class="glass-surface rounded-[28px] px-4 py-8 text-center text-sm text-slate-500">
      {available ? 'Không có bản ghi phù hợp.' : 'Chưa có dữ liệu audit để hiển thị.'}
    </div>
  {:else}
    <div class="space-y-3">
      {#each items as entry (entry.id)}
        <article class="glass-surface rounded-[28px] px-4 py-4">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="text-sm font-semibold text-slate-800">{entry.action}</div>
              <div class="mt-1 text-sm text-slate-500">
                {entry.actor_display_name ?? entry.actor_username ?? entry.actor_id}
                {#if entry.target_type || entry.target_id}
                  · {entry.target_type ?? 'target'} {entry.target_id ?? ''}
                {/if}
              </div>
            </div>
            <span class="text-xs uppercase tracking-[0.24em] text-slate-400">{new Date(entry.created_at).toLocaleString('vi-VN')}</span>
          </div>

          {#if entry.metadata}
            <pre class="mt-3 overflow-x-auto rounded-[22px] bg-[rgba(248,250,252,0.82)] px-3 py-3 text-xs text-slate-500">{JSON.stringify(entry.metadata, null, 2)}</pre>
          {/if}
        </article>
      {/each}
    </div>
  {/if}

  {#if nextCursor}
    <div class="mt-4 flex justify-end">
      <a
        class="glass-chip"
        href={`/admin?audit_cursor=${encodeURIComponent(nextCursor)}&actor_id=${encodeURIComponent(actorId)}&action=${encodeURIComponent(action)}&limit=${limit}&tab=audit`}
      >
        Trang tiếp
      </a>
    </div>
  {/if}
</section>
