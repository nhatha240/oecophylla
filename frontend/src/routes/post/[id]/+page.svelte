<script lang="ts">
  import type { PageData } from './$types';
  import type { Comment, ReportReason } from '$lib/types';
  import { apiFetch } from '$lib/api';
  import { createComment, deleteComment, reportPost, type CommentReceipt } from '$lib/discussion';
  import { detailReadTracker } from '$lib/actions/detailReadTracker';
  import { isRecommendationTelemetryEnabled, recommendationLabelVersion, recommendationQualifiedReadMs } from '$lib/telemetry/config';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import CommentCard from '$lib/components/CommentCard.svelte';
  import DeleteCommentDialog from '$lib/components/DeleteCommentDialog.svelte';
  import MentionText from '$lib/components/MentionText.svelte';
  import MentionTextarea from '$lib/components/MentionTextarea.svelte';
  export let data: PageData;
  let liked = data.me?.liked ?? false;
  let saved = data.me?.saved ?? false;
  let shared = data.me?.shared ?? false;
  let likeCount = data.post.like_count;
  let commentCount = data.post.comment_count;
  let comments: Comment[] = data.comments;
  let comment = '';
  let replyingTo: string | null = null;
  let reply = '';
  let expandedReplies: Record<string, Comment[]> = {};
  let reportOpen = false;
  let reported = data.me?.reported_pending ?? false;
  let reportReason: ReportReason = 'spam';
  let reportDetail = '';
  let busy = false;
  let feedback = '';
  let discussionFeedback = '';
  let pendingDelete: Comment | null = null;
  let deleting = false;
  let deleteError = '';
  let commentsRefreshVersion = 0;
  const repliesRefreshVersions: Record<string, number> = {};
  $: authorName = data.author?.display_name || data.author?.username || 'Thành viên Oecophylla';
  function createdComment(receipt: CommentReceipt, content: string): Comment | null {
    const author = data.user;
    if (!author) return null;
    return {
      id: receipt.id, post_id: data.post.id, author_id: author.id,
      author_username: author.username, author_display_name: author.display_name,
      parent_comment_id: receipt.parent_comment_id, content, is_deleted: false,
      created_at: new Date().toISOString(), replies: [], reply_count: 0, has_more_replies: false
    };
  }
  async function toggle(kind: 'like' | 'save') {
    if (busy) return;
    busy = true; feedback = '';
    const wasOn = kind === 'like' ? liked : saved;
    try { await apiFetch(fetch, '/posts/' + data.post.id + '/' + kind, { method: wasOn ? 'DELETE' : 'POST' }); if (kind === 'like') { liked = !liked; likeCount += liked ? 1 : -1; } else saved = !saved; }
    catch { feedback = 'Không thể cập nhật tương tác.'; }
    finally { busy = false; }
  }
  async function submitComment() {
    if (!comment.trim() || busy) return;
    busy = true; discussionFeedback = '';
    let created: Comment | null = null;
    try {
      const content = comment.trim();
      const receipt = await createComment(fetch, data.post.id, content);
      created = createdComment(receipt, content);
      comment = ''; commentCount += 1;
      if (created) comments = [...comments, created];
    }
    catch { discussionFeedback = 'Không thể gửi bình luận. Vui lòng thử lại.'; return; }
    finally { busy = false; }
    // Reading the updated list must not lock the next submission.
    try { await refreshComments(created); }
    catch { discussionFeedback = 'Đã gửi bình luận. Tải lại trang để xem nội dung mới.'; }
  }
  async function refreshComments(ensure?: Comment | null): Promise<void> {
    const version = ++commentsRefreshVersion;
    const fresh = await apiFetch<Comment[]>(fetch, '/posts/' + data.post.id + '/comments?limit=100');
    if (version !== commentsRefreshVersion) return;
    comments = ensure && !fresh.some((item) => item.id === ensure.id) ? [...fresh, ensure] : fresh;
  }
  async function loadReplies(parentId: string, ensure?: Comment | null): Promise<void> {
    const version = (repliesRefreshVersions[parentId] ?? 0) + 1;
    repliesRefreshVersions[parentId] = version;
    const replies = await apiFetch<Comment[]>(fetch, `/comments/${parentId}/replies?limit=100`);
    if (version !== repliesRefreshVersions[parentId]) return;
    expandedReplies = { ...expandedReplies, [parentId]: ensure && !replies.some((item) => item.id === ensure.id) ? [...replies, ensure] : replies };
  }
  async function submitReply(parentId: string): Promise<void> {
    if (!reply.trim() || busy) return;
    busy = true; discussionFeedback = '';
    let created: Comment | null = null;
    try {
      const content = reply.trim();
      const receipt = await createComment(fetch, data.post.id, content, parentId);
      created = createdComment(receipt, content);
      reply = ''; replyingTo = null;
      if (created) expandedReplies = { ...expandedReplies, [parentId]: [...(expandedReplies[parentId] ?? comments.find((item) => item.id === parentId)?.replies ?? []), created] };
    } catch { discussionFeedback = 'Không thể gửi câu trả lời. Vui lòng thử lại.'; return; }
    finally { busy = false; }
    try { await refreshComments(); await loadReplies(parentId, created); }
    catch { discussionFeedback = 'Đã gửi câu trả lời. Tải lại trang để xem nội dung mới.'; }
  }
  function askToDelete(item: Comment): void {
    if (busy) return;
    pendingDelete = item;
    deleteError = '';
  }
  function cancelDelete(): void {
    if (deleting) return;
    pendingDelete = null;
    deleteError = '';
  }
  async function removeComment(): Promise<void> {
    const item = pendingDelete;
    if (!item || busy || deleting) return;
    busy = true; deleting = true; deleteError = ''; discussionFeedback = '';
    try {
      await deleteComment(fetch, item.id);
      pendingDelete = null;
      if (!item.parent_comment_id) commentCount = Math.max(0, commentCount - 1);
      comments = item.parent_comment_id
        ? comments.map((parent) => ({ ...parent, replies: parent.replies?.filter((child) => child.id !== item.id) }))
        : comments.filter((parent) => parent.id !== item.id);
      if (item.parent_comment_id && expandedReplies[item.parent_comment_id]) {
        expandedReplies = { ...expandedReplies, [item.parent_comment_id]: expandedReplies[item.parent_comment_id].filter((child) => child.id !== item.id) };
      }
      try {
        await refreshComments();
        if (item.parent_comment_id && expandedReplies[item.parent_comment_id]) await loadReplies(item.parent_comment_id);
        discussionFeedback = 'Đã xóa bình luận.';
      } catch { discussionFeedback = 'Đã xóa bình luận. Tải lại trang để cập nhật danh sách.'; }
    } catch { deleteError = 'Không thể xóa bình luận. Vui lòng thử lại.'; }
    finally { busy = false; deleting = false; }
  }
  async function showReplies(parentId: string): Promise<void> {
    if (busy) return;
    busy = true; discussionFeedback = '';
    try { await loadReplies(parentId); }
    catch { discussionFeedback = 'Không thể tải câu trả lời.'; }
    finally { busy = false; }
  }
  async function submitReport(): Promise<void> {
    if (busy || reported) return;
    busy = true; feedback = '';
    try {
      await reportPost(fetch, data.post.id, reportReason, reportDetail);
      reported = true; reportOpen = false; reportDetail = '';
      feedback = 'Đã gửi báo cáo. Cảm ơn bạn đã giúp cộng đồng an toàn hơn.';
    } catch { feedback = 'Không thể gửi báo cáo. Vui lòng thử lại.'; }
    finally { busy = false; }
  }
  async function share() {
    try {
      await navigator.clipboard.writeText(location.href);
    } catch {
      feedback = 'Không thể sao chép liên kết.';
      return;
    }
    if (!shared) {
      try {
        await apiFetch(fetch, '/posts/' + data.post.id + '/share', { method: 'POST' });
        shared = true;
      } catch {
        feedback = 'Đã sao chép liên kết, nhưng chưa ghi nhận lượt chia sẻ.';
        return;
      }
    }
    feedback = 'Đã sao chép liên kết.';
  }
</script>

<svelte:head><title>Bài viết — Oecophylla</title></svelte:head>
<div class="article-page"><article><nav class="breadcrumbs"><a href="/">Trang chủ</a><Icon name="Chevron" size={13} /><span>Bài viết</span></nav><div class="reading-region" use:detailReadTracker={{ postId: data.post.id, userId: data.user?.id, enabled: isRecommendationTelemetryEnabled(), labelVersion: recommendationLabelVersion(), qualifiedReadMs: recommendationQualifiedReadMs() }}><p class="eyebrow">{data.post.topics?.[0] ?? data.post.tags?.[0] ?? 'CỘNG ĐỒNG'} · {new Intl.DateTimeFormat('vi-VN').format(new Date(data.post.created_at))}</p><h1 class="serif">{data.post.content.slice(0, 135)}{data.post.content.length > 135 ? '…' : ''}</h1><div class="author"><a class="avatar" href={'/profile/' + data.post.author_id}>{#if data.author?.avatar_url}<img src={data.author.avatar_url} alt="" />{:else}{authorName.slice(0,1).toUpperCase()}{/if}</a><div><a href={'/profile/' + data.post.author_id}>{authorName}</a><small>@{data.author?.username ?? 'oecophylla'}</small></div></div>
    {#if data.post.media_urls?.length}<div class="article-images">{#each data.post.media_urls as image, index}<img class="article-image" src={image} alt={'Ảnh bài viết ' + (index + 1)} />{/each}</div>{/if}
    <div class="body-copy serif"><MentionText text={data.post.content} /></div>
    </div>
    {#if data.post.tags?.length}<div class="tags">{#each data.post.tags as tag}<a href={'/search?q=' + encodeURIComponent(tag)}>#{tag}</a>{/each}</div>{/if}
    <div class="actions"><button class:active={liked} disabled={busy} on:click={() => toggle('like')} aria-label="Thích bài viết"><Icon name={liked ? 'HeartFill' : 'Heart'} size={19} /> {likeCount}</button><a href="#comments"><Icon name="Comment" size={19} /> {commentCount}</a><button on:click={share}><Icon name="Share" size={19} /> Chia sẻ</button><button class:active={saved} disabled={busy} on:click={() => toggle('save')}><Icon name={saved ? 'BookmarkFill' : 'Bookmark'} size={19} /> {saved ? 'Đã lưu' : 'Lưu'}</button><button class:active={reported} disabled={busy || reported} on:click={() => reportOpen = !reportOpen}><Icon name="Flag" size={17} /> {reported ? 'Đã báo cáo' : 'Báo cáo'}</button></div>
    {#if reportOpen && !reported}
      <form class="report-form" on:submit|preventDefault={submitReport}>
        <label for="report-reason">Lý do báo cáo</label>
        <select id="report-reason" bind:value={reportReason}><option value="spam">Spam hoặc quảng cáo</option><option value="misinformation">Thông tin sai lệch</option><option value="harassment">Quấy rối</option><option value="nsfw">Nội dung không phù hợp</option><option value="other">Lý do khác</option></select>
        <label for="report-detail">Mô tả thêm (nếu có)</label>
        <textarea id="report-detail" bind:value={reportDetail} maxlength="1000" rows="3" placeholder="Cho chúng tôi biết thêm về vấn đề..."></textarea>
        <div class="report-buttons"><button type="button" class="pill-outline" on:click={() => reportOpen = false}>Hủy</button><button type="submit" class="pill-primary" disabled={busy}>Gửi báo cáo</button></div>
      </form>
    {/if}
    {#if feedback}<p class="feedback" role="status">{feedback}</p>{/if}
  </article>
  <section class="discussion" id="comments">
    <h2 class="serif">Thảo luận ({commentCount})</h2>
    {#if discussionFeedback}<p class="feedback" role="status">{discussionFeedback}</p>{/if}
    <form class="comment-form" on:submit|preventDefault={submitComment}>
      <MentionTextarea bind:value={comment} maxlength={2000} rows={3} placeholder="Viết bình luận của bạn..." ariaLabel="Bình luận" />
      <small>Gõ @ và ít nhất 2 ký tự để gắn tên người dùng.</small>
      <button type="submit" class="pill-primary" disabled={busy || !comment.trim()}>Gửi bình luận <Icon name="ArrowRight" size={15} /></button>
    </form>
    <div class="comments">
      {#each comments as item (item.id)}
        <div class="thread">
          <CommentCard {item} currentUserId={data.user?.id} isAdmin={data.user?.role === 'admin'} canReply
            disabled={busy} onReply={() => { replyingTo = replyingTo === item.id ? null : item.id; reply = ''; }} onDelete={() => askToDelete(item)} />
          {#if replyingTo === item.id}
            <form class="reply-form" on:submit|preventDefault={() => submitReply(item.id)}>
              <MentionTextarea bind:value={reply} maxlength={2000} rows={2} placeholder={'Trả lời @' + item.author_username + '...'} ariaLabel={'Trả lời ' + item.author_username} />
              <div class="reply-buttons"><button type="button" on:click={() => replyingTo = null}>Hủy</button><button type="submit" class="pill-primary" disabled={busy || !reply.trim()}>Gửi trả lời</button></div>
            </form>
          {/if}
          {#if (expandedReplies[item.id] ?? item.replies ?? []).length}<div class="replies">{#each expandedReplies[item.id] ?? item.replies ?? [] as child (child.id)}<CommentCard item={child} currentUserId={data.user?.id} isAdmin={data.user?.role === 'admin'} disabled={busy} onDelete={() => askToDelete(child)} />{/each}</div>{/if}
          {#if item.has_more_replies && !expandedReplies[item.id]}<button type="button" class="more-replies" disabled={busy} on:click={() => showReplies(item.id)}>Xem thêm câu trả lời ({item.reply_count})</button>{/if}
        </div>
      {:else}<p class="muted">Hãy bắt đầu cuộc thảo luận đầu tiên.</p>{/each}
    </div>
  </section>
</div>

<DeleteCommentDialog item={pendingDelete} busy={deleting} error={deleteError} onCancel={cancelDelete} onConfirm={removeComment} />

<style>
  .article-page { display: grid; grid-template-columns: minmax(0,1.4fr) minmax(280px,.8fr); gap: 30px; max-width: 1180px; margin: auto; padding: 32px 35px 60px; }
  article { min-width: 0; }
  .breadcrumbs { display: flex; align-items: center; gap: 8px; margin-bottom: 25px; color: #86968f; font-size: 11px; }
  .breadcrumbs a:hover { color: #1d5b54; }
  h1 { margin: 10px 0 20px; font-size: clamp(31px, 3vw, 45px); font-weight: 500; line-height: 1.24; letter-spacing: -.05em; }
  .author { display: flex; gap: 10px; align-items: center; margin-bottom: 23px; }
  .avatar { width: 38px; height: 38px; display: grid; place-items: center; overflow: hidden; border-radius: 50%; background: #dcece5; color: #1d5b54; font: 600 17px 'Lora', serif; }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .author div { display: grid; gap: 3px; font: 600 12px 'Lora', serif; }
  .author small { color: #91a19a; font: 10px 'Be Vietnam Pro', sans-serif; }
  .article-image { display: block; width: 100%; max-height: 460px; object-fit: cover; border-radius: 8px; }
  .article-images { display: grid; gap: 12px; }
  .body-copy { margin-top: 23px; white-space: pre-wrap; font-size: 16px; line-height: 1.9; color: #304b43; }
  .tags { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 22px; }
  .tags a { padding: 7px 12px; border-radius: 20px; background: #edf4ef; color: #396c61; font-size: 11px; }
  .actions { display: flex; flex-wrap: wrap; gap: 14px 23px; padding: 18px 0; margin-top: 20px; border-top: 1px solid #e8eeeb; border-bottom: 1px solid #e8eeeb; }
  .actions a, .actions button { display: inline-flex; align-items: center; gap: 7px; padding: 0; border: 0; background: transparent; color: #56776d; font-size: 12px; }
  .actions .active { color: #19635a; }
  .feedback { color: #527a70; font-size: 12px; }
  .report-form { display: grid; gap: 9px; margin-top: 14px; padding: 16px; border: 1px solid #e6eee9; border-radius: 9px; background: #fafcfb; }
  .report-form label { font-size: 11px; font-weight: 600; color: #3e6258; }
  .report-form select, .report-form textarea { width: 100%; padding: 10px 12px; border: 1px solid #dfe8e3; border-radius: 7px; background: white; color: #304b43; font-size: 12px; }
  .report-buttons, .reply-buttons { display: flex; justify-content: flex-end; align-items: center; gap: 9px; }
  .discussion { padding-left: 25px; border-left: 1px solid #edf1ee; }
  .discussion h2 { margin: 5px 0 20px; font-size: 21px; font-weight: 500; }
  .comment-form, .reply-form { display: grid; justify-items: end; gap: 9px; }
  .comment-form small { justify-self: start; color: #8ca099; font-size: 10px; }
  .comments { display: grid; gap: 18px; margin-top: 25px; }
  .thread { min-width: 0; padding-bottom: 17px; border-bottom: 1px solid #edf1ee; }
  .reply-form, .replies { margin: 12px 0 0 42px; }
  .replies { display: grid; gap: 14px; padding-left: 12px; border-left: 2px solid #e5eee9; }
  .reply-buttons button:not(.pill-primary), .more-replies { border: 0; background: transparent; color: #39776b; font-size: 11px; cursor: pointer; }
  .more-replies { margin: 10px 0 0 42px; padding: 0; }
  @media (max-width: 900px) { .article-page { display: block; } .discussion { margin-top: 40px; padding: 0; border: 0; } }
  @media (max-width: 720px) { .article-page { padding: 22px 17px 40px; } h1 { font-size: 28px; } .actions { gap: 14px; } .actions a, .actions button { font-size: 10px; } }
</style>
