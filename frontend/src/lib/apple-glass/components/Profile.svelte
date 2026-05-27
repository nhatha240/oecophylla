<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Icon from './Icon.svelte';
  import PostCard from './PostCard.svelte';
  import ToggleRow from './ToggleRow.svelte';
  import { AUTHORS, POSTS, TASTE, topicName } from '../data';

  let tab = 'posts';
  let personalization = true;
  let showSensitive = false;
  let activityMix = true;
  const me = AUTHORS[0];
  const tabs = [
    ['posts', 'Bài viết', '42'],
    ['comments', 'Bình luận', '138'],
    ['saved', 'Đã lưu', '12'],
    ['groups', 'Nhóm', '7'],
    ['activity', 'Hoạt động', '']
  ];
</script>

<div class="profile-page" data-screen-label="07 Profile">
  <div class="profile-cover"></div>
  <div class="profile-head">
    <Avatar author={me} size="s120" showVerified />
    <div class="profile-meta">
      <h2>{me.name}<Icon name="Verified" size={18} style="color: var(--azure-500)" /></h2>
      <div class="handle">{me.handle} · Hà Nội</div>
      <p class="bio">Biên tập tin công nghệ, quan tâm AI có trách nhiệm và báo chí số tại Việt Nam. Viết về cách công nghệ thay đổi cách chúng ta đọc tin.</p>
      <div class="chips"><span class="chip active">AI</span><span class="chip active">Báo chí số</span><span class="chip active">Edu-tech</span><span class="chip outline">+ 4</span></div>
      <div class="profile-stats"><div><b>1.842</b> <span>người theo dõi</span></div><div><b>283</b> <span>đang theo dõi</span></div><div><b>42</b> <span>bài viết</span></div><div><b>7</b> <span>nhóm</span></div></div>
    </div>
    <div class="profile-head-actions"><button class="btn ghost"><Icon name="Share" size={14} /> Chia sẻ</button><button class="btn primary"><Icon name="Edit" size={14} /> Chỉnh sửa hồ sơ</button></div>
  </div>
  <div class="tabs" style="margin-top: 12px">{#each tabs as item}<button class={`tab ${tab === item[0] ? 'active' : ''}`} on:click={() => (tab = item[0])}>{item[1]} {#if item[2]}<span class="count-mini">{item[2]}</span>{/if}</button>{/each}</div>
  <div class="profile-grid">
    <div>
      {#if tab === 'posts'}
        {#each POSTS.slice(0, 2) as post}<PostCard post={{ ...post, author: me }} hideRecommend />{/each}
      {:else if tab === 'comments'}
        <div class="card card-pad">{#each POSTS.slice(0, 3) as post}<div class="profile-row"><div class="t-meta" style="margin-bottom: 4px">Bình luận trong: <b style="color: var(--ink)">{post.title}</b></div><div class="row-text">Cảm ơn nhóm đã làm khảo sát này. Có công bố dataset không ạ?</div></div>{/each}</div>
      {:else if tab === 'saved'}
        <div class="card-grid">{#each POSTS.slice(0, 4) as post}<div class="card card-pad"><div class="t-eyebrow" style="margin-bottom: 6px">{topicName(post.tags[0])}</div><div class="small-title">{post.title}</div><div class="t-meta">{post.author.name} · {post.time}</div></div>{/each}</div>
      {:else if tab === 'groups'}
        <div class="card-grid">{#each ['AI có trách nhiệm Vietnam','Báo chí Số','Edtech Builders','Khoa học mở'] as group}<div class="card card-pad group-card"><span class="avatar s56 sq t-emerald"><Icon name="Group" size={22} /></span><div><div style="font-weight: 600">{group}</div><div class="t-meta">2.000 thành viên · Bạn là quản trị</div></div></div>{/each}</div>
      {:else}
        <div class="card card-pad">{#each ['Bạn đã thích bài “Quy định mới về dán nhãn nội dung do AI tạo ra”','Bạn đã lưu bài “Tự host một mô hình 8B trên Mac Mini M4”','Bạn đã bình luận trong “Vì sao mô hình ngôn ngữ Việt Nam vẫn lệch”'] as item}<div class="activity-row"><span class="avatar s32 t-rose"><Icon name="HeartFill" size={14} /></span><div><div>{item}</div><div class="t-meta">Hôm qua</div></div></div>{/each}</div>
      {/if}
    </div>
    <aside class="profile-aside">
      <div class="taste-card">
        <h4>Hồ sơ sở thích</h4>
        <p class="hint">Các chủ đề Oecophylla nhận diện từ hành vi đọc của bạn.</p>
        <div class="taste-bars">{#each TASTE as taste}<div class="taste-bar"><div class="taste-bar-head"><span>{taste.topic}</span><span class="pct">{taste.pct}%</span></div><div class="taste-bar-track"><div class="taste-bar-fill" style={`width: ${taste.pct}%`}></div></div></div>{/each}</div>
        <button class="btn ghost sm" style="width: 100%; margin-top: 14px"><Icon name="Edit" size={12} /> Chỉnh sở thích</button>
      </div>
      <div class="taste-card"><h4>Kiểm soát cá nhân hóa</h4><p class="hint">Bạn quyết định mức độ thuật toán định hình bảng tin.</p><ToggleRow bind:value={personalization} name="Bật cá nhân hóa" desc="Tắt để chỉ thấy bài theo thời gian." /><ToggleRow bind:value={showSensitive} name="Hiển thị nội dung nhạy cảm" desc="Đã được kiểm duyệt và gắn nhãn." /><ToggleRow bind:value={activityMix} name="Trộn chủ đề ngoài sở thích" desc="Giúp tránh bong bóng thông tin." /></div>
      <div class="taste-card"><h4>Chủ đề đang ẩn</h4><p class="hint">Bạn đã chọn không xem các chủ đề này.</p><div class="chips"><span class="chip outline">Bóng đá <Icon name="X" size={10} /></span><span class="chip outline">Giải trí <Icon name="X" size={10} /></span><button class="chip outline" style="background: transparent"><Icon name="Plus" size={11} /> Thêm</button></div></div>
    </aside>
  </div>
</div>

<style>
  .chips { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
  .card-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .small-title { font: 500 17px/1.3 var(--font-serif); letter-spacing: -0.01em; margin-bottom: 8px; }
  .group-card, .activity-row { display: flex; gap: 12px; align-items: center; }
  .profile-row, .activity-row { padding: 14px 0; border-top: 1px solid var(--hairline); }
  .row-text { font-size: 14px; line-height: 1.55; }
  .profile-aside { display: flex; flex-direction: column; gap: 14px; }
</style>
