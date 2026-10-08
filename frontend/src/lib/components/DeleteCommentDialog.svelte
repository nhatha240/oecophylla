<script lang="ts">
  import { tick } from 'svelte';
  import type { Comment } from '$lib/types';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  export let item: Comment | null = null;
  export let busy = false;
  export let error = '';
  export let onCancel: () => void = () => undefined;
  export let onConfirm: () => void = () => undefined;

  let dialog: HTMLDialogElement;
  let cancelButton: HTMLButtonElement;
  $: authorName = item?.author_display_name || item?.author_username || 'Thành viên Oecophylla';
  $: if (dialog) syncDialog(item);

  async function syncDialog(selected: Comment | null): Promise<void> {
    await tick();
    if (selected && item && !dialog.open) {
      dialog.showModal();
      cancelButton.focus();
    } else if (!item && dialog.open) {
      dialog.close();
    }
  }

  function cancel(event?: Event): void {
    event?.preventDefault();
    if (!busy) onCancel();
  }

  function backdrop(event: PointerEvent): void {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) cancel();
  }
</script>

<dialog bind:this={dialog} aria-labelledby="delete-comment-title" aria-describedby="delete-comment-description"
  aria-busy={busy} on:cancel={cancel} on:pointerdown={backdrop}>
  {#if item}
    <div class="modal-content">
      <button type="button" class="close" aria-label="Đóng" disabled={busy} on:click={() => cancel()}><Icon name="X" size={18} /></button>
      <div class="delete-symbol" aria-hidden="true">
        <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6" /></svg>
      </div>
      <p class="eyebrow">QUẢN LÝ BÌNH LUẬN</p>
      <h2 id="delete-comment-title">Xóa bình luận?</h2>
      <p id="delete-comment-description" class="description">Bình luận này sẽ được gỡ khỏi cuộc thảo luận. Bạn không thể hoàn tác thao tác này.</p>
      <div class="comment-preview">
        <div class="preview-author"><span class="avatar">{authorName.slice(0, 1).toUpperCase()}</span><strong>{authorName}</strong></div>
        <blockquote>{item.content}</blockquote>
      </div>
      {#if (item.reply_count ?? 0) > 0}
        <p class="reply-notice"><Icon name="Comment" size={16} /><span>Các câu trả lời bên dưới cũng sẽ bị ẩn.</span></p>
      {/if}
      {#if error}<p class="error" role="alert"><Icon name="AlertCircle" size={17} /><span>{error}</span></p>{/if}
      <div class="modal-actions">
        <button bind:this={cancelButton} type="button" class="cancel" disabled={busy} on:click={() => cancel()}>Hủy</button>
        <button type="button" class="confirm" disabled={busy} on:click={onConfirm}>
          {#if busy}<span class="spinner" aria-hidden="true"></span>Đang xóa…{:else}Xóa bình luận{/if}
        </button>
      </div>
    </div>
  {/if}
</dialog>

<style>
  dialog { width: min(440px, calc(100vw - 32px)); max-width: none; max-height: calc(100dvh - 40px); margin: auto; padding: 0; overflow-y: auto; border: 1px solid #e1e9e2; border-radius: 22px; background: #fcfdfb; color: #23483e; box-shadow: 0 28px 90px #102e3440, 0 4px 16px #102e3414; }
  dialog::backdrop { background: #132d3261; backdrop-filter: blur(5px); }
  dialog[open] { animation: appear 180ms ease-out; }
  .modal-content { position: relative; padding: 30px; }
  .close { position: absolute; top: 16px; right: 16px; display: grid; place-items: center; width: 32px; height: 32px; padding: 0; border: 0; border-radius: 50%; background: transparent; color: #70857b; cursor: pointer; }
  .close:hover { background: #edf2ed; }
  .delete-symbol { display: grid; place-items: center; width: 52px; height: 52px; margin-bottom: 22px; border: 1px solid #f1ded7; border-radius: 16px; background: #fbefea; color: #ac5345; }
  .eyebrow { margin: 0 0 9px; color: #71867b; font-size: 9px; font-weight: 600; letter-spacing: .14em; }
  h2 { margin: 0; color: #23483e; font: 500 29px/1.3 'Lora', Georgia, serif; letter-spacing: -.035em; }
  .description { margin: 13px 0 20px; color: #6a7e74; font-size: 12px; line-height: 1.8; }
  .comment-preview { padding: 15px 16px; border: 1px solid #e4ebe3; border-radius: 12px; background: #f2f6f0; }
  .preview-author { display: flex; align-items: center; gap: 9px; }
  .avatar { display: grid; place-items: center; flex: 0 0 26px; width: 26px; height: 26px; border-radius: 50%; background: #dfece2; color: #396455; font: 600 12px 'Lora', Georgia, serif; }
  strong { font-size: 11px; font-weight: 600; overflow-wrap: anywhere; }
  blockquote { display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; margin: 9px 0 0; color: #587063; font: 12px/1.8 'Lora', Georgia, serif; white-space: pre-wrap; overflow-wrap: anywhere; }
  .reply-notice, .error { display: flex; align-items: flex-start; gap: 8px; margin: 13px 0 0; font-size: 11px; line-height: 1.7; }
  .reply-notice { color: #887651; }
  .reply-notice :global(svg), .error :global(svg) { flex-shrink: 0; margin-top: 1px; }
  .error { padding: 11px 12px; border-radius: 9px; background: #fbefea; color: #a34a3d; }
  .modal-actions { display: flex; gap: 10px; margin-top: 26px; }
  .modal-actions button { display: inline-flex; justify-content: center; align-items: center; gap: 8px; min-height: 44px; padding: 11px 18px; border-radius: 24px; font: 500 12px 'Be Vietnam Pro', sans-serif; cursor: pointer; transition: background 140ms, box-shadow 140ms; }
  .cancel { flex: 1; border: 1px solid #d9e4da; background: #fcfdfb; color: #4a6a5c; }
  .cancel:hover { background: #edf3ec; }
  .confirm { flex: 1.6; border: 1px solid #a95143; background: #a95143; color: white; box-shadow: 0 3px 8px #a951431c; }
  .confirm:hover { border-color: #914437; background: #914437; }
  button:focus-visible { outline: 2px solid #3d7d69; outline-offset: 3px; }
  button:disabled { opacity: .6; cursor: wait; }
  .spinner { width: 14px; height: 14px; border: 2px solid #ffffff55; border-top-color: white; border-radius: 50%; animation: spin 750ms linear infinite; }
  @keyframes appear { from { opacity: 0; transform: translateY(8px) scale(.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (max-width: 480px) { .modal-content { padding: 25px 23px; } h2 { font-size: 27px; } }
  @media (prefers-reduced-motion: reduce) { dialog[open], .spinner { animation: none; } .modal-actions button { transition: none; } }
</style>
