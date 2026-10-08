<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import MentionTextarea from '$lib/components/MentionTextarea.svelte';
  import MentionText from '$lib/components/MentionText.svelte';
  import PostImagePicker from '$lib/components/PostImagePicker.svelte';
  import { goto } from '$app/navigation';
  import { apiFetch, ApiException, uploadPostImage } from '$lib/api';
  import type { Post } from '$lib/types';
  export let form: { error?: string; content?: string } | null = null;
  let content = form?.content ?? '';
  let mediaUrl = '';
  let tags = '';
  let preview = false;
  let files: File[] = [];
  let imageError = '';
  let publishing = false;
  let uploadError = '';
  let createdPostId: string | null = null;
  let uploadedCount = 0;

  async function publish() {
    if (publishing) return;
    if (imageError) return;
    if (!content.trim()) { uploadError = 'Vui lòng nhập nội dung bài viết.'; return; }
    if (files.length + (mediaUrl.trim() ? 1 : 0) > 6) { uploadError = 'Một bài viết có tối đa 6 ảnh.'; return; }
    publishing = true;
    uploadError = '';
    try {
      if (!createdPostId) {
        const post = await apiFetch<Post>(fetch, '/posts', { method: 'POST', body: JSON.stringify({
          content: content.trim(), tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean),
          media_urls: mediaUrl.trim() ? [mediaUrl.trim()] : []
        }) });
        createdPostId = post.id;
      }
      for (let index = uploadedCount; index < files.length; index++) {
        await uploadPostImage(fetch, createdPostId, files[index]);
        uploadedCount = index + 1;
      }
      await goto('/post/' + createdPostId);
    } catch (error) {
      if (error instanceof ApiException && error.status === 401) { await goto('/login'); return; }
      uploadError = createdPostId
        ? 'Bài viết đã được tạo nhưng chưa tải hết ảnh. Nhấn Đăng bài viết để thử tải tiếp.'
        : 'Không thể đăng bài. Hãy kiểm tra nội dung và thử lại.';
    } finally {
      publishing = false;
    }
  }
</script>

<svelte:head><title>Viết bài — Oecophylla</title></svelte:head>
<div class="compose-page"><header><div><p class="eyebrow">CHIA SẺ GÓC NHÌN CỦA BẠN</p><h1 class="serif">Viết bài mới</h1><p>Những nội dung tốt đẹp hơn bắt đầu từ một góc nhìn chân thành.</p></div><a class="pill-outline" href="/">Quay lại bảng tin</a></header>
  <div class="compose-grid"><form method="POST" class="editor" on:submit|preventDefault={publish}><div class="editor-header"><Icon name="Edit" size={20} /><span>Bài viết của bạn</span><button type="button" on:click={() => preview = !preview}>{preview ? 'Chỉnh sửa' : 'Xem trước'}</button></div>
    {#if preview}<div class="preview serif">{#if content}<MentionText text={content} />{:else}Nội dung bài viết sẽ hiển thị ở đây.{/if}</div>{:else}<label for="content">Nội dung <span>*</span></label><MentionTextarea id="content" name="content" bind:value={content} rows={4} maxlength={4000} minHeight="130px" placeholder="Chia sẻ câu chuyện, góc nhìn hoặc thông tin mà bạn muốn lan tỏa..." required />{/if}
    <small>Gõ @ và ít nhất 2 ký tự để gắn tên người dùng trong bài viết.</small>
    {#if preview}<input type="hidden" name="content" value={content} />{/if}
    <label class="image-heading" for="post-images">Ảnh bài viết <span class="optional">(không bắt buộc)</span></label>
    <PostImagePicker bind:files existingUrls={mediaUrl.trim() ? [mediaUrl.trim()] : []}
      allowRemoveExisting={false} locked={!!createdPostId} bind:error={imageError} />
    <details class="image-url-option"><summary>Hoặc thêm ảnh bằng đường dẫn</summary><div class="field"><Icon name="Image" size={18} /><input id="media_url" name="media_url" type="url" bind:value={mediaUrl} placeholder="https://..." aria-label="Đường dẫn ảnh" /></div></details>
    <label for="tags">Thẻ chủ đề</label><div class="field"><Icon name="Tag" size={18} /><input id="tags" name="tags" bind:value={tags} placeholder="môi trường, giáo dục, cộng đồng" /></div><small>Phân tách các thẻ bằng dấu phẩy.</small>
    {#if form?.error || uploadError}<p class="error" role="alert">{uploadError || form?.error}</p>{/if}
    <button class="pill-primary publish" type="submit" disabled={publishing}><Icon name="Send" size={17} /> {publishing ? 'Đang đăng…' : 'Đăng bài viết'}</button>
  </form><aside><img src="/brand/street.jpg" alt="Góc phố Việt Nam" /><h2 class="serif">Viết để kết nối</h2><p>Một câu chuyện rõ ràng, nguồn tin đáng tin cậy và sự tôn trọng người đọc sẽ giúp cuộc thảo luận đi xa hơn.</p><div><Icon name="Shield" size={18} /> Nội dung cần tuân theo quy tắc cộng đồng.</div></aside></div>
</div>

<style>
  .compose-page { max-width: 1120px; margin: auto; padding: 32px 35px 60px; }
  header { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 25px; }
  h1 { margin: 8px 0; font-size: 35px; font-weight: 500; letter-spacing: -.05em; }
  header p:last-child { margin: 0; color: #73847d; font: 13px 'Lora', serif; }
  .compose-grid { display: grid; grid-template-columns: minmax(0,1fr) 245px; gap: 18px; }
  .editor, aside { padding: 24px; border: 1px solid #e5ede9; border-radius: 10px; background: white; }
  .editor { display: grid; align-content: start; gap: 11px; }
  .editor-header { display: flex; align-items: center; gap: 9px; padding-bottom: 14px; border-bottom: 1px solid #edf1ee; color: #1d5b54; font: 600 14px 'Lora', serif; }
  .editor-header button { margin-left: auto; border: 0; background: transparent; color: #1e635a; text-decoration: underline; font: 12px 'Lora', serif; }
  label { margin-top: 9px; font: 600 13px 'Lora', serif; }
  label span { color: #b34545; }
  .field:focus-within { border-color: #34796c; box-shadow: 0 0 0 3px #e3f1eb; }
  .field { display: flex; align-items: center; gap: 10px; height: 44px; padding: 0 13px; border: 1px solid #dfe8e3; border-radius: 7px; color: #51776d; }
  .field input { width: 100%; border: 0; outline: 0; background: transparent; font-size: 12px; }
  small { color: #8fa09a; }
  .publish { justify-self: start; margin-top: 10px; }
  .preview { min-height: 130px; padding: 15px; white-space: pre-wrap; border: 1px solid #dfe8e3; border-radius: 7px; line-height: 1.7; }
  .image-heading { margin-top: 13px; }
  .optional { color: #849b90; font-weight: 400; }
  .image-url-option { margin-bottom: 5px; }
  .image-url-option summary { width: fit-content; color: #55796c; font-size: 12px; cursor: pointer; }
  .image-url-option .field { margin-top: 9px; }
  .error { color: #a33f43; font-size: 12px; }
  aside { align-self: start; }
  aside img { width: 100%; height: 138px; object-fit: cover; border-radius: 6px; }
  aside h2 { margin: 14px 0 8px; font-size: 19px; font-weight: 500; }
  aside p { color: #6d8078; font: 12px/1.7 'Lora', serif; }
  aside div { display: flex; gap: 8px; margin-top: 20px; padding-top: 17px; border-top: 1px solid #e9efeb; color: #52776d; font-size: 11px; }
  @media (max-width: 850px) { .compose-grid { display: block; } aside { display: none; } }
  @media (max-width: 720px) { .compose-page { padding: 20px 14px 35px; } header { display: block; } header .pill-outline { margin-top: 14px; } h1 { font-size: 29px; } .editor { padding: 17px; } }
</style>
