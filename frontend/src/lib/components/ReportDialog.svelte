<script lang="ts">
  import { apiFetch, ApiException } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
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
<div class="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50 px-4">
  <div class="card card-pad" style="max-width: 560px; width: 100%;">
    <h3 class="serif" style="font-size: 24px; margin: 0 0 12px;">Báo cáo bài viết</h3>
    <div class="field" style="gap: 10px;">
      {#each ['spam','misinformation','harassment','nsfw','other'] as r}
        <label class="chip outline" style="justify-content: flex-start; padding: 10px 14px;">
          <input type="radio" bind:group={reason} value={r} /> {r}
        </label>
      {/each}
    </div>
    <textarea class="input" style="margin-top: 14px;" rows="3"
              bind:value={detail} placeholder="Chi tiết (tùy chọn)"></textarea>
    {#if err}<p class="field err-msg" style="margin-top: 12px;"><Icon name="AlertCircle" size={12} /> {err}</p>{/if}
    <div style="margin-top: 18px; display: flex; justify-content: flex-end; gap: 8px;">
      <button class="btn ghost sm" on:click={() => dispatch('close')}>Hủy</button>
      <button class="btn emerald sm" on:click={submit} disabled={busy}>Gửi báo cáo</button>
    </div>
  </div>
</div>
