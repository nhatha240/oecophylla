<script lang="ts">
  import { apiFetch, ApiException } from '$lib/api';
  import { invalidateAll } from '$app/navigation';
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
<form on:submit|preventDefault={submit} class="glass-surface p-3">
  <textarea class="w-full bg-transparent outline-none resize-none" rows="2" bind:value={content}
            placeholder={parent_comment_id ? 'Phản hồi…' : 'Viết bình luận…'} maxlength="2000"></textarea>
  {#if err}<p class="text-red-700 text-sm">{err}</p>{/if}
  <div class="mt-2 flex justify-end">
    <button class="glass-button-primary" type="submit" disabled={busy}>Gửi</button>
  </div>
</form>
