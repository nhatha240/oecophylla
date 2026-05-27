<script lang="ts">
  import Badge from '../components/Badges.svelte';
  import Icon from '../components/Icon.svelte';
  import { POSTS, topicName } from '../data';
  import Chart from './Charts.svelte';

  export let page = 'overview';
  export let onJump: (page: string) => void = () => {};

  let selected = 0;
  let action = '';
  const modItems = [
    ['Bài viết về vacxin COVID có dấu hiệu sai lệch', 'Thông tin sai lệch', 'high', 12],
    ['Tài khoản giả mạo @vtcnews_real đăng tin giật gân', 'Tài khoản giả mạo', 'high', 8],
    ['Spam quảng cáo crypto trong nhóm Kinh tế Việt Nam', 'Spam', 'med', 4],
    ['Bình luận xúc phạm trong bài “Quy định nội dung AI”', 'Ngôn từ kích động', 'med', 5],
    ['Hình ảnh có dấu hiệu nhạy cảm chưa gắn nhãn', 'Nội dung nhạy cảm', 'low', 2]
  ];
  const kpis = [
    ['Tổng người dùng', '184.2K', '+2.4%'],
    ['Bài viết hôm nay', '3.812', '+12%'],
    ['Bài chờ duyệt', '142', '-8%'],
    ['Báo cáo vi phạm', '38', '+5'],
    ['Tỷ lệ tương tác', '6.8%', '+0.4pp'],
    ['Tỷ lệ bài bị ẩn', '1.2%', '-0.1pp']
  ];

  function doAction(label: string) {
    action = label;
    window.setTimeout(() => (action = ''), 1500);
  }
</script>

{#if page === 'overview'}
  <div class="admin-h"><div><h2>Tổng quan</h2><div class="sub">Sức khỏe của Oecophylla trong 7 ngày qua. Cập nhật lần cuối 3 phút trước.</div></div><div class="admin-h-actions"><div class="date-range"><Icon name="Clock" size={13} /> 7 ngày qua <Icon name="Chevron" size={11} /></div><button class="btn ghost sm"><Icon name="Refresh" size={13} /> Làm mới</button><button class="btn primary sm"><Icon name="FileText" size={13} /> Xuất báo cáo</button></div></div>
  <div class="kpi-grid">{#each kpis as kpi}<div class="kpi"><div class="label">{kpi[0]}</div><div class="value">{kpi[1]}</div><div class="delta up"><Icon name="ArrowUp" size={11} /> {kpi[2]} so với tuần trước</div></div>{/each}</div>
  <div class="chart-grid"><div class="chart-card"><div class="head"><div><h4>Xu hướng bài viết theo ngày</h4><div class="sub">Tổng bài đăng và bài được duyệt qua kiểm duyệt tự động.</div></div></div><Chart data={[42,58,51,64,72,68,81,75,92,88,96,110,102,121]} secondary={[38,50,47,55,60,58,64,62,71,68,70,78,75,88]} height={220} /></div><div class="chart-card"><div class="head"><div><h4>Phân bố chủ đề</h4><div class="sub">12.4K bài hôm nay</div></div></div><div style="display: flex; align-items: center; gap: 18px"><Chart kind="donut" /><div class="legend-list">{#each ['Công nghệ 32%','Kinh tế 22%','Đời sống 18%','AI 14%','Xã hội 8%','Khác 6%'] as item}<div>{item}</div>{/each}</div></div></div></div>
  <div class="chart-grid" style="margin-top: 16px"><div class="chart-card"><h4>Chất lượng đề xuất</h4><Chart kind="bars" max={8} items={[{label:'CTR feed',value:6.8,display:'6.8%'},{label:'Tỷ lệ lưu bài',value:4.2,display:'4.2%',color:'var(--azure-500)'},{label:'Tỷ lệ ẩn bài',value:1.2,display:'1.2%',color:'var(--rose-500)'},{label:'Thời gian đọc TB (s)',value:4.7,display:'128 giây',color:'var(--amber-500)'}]} /></div><div class="chart-card"><h4>Nội dung cần xử lý gấp</h4>{#each modItems.slice(0, 4) as item}<div class="urgent-row"><Badge kind="flagged" label="" /><div><div>{item[0]}</div><div class="t-meta">{item[3]} báo cáo · Rủi ro {item[2]}</div></div><button class="btn primary sm">Xem</button></div>{/each}</div></div>
{:else if page === 'mod' || page === 'flagged'}
  <div class="admin-h"><div><h2>Kiểm duyệt nội dung</h2><div class="sub">28 mục đang chờ. Ưu tiên theo rủi ro và số lượt báo cáo.</div></div><div class="admin-h-actions"><div class="date-range"><Icon name="Filter" size={13} /> Mọi lý do</div><button class="btn primary sm"><Icon name="Check" size={13} /> Duyệt nhanh đã chọn (5)</button></div></div>
  <div class="mod-grid"><div class="mod-list">{#each modItems as item, i}<button class={`mod-row mod-button ${selected === i ? 'selected' : ''}`} on:click={() => (selected = i)}><div><div class="lead"><span class={`risk ${item[2]}`}><Icon name="AlertCircle" size={10} /> Rủi ro {String(item[2]).toUpperCase()}</span>{item[0]}</div><div class="preview-line">Nội dung xem trước được hệ thống AI gắn nhãn và đưa vào hàng đợi kiểm duyệt.</div><div class="meta"><span>Người đăng · @demo</span><span>·</span><span>{item[3]} báo cáo</span><span>·</span><span><Badge kind="flagged" label={String(item[1])} /></span></div></div><Icon name="Chevron" size={14} /></button>{/each}</div><aside class="mod-detail"><h4>Phân tích AI</h4><p class="t-meta" style="margin: -4px 0 14px">Gắn nhãn tự động — admin xác nhận cuối cùng.</p><div class="mod-section"><div class="lab">Bài viết</div><div style="font-size: 14px; font-weight: 500">{modItems[selected][0]}</div></div><div class="mod-section"><div class="lab">Metadata</div><div class="mod-meter"><div class="row"><span>Độ nhạy cảm</span><b>72/100</b></div><div class="track"><div class="fill rose" style="width: 72%"></div></div></div><div class="mod-meter" style="margin-top: 10px"><div class="row"><span>Độ tin cậy</span><b>18/100</b></div><div class="track"><div class="fill rose" style="width: 18%"></div></div></div></div><div class="mod-section"><div class="lab">Hành động</div><div class="mod-actions"><button class="btn emerald sm" on:click={() => doAction('Đã duyệt bài viết')}><Icon name="Check" size={12} /> Duyệt</button><button class="btn ghost sm" on:click={() => doAction('Đã yêu cầu chỉnh sửa')}><Icon name="Edit" size={12} /> Yêu cầu sửa</button><button class="btn ghost sm" on:click={() => doAction('Đã ẩn bài viết')}><Icon name="EyeOff" size={12} /> Ẩn</button></div>{#if action}<div class="action-note"><Icon name="Check" size={14} /> {action}. Cập nhật trong bộ nhớ phiên.</div>{/if}</div></aside></div>
{:else if page === 'rec'}
  <div class="admin-h"><div><h2>Hiệu quả đề xuất</h2><div class="sub">Theo dõi chất lượng feed cá nhân hóa và chất lượng nội dung được đề xuất.</div></div><div class="admin-h-actions"><div class="date-range"><Icon name="Clock" size={13} /> 14 ngày qua</div><button class="btn ghost sm"><Icon name="Refresh" size={13} /> Làm mới</button></div></div>
  <div class="alert-card"><Icon name="AlertTriangle" size={18} /><div class="body"><strong>Cảnh báo: chủ đề “Crypto” đang được đề xuất tăng 68% so với tuần trước.</strong><p>Phần lớn nội dung đến từ 4 tài khoản chưa xác minh. Tỷ lệ báo cáo cao gấp 3 lần mức trung bình.</p></div><button class="btn ghost sm">Mở điều tra</button></div>
  <div class="kpi-grid" style="grid-template-columns: repeat(5, 1fr)">{#each ['Precision@10 72.4%','Recall@10 38.6%','CTR feed 6.8%','Tỷ lệ lưu bài 4.2%','Tỷ lệ ẩn bài 1.2%'] as item}<div class="kpi"><div class="label">{item.split(' ').slice(0,-1).join(' ')}</div><div class="value">{item.split(' ').at(-1)}</div><div class="delta up"><Icon name="ArrowUp" size={11} /> +0.4pp</div></div>{/each}</div>
  <div class="chart-grid"><div class="chart-card"><h4>CTR feed theo ngày</h4><Chart data={[62,64,61,66,68,70,67,72,70,74,71,73,75,74]} secondary={[38,40,39,41,42,43,40,44,43,45,42,45,47,46]} height={240} /></div><div class="chart-card"><h4>Theo nguồn đề xuất</h4><Chart kind="bars" max={100} items={[{label:'Theo sở thích cá nhân',value:78,display:'78%'},{label:'Theo người theo dõi',value:64,display:'64%'},{label:'Theo xu hướng',value:52,display:'52%'},{label:'Theo nhóm',value:47,display:'47%'}]} /></div></div>
  <div class="chart-card" style="margin-top: 16px"><h4>Top bài được đề xuất nhiều nhất tuần này</h4><table class="admin-table"><tbody>{#each POSTS as post, i}<tr><td>{i + 1}</td><td><b>{post.title}</b><div class="t-meta">{post.author.name}</div></td><td><span class="chip">{topicName(post.tags[0])}</span></td><td style="text-align: right">{120 - i * 12}K</td><td style="text-align: right"><Badge kind={i < 4 ? 'verified-src' : 'pending'} label={i < 4 ? 'Tốt' : 'Theo dõi'} /></td></tr>{/each}</tbody></table></div>
{:else}
  <div class="admin-h"><div><h2>Trang quản trị</h2><div class="sub">Màn hình này được phác thảo cho giai đoạn tiếp theo.</div></div></div>
  <div class="card card-pad admin-placeholder"><Icon name="Layers" size={28} className="muted" /><h3 class="serif">Trang này được phác thảo cho giai đoạn tiếp theo.</h3><p class="muted">Ba trang trọng tâm đang hoạt động: Tổng quan, Kiểm duyệt nội dung và Hiệu quả đề xuất.</p><div><button class="btn emerald sm" on:click={() => onJump('overview')}>Mở Tổng quan</button><button class="btn ghost sm" on:click={() => onJump('mod')}>Mở Kiểm duyệt</button><button class="btn ghost sm" on:click={() => onJump('rec')}>Mở Hiệu quả đề xuất</button></div></div>
{/if}

<style>
  .legend-list { flex: 1; display: flex; flex-direction: column; gap: 6px; font-size: 12px; }
  .urgent-row { display: flex; gap: 10px; padding: 10px; border-radius: 10px; background: var(--surface-2); align-items: center; margin-top: 10px; }
  .urgent-row > div { flex: 1; min-width: 0; font-size: 13px; font-weight: 500; }
  .mod-button { width: 100%; border: 0; color: inherit; text-align: left; }
  .action-note { margin-top: 12px; padding: 10px 12px; background: var(--emerald-50); color: var(--emerald-700); border-radius: 10px; font-size: 12.5px; display: flex; gap: 8px; align-items: center; }
  .admin-placeholder { padding: 40px; text-align: center; }
  .admin-placeholder h3 { font-weight: 500; font-size: 20px; margin: 12px 0 6px; }
  .admin-placeholder p { font-size: 14px; line-height: 1.5; max-width: 520px; margin: 0 auto 18px; }
  .admin-placeholder div { display: flex; gap: 8px; justify-content: center; }
</style>
