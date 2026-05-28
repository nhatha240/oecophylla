<script lang="ts">
  import type { Post, MyInteractions } from '$lib/types';
  import PostActionBar from './PostActionBar.svelte';
  export let post: Post;
  export let me: MyInteractions | null = null;

  $: authorName =
    ('display_name' in post && post.display_name) ||
    ('username' in post && post.username) ||
    'Oecophylla';
  $: authorHandle =
    ('username' in post && post.username) ||
    post.author_id.slice(0, 8);
</script>

<article class="post">
  <div class="post-head">
    <div class="avatar s40">
      {post.author_id.slice(0, 1).toUpperCase()}
    </div>
    <div class="who">
      <div class="name">{authorName}</div>
      <div class="sub">
        <span>@{authorHandle}</span>
        <span>·</span>
        <span>{new Date(post.created_at).toLocaleString('vi-VN')}</span>
      </div>
    </div>
  </div>

  <a class="post-title" href={`/post/${post.id}`}>
    {post.content.length > 140 ? `${post.content.slice(0, 140)}…` : post.content}
  </a>
  <p class="post-summary whitespace-pre-wrap">{post.content}</p>

  <div class="post-meta-row">
    {#each post.tags as t}
      <a href="/tag/{t}" class="chip outline">#{t}</a>
    {/each}
    {#if post.topics?.length}
      {#each post.topics.slice(0, 2) as topic}
        <a href="/topic/{topic}" class="chip active">{topic}</a>
      {/each}
    {/if}
  </div>

  <PostActionBar {post} {me} />
</article>
