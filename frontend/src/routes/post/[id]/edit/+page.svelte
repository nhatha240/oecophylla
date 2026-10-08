<script lang="ts">
  import Composer from '$lib/components/Composer.svelte';
  import type { Post } from '$lib/types';

  export let data: { post: Post };
  export let form: { error?: string } | null;
</script>

<svelte:head>
  <title>Sửa bài viết — Oecophylla</title>
</svelte:head>

<div class="reader">
  <div class="crumbs"><a href="/post/{data.post.id}">Quay lại bài viết</a></div>
  <h1>Sửa bài viết</h1>
  <p class="dek">Cập nhật nội dung, thẻ hoặc hình ảnh của bài viết.</p>
  <Composer
    action=""
    error={form?.error ?? null}
    prominent
    initialContent={data.post.content}
    initialTags={data.post.tags}
    initialMediaUrls={data.post.media_urls}
    postId={data.post.id}
    submitLabel="Lưu thay đổi"
  />
</div>
