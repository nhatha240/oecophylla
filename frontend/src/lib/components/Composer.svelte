<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let action = '/post/new';
  export let error: string | null = null;

  let content = '';
  let tagsRaw = '';
  let mediaUrls: string[] = [];
  let showPreview = false;
  let showImageInput = false;
  let imageUrl = '';

  const MAX_CHARS = 4000;
  $: charsLeft = MAX_CHARS - content.length;
  $: charsClass = charsLeft < 0 ? 'text-red-500' : charsLeft < 100 ? 'text-orange-500' : 'text-slate-400';

  // ── tag management ────────────────────────────────────────────────
  // Normalise a single tag: lowercase, strip leading #, trim spaces
  function normalise(t: string): string {
    return t.replace(/^#/, '').trim().toLowerCase();
  }

  $: selectedTags = tagsRaw
    .split(',')
    .map(normalise)
    .filter(Boolean);

  function tagsFromArray(arr: string[]): string {
    return arr.join(', ');
  }

  function toggleTag(tag: string): void {
    const norm = normalise(tag);
    if (selectedTags.includes(norm)) {
      tagsRaw = tagsFromArray(selectedTags.filter((t) => t !== norm));
    } else {
      tagsRaw = tagsFromArray([...selectedTags, norm]);
    }
  }

  // ── auto-detection ────────────────────────────────────────────────
  // keyword → canonical topic slug
  const KEYWORD_MAP: Record<string, string[]> = {
    tech: ['tech','technology','software','code','coding','programming','developer','lập trình','phần mềm','công nghệ','digital'],
    ai: ['ai','artificial intelligence','machine learning','deep learning','gpt','llm','neural','chatgpt','trí tuệ nhân tạo','học máy'],
    science: ['science','research','study','experiment','biology','physics','chemistry','khoa học','nghiên cứu','thí nghiệm'],
    sports: ['sports','football','soccer','basketball','tennis','running','thể thao','bóng đá','bóng rổ'],
    politics: ['politics','government','election','policy','parliament','chính trị','bầu cử','chính phủ','chính sách'],
    entertainment: ['entertainment','movie','film','music','concert','series','giải trí','phim','âm nhạc','ca nhạc'],
    health: ['health','fitness','workout','nutrition','mental health','sức khỏe','y tế','tập luyện','dinh dưỡng'],
    business: ['business','startup','finance','economy','market','investment','kinh doanh','khởi nghiệp','tài chính','thị trường'],
    culture: ['culture','art','history','tradition','heritage','văn hóa','nghệ thuật','lịch sử','truyền thống'],
    education: ['education','school','university','learning','student','giáo dục','trường học','học sinh','sinh viên','đại học'],
    environment: ['environment','climate','green','renewable','eco','môi trường','khí hậu','sinh thái','tái tạo'],
    news: ['news','breaking','report','update','tin tức','báo chí','tin nóng','thời sự'],
  };

  const TOPIC_LABELS: Record<string, string> = {
    tech: 'Công nghệ', science: 'Khoa học', sports: 'Thể thao',
    politics: 'Chính trị', entertainment: 'Giải trí', health: 'Sức khoẻ',
    business: 'Kinh doanh', culture: 'Văn hoá', education: 'Giáo dục',
    environment: 'Môi trường', ai: 'AI', news: 'Tin tức',
  };

  // Extract #hashtags typed inside the content body
  function extractHashtags(text: string): string[] {
    const matches = text.match(/#([\wÀ-ỹ]+)/gu) ?? [];
    return matches.map((m) => m.replace(/^#/, '').toLowerCase());
  }

  // Match content text against keyword map → set of topic slugs
  function detectTopics(text: string): string[] {
    const lower = text.toLowerCase();
    const found: string[] = [];
    for (const [slug, keywords] of Object.entries(KEYWORD_MAP)) {
      if (keywords.some((kw) => lower.includes(kw))) {
        found.push(slug);
      }
    }
    return found;
  }

  // Combine hashtags + detected topics, deduplicate, exclude already-selected
  $: suggestedTags = (() => {
    if (!content.trim()) return [];
    const hashtags = extractHashtags(content);
    const topics = detectTopics(content);
    const all = [...new Set([...hashtags, ...topics])];
    // Keep up to 6 suggestions; show even if already selected (chip will be highlighted)
    return all.slice(0, 6);
  })();

  // ── preview & media ───────────────────────────────────────────────
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

  function addImageUrl(): void {
    const url = imageUrl.trim();
    if (url && mediaUrls.length < 4) {
      mediaUrls = [...mediaUrls, url];
      imageUrl = '';
      showImageInput = false;
    }
  }

  function removeImage(idx: number): void {
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
            >×</button>
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

    <!-- Auto-suggested tags — only shown when content has detectable tags -->
    {#if suggestedTags.length > 0}
      <div class="composer-suggest">
        {#each suggestedTags as tag}
          {@const label = TOPIC_LABELS[tag] ?? tag}
          {@const active = selectedTags.includes(tag)}
          <button
            type="button"
            class="chip {active ? 'active' : 'outline'}"
            style="font-size:12px;cursor:pointer;"
            title={active ? 'Bỏ thẻ này' : 'Thêm thẻ này'}
            on:click={() => toggleTag(tag)}
          >
            {#if active}<span style="margin-right:3px;">✓</span>{/if}#{label}
          </button>
        {/each}
      </div>
    {/if}

    <!-- Hidden input carries the final comma-separated tags to the server action -->
    <input name="tags" bind:value={tagsRaw} placeholder="thẻ, ngăn cách bởi dấu phẩy" class="input" />

    {#each mediaUrls as url}
      <input type="hidden" name="media_urls[]" value={url} />
    {/each}

    {#if error}
      <p class="field err-msg" style="margin-top:10px;">
        <Icon name="AlertCircle" size={12} /> {error}
      </p>
    {/if}

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
      <span class="t-meta" style="margin-left:auto;">Hiển thị công khai · có kiểm duyệt</span>
      <button class="btn emerald sm" type="submit" data-testid="composer-submit">
        Đăng <Icon name="Send" size={12} />
      </button>
    </div>
  </div>
</form>
