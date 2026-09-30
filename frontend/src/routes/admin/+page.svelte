<script lang="ts">
  import type { PageData } from './$types';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let data: PageData;
  const steps = [
    { icon: 'Globe', name: 'Nguồn tin', detail: 'Nguồn nội dung được chọn lọc' },
    { icon: 'Database', name: 'Thu thập', detail: 'Bài viết đi vào hệ thống' },
    { icon: 'Shield', name: 'Kiểm duyệt', detail: 'Nội dung được đánh giá' },
    { icon: 'FileText', name: 'Xuất bản', detail: 'Tin đến cộng đồng' },
    { icon: 'Users', name: 'Người dùng', detail: 'Đọc và thảo luận' }
  ];
</script>
<svelte:head><title>Quản trị — Oecophylla</title></svelte:head>
<div class="admin-page"><header><div><p class="eyebrow">VẬN HÀNH NỘI DUNG</p><h1 class="serif">Tổng quan quản trị</h1><p>Theo dõi nội dung, cộng đồng và các báo cáo cần xử lý.</p></div><span class="admin-badge"><Icon name="Shield" size={17} /> Quản trị viên</span></header>
  <section class="workflow"><h2 class="serif">Quy trình vận hành nội dung</h2><p>Từ nguồn tin đến cộng đồng, mỗi bước đều hướng đến chất lượng thông tin.</p><div class="steps">{#each steps as step, i}<div class="step"><span class="step-icon"><Icon name={step.icon} size={20} /></span><strong>{step.name}</strong><small>{step.detail}</small><em>{i + 1}</em></div>{/each}</div></section>
  <section class="metrics" aria-label="Số liệu hoạt động"><div><Icon name="FileText" size={19} /><strong>{data.metrics?.posts_last_24h ?? '—'}</strong><span>Bài viết trong 24 giờ</span></div><div><Icon name="Book" size={19} /><strong>{data.metrics?.total_posts ?? '—'}</strong><span>Tổng bài viết</span></div><div><Icon name="AlertCircle" size={19} /><strong>{data.metrics?.pending_reports ?? '—'}</strong><span>Báo cáo chờ xử lý</span></div><div><Icon name="Users" size={19} /><strong>{data.metrics?.active_users_24h ?? '—'}</strong><span>Người dùng hoạt động</span></div></section>
  <section class="reports"><div class="section-head"><div><h2 class="serif">Báo cáo cần xem xét</h2><p>Các báo cáo từ cộng đồng đang chờ quyết định của quản trị viên.</p></div><span>{data.reports.length} báo cáo</span></div>{#if data.reports.length}<div class="report-list">{#each data.reports as report}<article><span class="report-icon"><Icon name="Flag" size={17} /></span><div><strong>{report.reason}</strong><p>{report.post_snippet ?? 'Bài viết được báo cáo'}</p><small>{new Intl.DateTimeFormat('vi-VN').format(new Date(report.created_at))} · {report.reporter_username ?? 'Thành viên'}</small></div><a class="pill-outline" href={'/post/' + report.post_id}>Xem bài viết</a></article>{/each}</div>{:else}<div class="empty"><Icon name="Check" size={22} /> Chưa có báo cáo cần xem xét.</div>{/if}</section>
</div>
<style>
  .admin-page { max-width: 1160px; margin: auto; padding: 30px 32px 60px; }
  header { display: flex; justify-content: space-between; align-items: center; gap: 20px; }
  h1 { margin: 8px 0 4px; font-size: 34px; font-weight: 500; letter-spacing: -.05em; }
  header p:last-child, .workflow > p, .section-head p { margin: 0; color: #7b8c83; font: 12px/1.6 'Lora', serif; }
  .admin-badge { display: flex; align-items: center; gap: 7px; padding: 9px 13px; border: 1px solid #bdd9cb; border-radius: 20px; color: #276a5d; background: #eff7f1; font-size: 11px; }
  .workflow { margin-top: 28px; padding: 20px; border: 1px solid #e7eeea; border-radius: 9px; background: white; }
  h2 { margin: 0 0 4px; font-size: 20px; font-weight: 500; }
  .steps { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 10px; margin-top: 22px; }
  .step { position: relative; display: grid; align-content: start; gap: 8px; min-height: 145px; padding: 15px; border: 1px solid #e7eeea; border-radius: 9px; background: #fbfdfb; }
  .step-icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: #e3f1e9; color: #1e6256; }
  .step strong { font: 600 12px 'Lora', serif; }
  .step small { color: #84958b; font-size: 10px; line-height: 1.5; }
  .step em { position: absolute; top: 20px; right: 15px; color: #98b8a7; font: 11px 'Lora', serif; }
  .metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 11px; margin-top: 13px; }
  .metrics div { display: grid; gap: 8px; padding: 18px; border: 1px solid #e7eeea; border-radius: 9px; background: white; color: #276a5c; }
  .metrics strong { color: #183d36; font: 600 24px 'Lora', serif; }
  .metrics span { color: #83958b; font-size: 10px; }
  .reports { margin-top: 28px; padding: 20px; border: 1px solid #e7eeea; border-radius: 9px; background: white; }
  .section-head { display: flex; justify-content: space-between; gap: 10px; }
  .section-head > span { align-self: start; padding: 7px 10px; border-radius: 20px; background: #eef4ef; color: #50796b; font-size: 10px; }
  .report-list { display: grid; gap: 0; margin-top: 15px; }
  .report-list article { display: flex; align-items: center; gap: 13px; padding: 13px 0; border-top: 1px solid #e9efea; }
  .report-icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 7px; background: #f8efe7; color: #9e6c3d; }
  article > div { flex: 1; }
  article strong { font: 600 12px 'Lora', serif; }
  article p { margin: 3px 0; color: #60776d; font-size: 11px; }
  article small { color: #94a39b; font-size: 10px; }
  .empty { display: flex; align-items: center; gap: 8px; margin-top: 16px; padding: 20px; border-radius: 7px; background: #f4f8f4; color: #548071; font-size: 12px; }
  @media (max-width: 1000px) { .steps { grid-template-columns: repeat(3, minmax(0,1fr)); } .metrics { grid-template-columns: repeat(2,minmax(0,1fr)); } }
  @media (max-width: 720px) { .admin-page { padding: 22px 14px 35px; } h1 { font-size: 27px; } .admin-badge { display: none; } .steps { grid-template-columns: repeat(2,minmax(0,1fr)); } .metrics { gap: 8px; } .metrics div { padding: 14px; } .report-list article { flex-wrap: wrap; } }
</style>
