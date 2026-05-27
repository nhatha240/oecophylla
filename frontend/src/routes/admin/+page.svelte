<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import AdminReportsTable from '$lib/components/AdminReportsTable.svelte';
  import AdminAuditTable from '$lib/components/AdminAuditTable.svelte';
  import type { AdminAuditLog, AdminReport, CursorPage } from '$lib/types';

  export let data: {
    reports: CursorPage<AdminReport>;
    reportsAvailable: boolean;
    audit: CursorPage<AdminAuditLog>;
    auditAvailable: boolean;
    filters: {
      actorId: string;
      action: string;
      limit: number;
    };
  };

  let tab: 'reports' | 'audit' = data.filters.action || data.audit.items.length ? 'audit' : 'reports';
</script>

<svelte:head>
  <title>Oecophylla — Admin</title>
</svelte:head>

<div class="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-6">
  <section class="glass-surface flex flex-col gap-5 rounded-[40px] px-6 py-6 md:flex-row md:items-end md:justify-between">
    <div>
      <p class="text-mono-meta text-xs uppercase tracking-[0.32em] text-slate-400">Moderation Center</p>
      <h1 class="text-display-serif mt-2 text-4xl text-slate-900">Admin Console</h1>
      <p class="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
        Dùng giao diện thật của Oecophylla để xử lý báo cáo và đọc audit log. Nếu backend Phase 3 chưa sẵn sàng, trang vẫn render trạng thái rỗng an toàn.
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button class={`glass-chip ${tab === 'reports' ? 'bg-white text-slate-900' : ''}`} type="button" on:click={() => (tab = 'reports')}>
        <Icon name="Flag" size={14} /> Reports
      </button>
      <button class={`glass-chip ${tab === 'audit' ? 'bg-white text-slate-900' : ''}`} type="button" on:click={() => (tab = 'audit')}>
        <Icon name="ChartBar" size={14} /> Audit
      </button>
    </div>
  </section>

  {#if tab === 'reports'}
    <AdminReportsTable
      items={data.reports.items}
      nextCursor={data.reports.next_cursor}
      available={data.reportsAvailable}
      limit={data.filters.limit}
    />
  {:else}
    <AdminAuditTable
      items={data.audit.items}
      nextCursor={data.audit.next_cursor}
      available={data.auditAvailable}
      actorId={data.filters.actorId}
      action={data.filters.action}
      limit={data.filters.limit}
    />
  {/if}
</div>
