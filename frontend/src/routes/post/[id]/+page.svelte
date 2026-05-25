<script lang="ts">
  import PostCard from '$lib/components/PostCard.svelte';
  export let data: { post: import('$lib/types').Post };
</script>
<PostCard post={data.post} />
