<script lang="ts">
  import type { Comment } from '$lib/types';
  import MentionText from './MentionText.svelte';
  export let item: Comment;
  export let currentUserId: string | undefined;
  export let isAdmin = false;
  export let canReply = false;
  export let onReply: () => void = () => undefined;
  export let onDelete: () => void = () => undefined;
  export let disabled = false;
  $: displayName = item.author_display_name ?? item.author_username;
</script>

<div class="comment-card">
  <a class="comment-avatar" href={'/profile/' + item.author_id} aria-label={'Hồ sơ ' + displayName}>{displayName.slice(0, 1).toUpperCase()}</a>
  <div class="comment-main">
    <div class="comment-head"><a href={'/profile/' + item.author_id}>{displayName}</a><small>{new Intl.DateTimeFormat('vi-VN').format(new Date(item.created_at))}</small></div>
    <p><MentionText text={item.content} /></p>
    <div class="comment-actions">
      {#if canReply}<button type="button" on:click={onReply} {disabled}>Trả lời</button>{/if}
      {#if currentUserId === item.author_id || isAdmin}<button type="button" class="delete" on:click={onDelete} {disabled}>Xóa</button>{/if}
    </div>
  </div>
</div>

<style>
  .comment-card { display: flex; gap: 10px; min-width: 0; }
  .comment-avatar { flex: 0 0 32px; display: grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; background: #dcece5; color: #1d5b54; font: 600 14px 'Lora', serif; }
  .comment-main { min-width: 0; }
  .comment-head { display: flex; align-items: baseline; flex-wrap: wrap; gap: 7px; }
  .comment-head a { color: #274b40; font: 600 12px 'Lora', serif; }
  .comment-head small { color: #96a59d; font-size: 10px; }
  p { margin: 7px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; color: #5f746a; font: 12px/1.65 'Lora', serif; }
  .comment-actions { display: flex; gap: 13px; margin-top: 6px; }
  .comment-actions button { padding: 0; border: 0; background: transparent; color: #39776b; font-size: 11px; cursor: pointer; }
  .comment-actions button.delete { color: #986b65; }
  .comment-actions button:disabled { opacity: .5; cursor: not-allowed; }
</style>
