<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let form: { error?: string; content?: string } | null = null;
  let content = form?.content ?? '';
  let mediaUrl = '';
  let tags = '';
  let preview = false;
</script>

<svelte:head><title>Viết bài — Oecophylla</title></svelte:head>
<div class="compose-page"><header><div><p class="eyebrow">CHIA SẺ GÓC NHÌN CỦA BẠN</p><h1 class="serif">Viết bài mới</h1><p>Những nội dung tốt đẹp hơn bắt đầu từ một góc nhìn chân thành.</p></div><a class="pill-outline" href="/">Quay lại bảng tin</a></header>
  <div class="compose-grid"><form method="POST" class="editor"><div class="editor-header"><Icon name="Edit" size={20} /><span>Bài viết của bạn</span><button type="button" on:click={() => preview = !preview}>{preview ? 'Chỉnh sửa' : 'Xem trước'}</button></div>
    {#if preview}<div class="preview serif">{content || 'Nội dung bài viết sẽ hiển thị ở đây.'}{#if mediaUrl}<img src={mediaUrl} alt="Ảnh xem trước" />{/if}</div>{:else}<label for="content">Nội dung <span>*</span></label><textarea id="content" name="content" bind:value={content} rows="12" placeholder="Chia sẻ câu chuyện, góc nhìn hoặc thông tin mà bạn muốn lan tỏa..." required></textarea>{/if}
    {#if preview}<input type="hidden" name="content" value={content} />{/if}
    <label for="media_url">Đường dẫn ảnh (nếu có)</label><div class="field"><Icon name="Image" size={18} /><input id="media_url" name="media_url" type="url" bind:value={mediaUrl} placeholder="https://..." /></div>
    <label for="tags">Thẻ chủ đề</label><div class="field"><Icon name="Tag" size={18} /><input id="tags" name="tags" bind:value={tags} placeholder="môi trường, giáo dục, cộng đồng" /></div><small>Phân tách các thẻ bằng dấu phẩy.</small>
    {#if form?.error}<p class="error" role="alert">{form.error}</p>{/if}
    <button class="pill-primary publish" type="submit"><Icon name="Send" size={17} /> Đăng bài viết</button>
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
  textarea { width: 100%; min-height: 260px; padding: 15px; resize: vertical; border: 1px solid #dfe8e3; border-radius: 7px; outline: 0; color: #173d36; font: 14px/1.7 'Lora', serif; }
  textarea:focus, .field:focus-within { border-color: #34796c; box-shadow: 0 0 0 3px #e3f1eb; }
  .field { display: flex; align-items: center; gap: 10px; height: 44px; padding: 0 13px; border: 1px solid #dfe8e3; border-radius: 7px; color: #51776d; }
  .field input { width: 100%; border: 0; outline: 0; background: transparent; font-size: 12px; }
  small { color: #8fa09a; }
  .publish { justify-self: start; margin-top: 10px; }
  .preview { min-height: 260px; padding: 15px; white-space: pre-wrap; border: 1px solid #dfe8e3; border-radius: 7px; line-height: 1.7; }
  .preview img { display: block; max-height: 300px; margin-top: 15px; border-radius: 7px; }
  .error { color: #a33f43; font-size: 12px; }
  aside { align-self: start; }
  aside img { width: 100%; height: 138px; object-fit: cover; border-radius: 6px; }
  aside h2 { margin: 14px 0 8px; font-size: 19px; font-weight: 500; }
  aside p { color: #6d8078; font: 12px/1.7 'Lora', serif; }
  aside div { display: flex; gap: 8px; margin-top: 20px; padding-top: 17px; border-top: 1px solid #e9efeb; color: #52776d; font-size: 11px; }
  @media (max-width: 850px) { .compose-grid { display: block; } aside { display: none; } }
  @media (max-width: 720px) { .compose-page { padding: 20px 14px 35px; } header { display: block; } header .pill-outline { margin-top: 14px; } h1 { font-size: 29px; } .editor { padding: 17px; } }
</style>
