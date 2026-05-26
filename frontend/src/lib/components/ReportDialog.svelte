<script lang="ts">
  import { apiFetch, ApiException } from '$lib/api';
  import { createEventDispatcher } from 'svelte';
  export let post_id: string;
  const dispatch = createEventDispatcher();
  let reason: 'spam'|'misinformation'|'harassment'|'nsfw'|'other' = 'spam';
  let detail = ''; let busy = false; let err: string | null = null;
  async function submit() {
    busy = true; err = null;
    try {
      await apiFetch(fetch, `/posts/${post_id}/report`, {
        method: 'POST', body: JSON.stringify({ reason, detail: detail || undefined })
      });
      dispatch('close');
      alert('Đã ghi nhận báo cáo. Cảm ơn bạn!');
    } catch (e) {
      if (e instanceof ApiException && e.status === 409) err = 'Bạn đã có báo cáo đang xử lý.';
      else err = 'Lỗi máy chủ';
    } finally { busy = false; }
  }
</script>
<div class="fixed inset-0 bg-ink-900/40 flex items-center justify-center z-50">
  <div class="glass-surface p-6 max-w-md w-full">
    <h3 class="text-display-serif text-xl mb-3">Báo cáo bài viết</h3>
    <div class="flex flex-col gap-2 text-sm">
      {#each ['spam','misinformation','harassment','nsfw','other'] as r}
        <label><input type="radio" bind:group={reason} value={r} /> {r}</label>
      {/each}
    </div>
    <textarea class="block w-full mt-3 px-3 py-2 rounded-xl bg-white/60 border border-white/60" rows="2"
              bind:value={detail} placeholder="Chi tiết (tùy chọn)"></textarea>
    {#if err}<p class="text-red-700 text-sm mt-2">{err}</p>{/if}
    <div class="mt-4 flex justify-end gap-2">
      <button class="glass-chip" on:click={() => dispatch('close')}>Hủy</button>
      <button class="glass-button-primary" on:click={submit} disabled={busy}>Gửi</button>
    </div>
  </div>
</div>
