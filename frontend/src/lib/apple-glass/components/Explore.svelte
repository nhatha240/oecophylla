<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Icon from './Icon.svelte';
  import PostCard from './PostCard.svelte';
  import { AUTHORS, POSTS, type Post } from '../data';

  export let onOpenPost: (post: Post) => void = () => {};
  let filter = 'all';
  const filters = ['Tất cả', 'Tuần này', 'Phổ biến nhất', 'Nguồn đáng tin cậy', 'Có video', 'Bài dài'];
  const filterIds = ['all', 'week', 'pop', 'verified', 'video', 'long'];
</script>

<div class="explore-page" data-screen-label="06 Explore">
  <section class="explore-hero">
    <div class="blob"></div><div class="blob-2"></div>
    <span class="t-eyebrow" style="color: rgba(255,255,255,0.6)">Khám phá</span>
    <h1 style="margin-top: 6px">Tin tức, ý tưởng và cộng đồng <em>phù hợp với bạn</em></h1>
    <p>Tìm kiếm sâu hơn theo chủ đề, tác giả hoặc nhóm. Bộ lọc giúp bạn lọc theo độ tin cậy của nguồn và thời gian xuất bản.</p>
    <div class="search-big"><span class="icon"><Icon name="Search" size={18} /></span><input placeholder="Thử “Edge AI”, “lãi suất quý 3”, “@minhkhoa”…" /></div>
  </section>
  <div class="filter-row">
    {#each filters as item, i}
      <button class={`chip ${filter === filterIds[i] ? 'active' : ''}`} on:click={() => (filter = filterIds[i])}>{#if filter === filterIds[i]}<Icon name="Check" size={11} />{/if}{item}</button>
    {/each}
    <button class="chip outline" style="margin-left: auto"><Icon name="Filter" size={12} /> Bộ lọc nâng cao</button>
  </div>
  <div class="explore-grid">
    <div>
      <div class="section-title"><h3>Chủ đề đang tăng trưởng</h3><a class="link" href="/">Xem tất cả <Icon name="ArrowRight" size={12} /></a></div>
      <div class="topic-trends">
        {#each [
          ['AI tạo sinh', '2.4K bài · 14K tương tác hôm nay', '+34%'],
          ['An toàn thông tin', '1.1K bài · 8K tương tác hôm nay', '+22%'],
          ['Kinh tế số', '842 bài · 5K tương tác hôm nay', '+18%'],
          ['Edge AI', '432 bài · 3K tương tác hôm nay', '+62%']
        ] as trend}
          <div class="trend-card-lg"><div class="ph-img">CHỦ ĐỀ</div><div style="flex: 1"><h5>{trend[0]}</h5><div class="t-meta">{trend[1]}</div><div style="margin-top: 8px"><span class="delta"><Icon name="TrendUp" size={11} /> {trend[2]} so với tuần trước</span></div></div></div>
        {/each}
      </div>
      <div class="section-title"><h3>Bài viết nổi bật cho bạn</h3><a class="link" href="/">Đổi mới <Icon name="Refresh" size={12} /></a></div>
      {#each POSTS.slice(0, 3) as post (post.id)}
        <PostCard {post} onOpen={() => onOpenPost(post)} />
      {/each}
    </div>
    <aside class="explore-aside">
      <div class="rail-card"><h4><Icon name="Sparkle" size={16} className="pin" /> Chủ đề dành cho bạn</h4><p class="t-meta" style="margin: -6px 0 12px">Dựa trên 30 ngày đọc gần đây.</p><div class="chip-wrap">{#each ['AI có trách nhiệm','Edge AI','Khoa học dữ liệu','Báo chí số','Năng lượng tái tạo','Khởi nghiệp Việt','Edtech','Bảo mật'] as topic}<span class="chip active">+ {topic}</span>{/each}</div></div>
      <div class="rail-card"><h4><Icon name="Shield" size={16} className="pin" /> Nguồn tin đáng tin cậy</h4>{#each AUTHORS.filter((a) => a.verified).slice(0, 4) as author}<div class="author-row compact"><Avatar {author} size="s40" showVerified /><div class="meta"><div class="n">{author.name} <Icon name="Verified" size={12} style="color: var(--azure-500)" /></div><div class="s">{author.bio}</div></div></div>{/each}</div>
      <div class="rail-card"><h4><Icon name="Group" size={16} className="pin" /> Nhóm gợi ý</h4>{#each ['AI có trách nhiệm Vietnam','Báo chí Số','Edtech Builders'] as group}<div class="suggest-item"><span class="avatar s40 sq t-emerald"><Icon name="Group" size={18} /></span><div class="meta"><div class="n">{group}</div><div class="s">2.8K thành viên</div></div><button class="btn ghost sm">Tham gia</button></div>{/each}</div>
    </aside>
  </div>
</div>

<style>
  .topic-trends { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .explore-aside { display: flex; flex-direction: column; gap: 16px; }
  .chip-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
  .compact { border: 0; padding: 10px 0; margin: 0; background: transparent; }
</style>
