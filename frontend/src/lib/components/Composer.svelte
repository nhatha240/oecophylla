<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let action = '/post/new';
  export let error: string | null = null;

  let content = '';
  let tags = '';
  let mediaUrls: string[] = [];
  let showPreview = false;
  let showImageInput = false;
  let imageUrl = '';

  const MAX_CHARS = 4000;
  $: charsLeft = MAX_CHARS - content.length;
  $: charsClass = charsLeft < 0 ? 'text-red-500' : charsLeft < 100 ? 'text-orange-500' : 'text-slate-400';

  function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function renderMarkdown(text: string): string {
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener" class="text-blue-500 underline">$1</a>'
    );
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  function addImageUrl() {
    const url = imageUrl.trim();
    if (url && mediaUrls.length < 4) {
      mediaUrls = [...mediaUrls, url];
      imageUrl = '';
      showImageInput = false;
    }
  }

  function removeImage(idx: number) {
    mediaUrls = mediaUrls.filter((_, i) => i !== idx);
  }
</script>

<form method="post" action={action} class="composer">
  <div class="avatar s40">O</div>
  <div class="right">
    {#if showPreview}
      <div class="whitespace-pre-wrap text-slate-800 text-sm leading-relaxed min-h-[4.5rem] p-2 rounded-lg bg-slate-50">
        {#if content}
          {@html renderMarkdown(content)}
        {:else}
          <span class="text-slate-400 italic">Chưa có nội dung</span>
        {/if}
      </div>
    {:else}
      <textarea
        name="content"
        rows="3"
        maxlength="4000"
        bind:value={content}
        placeholder="Bạn muốn chia sẻ tin tức hoặc góc nhìn gì hôm nay?"
      ></textarea>
    {/if}

    {#if mediaUrls.length > 0}
      <div class="flex gap-2 mt-2 flex-wrap">
        {#each mediaUrls as url, i}
          <div class="relative group">
            <img src={url} alt="media {i}" class="w-16 h-16 object-cover rounded-lg border border-slate-200" />
            <button
              type="button"
              class="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
              on:click={() => removeImage(i)}
            >
              ×
            </button>
          </div>
        {/each}
      </div>
    {/if}

    {#if showImageInput}
      <div class="flex gap-2 mt-2">
        <input
          type="url"
          bind:value={imageUrl}
          placeholder="Dán URL hình ảnh…"
          class="input flex-1"
          on:keydown={(e) => e.key === 'Enter' && (e.preventDefault(), addImageUrl())}
        />
        <button type="button" class="btn ghost sm" on:click={addImageUrl}>Thêm</button>
        <button type="button" class="btn ghost sm" on:click={() => (showImageInput = false)}>Huỷ</button>
      </div>
    {/if}

    <div class="composer-suggest">
      <span class="chip outline">#Công nghệ</span>
      <span class="chip outline">#AI</span>
      <span class="chip outline">#Báo chí số</span>
    </div>
    <input name="tags" bind:value={tags} placeholder="thẻ, ngăn cách bởi dấu phẩy" class="input" />
    {#each mediaUrls as url, i}
      <input type="hidden" name="media_urls[]" value={url} />
    {/each}
    {#if error}<p class="field err-msg" style="margin-top: 10px;"><Icon name="AlertCircle" size={12} /> {error}</p>{/if}
    <div class="composer-foot">
      <div class="composer-actions">
        <button
          class="icon-btn"
          type="button"
          title="Xem trước"
          class:text-blue-500={showPreview}
          on:click={() => (showPreview = !showPreview)}
        >
          <Icon name={showPreview ? 'Edit' : 'Eye'} size={16} />
        </button>
        <button
          class="icon-btn"
          type="button"
          title="Thêm ảnh"
          on:click={() => (showImageInput = !showImageInput)}
        >
          <Icon name="Image" size={16} />
        </button>
        <button class="icon-btn" type="button" title="Thêm liên kết"><Icon name="Link" size={16} /></button>
        <button class="icon-btn" type="button" title="Thêm chủ đề"><Icon name="Tag" size={16} /></button>
      </div>
      <span class="text-xs {charsClass} tabular-nums">{charsLeft}</span>
      <span class="t-meta" style="margin-left: auto;">Hiển thị công khai · có kiểm duyệt</span>
      <button class="btn emerald sm" type="submit" data-testid="composer-submit">Đăng <Icon name="Send" size={12} /></button>
    </div>
  </div>
</form>
