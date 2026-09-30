<script lang="ts">
  import type { PageData } from './$types';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let data: PageData;
</script>
<svelte:head><title>Quản lý bài viết — Oecophylla</title></svelte:head>
<section class="manage-page"><header><div><p class="eyebrow">NỘI DUNG CỦA BẠN</p><h1 class="serif">Quản lý bài viết</h1><p>Tạo và xem lại những nội dung bạn đã chia sẻ cùng Oecophylla.</p></div><a class="pill-primary" href="/post/new"><Icon name="Plus" size={17} /> Viết bài mới</a></header><div class="summary"><span>Bài đã xuất bản</span><strong>{data.posts.length}</strong></div>
  {#if data.posts.length}<div class="table-wrap"><table><thead><tr><th>Bài viết</th><th>Trạng thái</th><th>Ngày cập nhật</th><th>Lượt xem</th><th>Thao tác</th></tr></thead><tbody>{#each data.posts as post}<tr><td><a class="title" href={'/post/' + post.id}>{#if post.media_urls?.[0]}<img src={post.media_urls[0]} alt="" />{:else}<span class="no-image"><Icon name="FileText" size={20} /></span>{/if}<span>{post.content.slice(0, 85)}{post.content.length > 85 ? '…' : ''}</span></a></td><td><span class="status">Đã đăng</span></td><td>{new Intl.DateTimeFormat('vi-VN').format(new Date(post.updated_at))}</td><td>{post.view_count}</td><td><a class="view" href={'/post/' + post.id} aria-label="Xem bài viết"><Icon name="Eye" size={17} /></a></td></tr>{/each}</tbody></table></div>{:else}<div class="empty"><Icon name="FileText" size={27} /><h2 class="serif">Bạn chưa đăng bài viết nào</h2><p>Hãy chia sẻ góc nhìn đầu tiên của mình với cộng đồng.</p><a class="pill-outline" href="/post/new">Bắt đầu viết</a></div>{/if}
</section>
<style>
  .manage-page { max-width: 1120px; margin: auto; padding: 31px 32px 60px; }
  header { display: flex; justify-content: space-between; align-items: center; gap: 20px; }
  h1 { margin: 8px 0 5px; font-size: 35px; font-weight: 500; letter-spacing: -.05em; }
  header p:last-child { margin: 0; color: #77887f; font: 12px 'Lora', serif; }
  .summary { display: flex; align-items: center; gap: 10px; width: fit-content; margin: 25px 0 15px; padding: 11px 16px; border: 1px solid #e4ece7; border-radius: 8px; color: #4e7468; background: #f2f7f3; font-size: 11px; }
  .summary strong { color: #1a554a; font: 600 16px 'Lora', serif; }
  .table-wrap { overflow: auto; border: 1px solid #e6eee9; border-radius: 9px; background: white; }
  table { width: 100%; border-collapse: collapse; text-align: left; }
  th { padding: 15px; border-bottom: 1px solid #e6eee9; color: #6e8578; background: #fafcfb; font-size: 10px; font-weight: 600; white-space: nowrap; }
  td { padding: 13px 15px; border-bottom: 1px solid #edf1ee; color: #627b6e; font-size: 11px; white-space: nowrap; }
  tr:last-child td { border: 0; }
  .title { display: flex; align-items: center; gap: 10px; min-width: 270px; max-width: 450px; color: #203f36; white-space: normal; font: 500 12px/1.5 'Lora', serif; }
  .title img, .no-image { flex: 0 0 54px; width: 54px; height: 47px; object-fit: cover; border-radius: 5px; }
  .no-image { display: grid; place-items: center; color: #648b7c; background: #edf5ef; }
  .status { padding: 6px 9px; border-radius: 20px; color: #1b6e50; background: #e5f5eb; font-size: 10px; }
  .view { display: grid; place-items: center; width: 30px; height: 30px; border: 1px solid #dce8e1; border-radius: 6px; color: #326e5e; }
  .view:hover { background: #eef7f0; }
  .empty { display: grid; justify-items: center; gap: 12px; padding: 62px 20px; border: 1px solid #e8eee9; border-radius: 9px; background: white; text-align: center; color: #4a7d6b; }
  .empty h2, .empty p { margin: 0; }
  .empty h2 { font-size: 21px; font-weight: 500; }
  .empty p { color: #84998b; font-size: 12px; }
  @media (max-width: 720px) { .manage-page { padding: 22px 14px 35px; } h1 { font-size: 28px; } header { align-items: start; } header .pill-primary { flex: 0 0 auto; padding: 0 11px; font-size: 10px; } }
</style>
