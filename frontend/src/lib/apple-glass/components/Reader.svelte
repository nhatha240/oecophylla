<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Badge from './Badges.svelte';
  import Comment from './Comment.svelte';
  import Icon from './Icon.svelte';
  import { AUTHORS, POSTS, topicName, type Post } from '../data';

  export let post: Post | null = null;
  export let onBack: () => void = () => {};
  export let toast: (message: string) => void = () => {};

  let liked = false;
  let saved = false;
  let followed = false;
  let commentSort = 'relevant';

  $: author = post?.author;
</script>

{#if post && author}
  <div class="reader" data-screen-label="05 Article Reader">
    <div class="crumbs">
      <button class="link-button" on:click={onBack} style="color: var(--muted)"><Icon name="ArrowLeft" size={12} style="vertical-align: -2px" /> Quay lại bảng tin</button>
      · <span>{topicName(post.tags[0])}</span>
    </div>

    <div style="display: flex; gap: 8px; margin-bottom: 16px; align-items: center; flex-wrap: wrap">
      <Badge kind={post.moderation} label={post.moderationLabel} />
      <span class="t-meta"><Icon name="Clock" size={12} style="vertical-align: -2px" /> 8 phút đọc</span>
      <span class="t-meta">· {post.time} · {post.stats.reads} lượt đọc</span>
    </div>

    <h1>{post.title}</h1>
    <p class="dek">{post.summary}</p>

    <div class="meta-row">
      <Avatar {author} size="s56" showVerified />
      <div style="flex: 1">
        <div style="display: flex; align-items: center; gap: 6px; font-weight: 600">
          {author.name}
          {#if author.verified}<Icon name="Verified" size={14} style="color: var(--azure-500)" />{/if}
        </div>
        <div class="t-meta">{author.handle} · {author.bio}</div>
      </div>
      <button class={`btn ${followed ? 'ghost' : 'emerald'} sm`} on:click={() => (followed = !followed)}>{followed ? 'Đang theo dõi' : '+ Theo dõi'}</button>
    </div>

    {#if post.image}<div class="ph-img" style="width: 100%; aspect-ratio: 16/9; border-radius: 14px; margin-bottom: 28px">ẢNH MINH HỌA · 16:9</div>{/if}

    <div class="body">
      <p>Trong sáu tháng qua, nhóm đánh giá độc lập của Đại học Bách khoa Hà Nội đã thử nghiệm 12 mô hình ngôn ngữ lớn phổ biến với một bộ dữ liệu kiểm thử riêng gồm 4.200 câu hội thoại có yếu tố địa phương. Kết quả khá bất ngờ: mặc dù điểm tổng thể trên các benchmark quốc tế khá cao, các mô hình này vẫn “lệch” khi xử lý từ ngữ vùng Bắc Trung Bộ và Tây Nguyên.</p>
      <p>Lỗi không nằm ở khả năng nhận diện ký tự, mà ở việc gán ngữ nghĩa. Các từ như “mô”, “tê”, “răng”, “rứa” thường bị gán sai vai trò trong câu, dẫn đến phản hồi mất ngữ cảnh. Trên một số tác vụ tóm tắt, độ chính xác giảm hơn 23% so với cùng một câu được viết theo chuẩn miền Bắc.</p>
      <h2>Vấn đề không chỉ là dữ liệu</h2>
      <p>Nhiều người sẽ nghĩ ngay đến chuyện thiếu dữ liệu huấn luyện. Đúng — nhưng chưa đủ. TS. Lê Minh Tuấn, người dẫn dắt nhóm, cho rằng phần lớn lỗi đến từ cách các mô hình được tinh chỉnh ưu tiên ngôn ngữ chuẩn báo chí, vốn nghiêng về phương ngữ miền Bắc, trong giai đoạn fine-tuning.</p>
      <blockquote>“Khi 80% dữ liệu tinh chỉnh là báo chí, chúng ta vô tình dạy mô hình rằng một số phương ngữ ‘không trang trọng đủ’.”</blockquote>
    </div>

    <div class="why-card">
      <h4><Icon name="Sparkle" size={14} /> Vì sao bạn thấy bài viết này?</h4>
      <p>Bạn đã đọc 11 bài về AI trong 30 ngày qua và tương tác nhiều với chủ đề <b>“AI có trách nhiệm”</b>. Bài viết này có nguồn được xác minh, độ tin cậy cao và đang nhận phản hồi tích cực từ cộng đồng mà bạn theo dõi.</p>
      <div class="why-tags"><span class="chip active">AI có trách nhiệm</span><span class="chip active">Khoa học dữ liệu</span><span class="chip outline">Tiếng Việt tự nhiên</span></div>
    </div>

    <div class="reader-actions">
      <button class={`post-action like ${liked ? 'active' : ''}`} on:click={() => { liked = !liked; toast(liked ? 'Đã thích.' : 'Đã bỏ thích.'); }}>
        <Icon name={liked ? 'HeartFill' : 'Heart'} size={16} /> {post.stats.likes + (liked ? 1 : 0)} lượt thích
      </button>
      <button class="post-action"><Icon name="Comment" size={16} /> {post.stats.comments} bình luận</button>
      <button class="post-action"><Icon name="Share" size={16} /> Chia sẻ</button>
      <button class={`post-action save ${saved ? 'active' : ''}`} on:click={() => { saved = !saved; toast(saved ? 'Đã lưu.' : 'Đã bỏ lưu.'); }}>
        <Icon name={saved ? 'BookmarkFill' : 'Bookmark'} size={16} /> {saved ? 'Đã lưu' : 'Lưu'}
      </button>
      <span style="flex: 1"></span>
      <button class="post-action"><Icon name="Flag" size={16} /> Báo cáo</button>
    </div>

    <h3 class="serif comments-title">
      {post.stats.comments} bình luận
      <span style="display: inline-flex; gap: 4px; font-size: 13px">
        <button class={`btn sm ${commentSort === 'relevant' ? 'primary' : ''}`} on:click={() => (commentSort = 'relevant')}>Liên quan nhất</button>
        <button class={`btn sm ${commentSort === 'new' ? 'primary' : ''}`} on:click={() => (commentSort = 'new')}>Mới nhất</button>
      </span>
    </h3>

    <div class="composer" style="margin-bottom: 24px">
      <Avatar author={AUTHORS[0]} size="s40" />
      <div class="right">
        <textarea placeholder="Viết bình luận của bạn… (lịch sự, có dẫn chứng nếu có thể)" rows="2"></textarea>
        <div class="composer-foot">
          <span class="t-meta">Bình luận sẽ hiển thị công khai. Hành vi quấy rối sẽ bị ẩn tự động.</span>
          <button class="btn emerald sm" style="margin-left: auto">Đăng bình luận</button>
        </div>
      </div>
    </div>

    <Comment author={AUTHORS[3]} time="12 phút trước" body="Bài viết phân tích cân bằng. Một câu hỏi: nhóm có thử kiểm tra với fine-tuning bằng dữ liệu cộng đồng chưa? Có thể bù lệch nhanh hơn là chờ data sạch." />
    <Comment author={AUTHORS[5]} time="40 phút trước" body="“Báo chí chuẩn” không có lỗi gì, nhưng nếu trở thành tiêu chuẩn duy nhất cho fine-tuning thì đúng là vấn đề. Vote cho ý này." />

    <h3 class="serif" style="font-weight: 500; font-size: 22px; margin: 40px 0 12px">Bài viết liên quan</h3>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px">
      {#each POSTS.slice(1, 3) as related}
        <button class="card card-pad related-card" on:click={onBack}>
          <div class="t-eyebrow" style="margin-bottom: 6px">{topicName(related.tags[0])}</div>
          <div class="related-title">{related.title}</div>
          <div class="t-meta">{related.author.name} · {related.time}</div>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .link-button,
  .related-card {
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
  }
  .comments-title {
    font-weight: 500;
    font-size: 22px;
    margin: 32px 0 12px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .related-title {
    font: 500 17px var(--font-serif);
    letter-spacing: -0.01em;
    line-height: 1.25;
    margin-bottom: 8px;
  }
</style>
