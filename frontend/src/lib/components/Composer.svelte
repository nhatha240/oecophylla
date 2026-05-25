<script lang="ts">
  export let action = '/post/new';
  export let error: string | null = null;
</script>
<form method="post" action={action} class="glass-surface p-5 mb-4">
  <textarea name="content" rows="3" maxlength="4000" placeholder="Bạn đang nghĩ gì?"
    class="w-full bg-transparent outline-none resize-none placeholder:text-ink-500"></textarea>
  <input name="tags" placeholder="thẻ, ngăn cách bởi dấu phẩy" class="block w-full mt-2 px-3 py-2 rounded-xl bg-white/60 border border-white/60 text-sm" />
  {#if error}<p class="text-red-700 text-sm mt-2">{error}</p>{/if}
  <div class="mt-3 flex justify-end"><button class="glass-button-primary" type="submit">Đăng</button></div>
</form>
