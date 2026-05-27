<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Badge from './Badges.svelte';
  import Icon from './Icon.svelte';
  import type { Post } from '../data';

  export let post: Post;
  export let liked = false;
  export let saved = false;
  export let hideRecommend = false;
  export let onLike: () => void = () => {};
  export let onSave: () => void = () => {};
  export let onOpen: () => void = () => {};
</script>

<article class="post" data-screen-label="Post Card">
  <header class="post-head">
    <Avatar author={post.author} size="s40" showVerified />
    <div class="who">
      <div class="name">
        {post.author.name}
        {#if post.author.verified}
          <Icon name="Verified" size={13} style="color: var(--verify, var(--azure-500))" />
        {/if}
      </div>
      <div class="sub">{post.author.handle} · <Icon name="Clock" size={11} /> {post.time}</div>
    </div>
    <div class="right">
      <Badge kind={post.moderation} label={post.moderationLabel} />
      <button class="icon-btn" title="Thêm"><Icon name="More" size={16} /></button>
    </div>
  </header>

  <button class="post-title title-button" on:click={onOpen}>{post.title}</button>
  <p class="post-summary">{post.summary}</p>

  {#if post.image}
    <div class="post-thumb"><div class="ph-img" style="width: 100%; height: 100%">ẢNH BÌA · 16:9</div></div>
  {/if}

  {#if post.link}
    <div class="post-link-preview">
      <div class="ph-img">LINK</div>
      <div class="pl-meta">
        <span class="pl-domain"><Icon name="ExternalLink" size={10} style="display: inline; vertical-align: -1px; margin-right: 4px" />{post.link.domain}</span>
        <div class="pl-title">{post.link.title}</div>
      </div>
    </div>
  {/if}

  <div class="post-meta-row">
    {#each post.tags as tag}
      <Badge topicId={tag} />
    {/each}
    <span class="t-meta" style="margin-left: auto">
      <Icon name="Eye" size={12} style="display: inline; vertical-align: -2px; margin-right: 4px" />
      {post.stats.reads} lượt đọc
    </span>
  </div>

  {#if !hideRecommend}
    <div class="recommend-line"><Icon name="Sparkle" size={14} /> {post.reason}</div>
  {/if}

  <div class="post-actions">
    <button class={`post-action like ${liked ? 'active' : ''}`} on:click={onLike}>
      <Icon name={liked ? 'HeartFill' : 'Heart'} size={16} />
      {post.stats.likes + (liked ? 1 : 0)}
    </button>
    <button class="post-action"><Icon name="Comment" size={16} /> {post.stats.comments}</button>
    <button class="post-action"><Icon name="Share" size={16} /> {post.stats.shares}</button>
    <button class={`post-action save ${saved ? 'active' : ''}`} on:click={onSave}>
      <Icon name={saved ? 'BookmarkFill' : 'Bookmark'} size={16} />
      {saved ? 'Đã lưu' : 'Lưu'}
    </button>
    <span style="flex: 1"></span>
    <button class="post-action" title="Ẩn bài"><Icon name="EyeOff" size={16} /></button>
    <button class="post-action" title="Báo cáo"><Icon name="Flag" size={16} /></button>
  </div>
</article>

<style>
  .title-button {
    display: block;
    border: 0;
    background: transparent;
    text-align: left;
    width: 100%;
    color: inherit;
    padding: 0;
  }
</style>
