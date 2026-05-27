<script lang="ts">
  import { apiFetch, ApiException } from '$lib/api';
  import { invalidateAll } from '$app/navigation';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let post_id: string;
  export let parent_comment_id: string | null = null;
  let content = ''; let busy = false; let err: string | null = null;
  async function submit() {
    if (!content.trim()) return;
    busy = true; err = null;
    try {
      await apiFetch(fetch, `/posts/${post_id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ content, parent_comment_id })
      });
      content = '';
      await invalidateAll();
    } catch (e) {
      if (e instanceof ApiException && e.status === 400) err = 'Nội dung không hợp lệ';
      else if (e instanceof ApiException && e.status === 401) err = 'Vui lòng đăng nhập';
      else err = 'Lỗi máy chủ';
    } finally { busy = false; }
  }
</script>

<form on:submit|preventDefault={submit} class="composer" style="margin-bottom: 0;">
  <div class="avatar s40">O</div>
  <div class="right">
    <textarea
      rows="2"
      bind:value={content}
      placeholder={parent_comment_id ? 'Phản hồi với ngữ cảnh rõ ràng…' : 'Viết bình luận của bạn…'}
      maxlength="2000"
    ></textarea>
    {#if err}<p class="field err-msg" style="margin-top: 10px;"><Icon name="AlertCircle" size={12} /> {err}</p>{/if}
    <div class="composer-foot">
      <span class="t-meta">Bình luận sẽ hiển thị công khai. Hành vi quấy rối sẽ bị ẩn tự động.</span>
      <button class="btn emerald sm" style="margin-left: auto" type="submit" disabled={busy}>Gửi</button>
    </div>
  </div>
</form>
