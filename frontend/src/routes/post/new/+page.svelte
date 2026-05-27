<script lang="ts">
  import Composer from '$lib/components/Composer.svelte';
  export let form: { error?: string } | null;
</script>

<div class="reader">
  <div class="crumbs"><a href="/" style="color: var(--muted);">Quay lại bảng tin</a></div>
  <h1>Soạn bài viết mới</h1>
  <p class="dek">Một giao diện viết bài tối giản theo hệ Apple Glass, nhưng vẫn gửi dữ liệu vào action thật của SvelteKit.</p>
  <Composer error={form?.error ?? null} />
</div>
