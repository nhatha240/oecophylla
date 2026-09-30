<script lang="ts">
  import type { PageData } from './$types';
  import type { FeedItem, MyInteractions } from '$lib/types';
  import { getFeed, getMyInteractionsBatch } from '$lib/api';
  import EditorialPostCard from '$lib/components/EditorialPostCard.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  export let data: PageData;
  let items: FeedItem[] = [];
  let me: Record<string, MyInteractions> = {};
  let cursor: string | null = null;
  let loading = false;
  let error = '';
  $: { items = data.feed?.items ?? []; me = data.me ?? {}; cursor = data.feed?.next_cursor ?? null; }

  async function loadMore() {
    if (!cursor || loading) return;
    loading = true; error = '';
    try {
      const next = await getFeed(fetch, cursor, 20, data.feedMode === 'foryou' ? undefined : data.feedMode);
      const nextMe = next.items.length ? await getMyInteractionsBatch(fetch, next.items.map((item) => item.id)).catch(() => ({ items: {} })) : { items: {} };
      items = [...items, ...next.items]; me = { ...me, ...nextMe.items }; cursor = next.next_cursor;
    } catch { error = 'Chưa tải thêm được bài viết. Vui lòng thử lại.'; }
    finally { loading = false; }
  }
</script>

<svelte:head>
  <title>Bảng tin — Oecophylla</title>
  <meta name="description" content="Tin tức đáng tin cậy và những cuộc thảo luận có chiều sâu trên Oecophylla." />
</svelte:head>

<div class="feed-layout">
  <section class="feed-content" aria-label="Bảng tin">
    <div class="feed-heading">
      <div><p class="eyebrow">TIN TỨC · THẢO LUẬN · CỘNG ĐỒNG</p><h1 class="serif">Cùng nhau đọc sâu,<br />nghĩ kỹ hơn, kiến tạo những đối thoại tốt đẹp hơn.</h1><p>Tin tức đáng tin cậy. Thảo luận có chiều sâu. Và một cộng đồng luôn hướng đến điều tốt đẹp hơn.</p></div>
      <div class="handwritten">Tri thức<br />kết nối<br />con người<span>⌁</span></div>
    </div>

    <div class="feed-tabs" aria-label="Chế độ bảng tin">
      <a class:active={data.feedMode === 'foryou'} href="/">Dành cho bạn</a>
      <a class:active={data.feedMode === 'following'} href="/?feed=following">Đang theo dõi</a>
      <a class:active={data.feedMode === 'trending'} href="/?feed=trending">Thịnh hành</a>
    </div>

    {#if !data.feed}
      <div class="empty-state"><Icon name="Book" size={27} /><h2 class="serif">Bảng tin đang chờ kết nối</h2><p>Chúng tôi chưa tải được bài viết lúc này. Hãy thử làm mới trang sau ít phút.</p><button class="pill-outline" on:click={() => location.reload()}>Tải lại</button></div>
    {:else if items.length === 0}
      <div class="empty-state"><Icon name="Sparkle" size={28} /><h2 class="serif">Chưa có bài viết để hiển thị</h2><p>{data.feedMode === 'following' ? 'Theo dõi thêm tác giả để bảng tin này phong phú hơn.' : 'Những câu chuyện mới sẽ xuất hiện tại đây.'}</p><a class="pill-outline" href="/search">Khám phá nội dung</a></div>
    {:else}
      <div class="feed-list">{#each items as post (post.impression_id ?? `${post.request_id}:${post.id}`)}<EditorialPostCard {post} me={me[post.id] ?? null} viewerId={data.user?.id ?? null} />{/each}</div>
      {#if error}<p class="load-error" role="alert">{error}</p>{/if}
      {#if cursor}<button class="load-more pill-outline" type="button" disabled={loading} on:click={loadMore}>{loading ? 'Đang tải…' : 'Xem thêm bài viết'} <Icon name="ArrowRight" size={15} /></button>{/if}
    {/if}
  </section>

  <aside class="feed-rail" aria-label="Thông tin bên lề">
    <div class="rail-community">
      <img src="/brand/street.jpg" alt="Một góc phố Việt Nam rợp bóng cây" />
      <h2 class="serif">Cùng những<br />con người tử tế<br />tạo nên khác biệt.</h2>
      <p>Mỗi bài viết là một lời mời cùng hiểu hơn và trò chuyện sâu hơn.</p>
      <a class="pill-primary" href="/post/new"><Icon name="Edit" size={15} /> Viết câu chuyện của bạn</a>
    </div>
    <blockquote>“Thế giới tốt đẹp hơn bắt đầu từ những cuộc đối thoại tốt đẹp hơn.”<cite>— Oecophylla</cite></blockquote>
    <div class="rail-trending">
      <h2 class="serif">Chủ đề nổi bật</h2>
      {#if data.trendingTopics?.length}
        {#each data.trendingTopics.slice(0, 4) as topic, index}
          <a href={'/search?q=' + encodeURIComponent(topic.slug)}><span class="trend-index">{index + 1}</span><span><strong>{topic.label}</strong><small>{topic.count} bài viết</small></span><Icon name="ArrowRight" size={14} /></a>
        {/each}
      {:else}
        <p class="muted">Các chủ đề đang được cập nhật.</p>
      {/if}
    </div>
  </aside>
</div>

<style>
  .feed-layout { display: grid; grid-template-columns: minmax(0, 1fr) 265px; gap: 26px; max-width: 1180px; margin: 0 auto; padding: 25px 28px 60px 30px; background: #fbfcfb; }
  .feed-content { min-width: 0; }
  .feed-heading { display: flex; gap: 15px; justify-content: space-between; align-items: center; padding: 5px 0 23px; }
  .feed-heading .eyebrow { margin: 0 0 12px; }
  h1 { margin: 0; max-width: 720px; font-size: clamp(23px, 2.1vw, 32px); line-height: 1.22; letter-spacing: -.045em; font-weight: 500; }
  .feed-heading p:last-child { margin: 8px 0 0; color: #7b8985; font: 12px/1.6 'Lora', Georgia, serif; }
  .handwritten { flex: 0 0 80px; transform: rotate(-11deg); color: #688b83; font: italic 14px/1.22 'Lora', Georgia, serif; text-align: center; }
  .handwritten span { display: block; font-size: 30px; line-height: .7; }
  .feed-tabs { display: flex; gap: 2px; width: fit-content; max-width: 100%; margin-bottom: 15px; padding: 3px; border: 1px solid #e2ebe6; border-radius: 99px; background: white; overflow: auto; }
  .feed-tabs a { flex: 0 0 auto; min-width: 115px; padding: 8px 15px; border: 0; border-radius: 99px; color: #536a64; background: transparent; text-align: center; font: 500 12px 'Lora', Georgia, serif; }
  .feed-tabs .active { background: #1e5b54; color: white; }
  .feed-list { display: grid; gap: 11px; }
  .load-more { display: flex; margin: 24px auto 0; }
  .load-error { color: #a64046; text-align: center; font-size: 12px; }
  .empty-state { display: grid; justify-items: center; gap: 12px; padding: 65px 30px; border: 1px solid #e7eeea; border-radius: 10px; background: white; text-align: center; color: #42736b; }
  .empty-state h2 { margin: 0; color: #173d37; font-size: 22px; font-weight: 500; }
  .empty-state p { max-width: 390px; margin: 0 0 5px; color: #758780; font-size: 12px; line-height: 1.6; }
  .rail-community { padding: 10px; border: 1px solid #e9efec; border-radius: 10px; background: white; }
  .rail-community img { display: block; width: 100%; height: 126px; object-fit: cover; border-radius: 5px; }
  .rail-community h2 { margin: 14px 5px 8px; font-size: 18px; line-height: 1.3; font-weight: 500; }
  .rail-community p { margin: 0 5px 16px; color: #6e807a; font: 11px/1.6 'Lora', Georgia, serif; }
  .rail-community .pill-primary { width: 100%; padding: 0 9px; font-size: 10px; }
  blockquote { margin: 14px 0; padding: 25px 16px; border-radius: 9px; background: #f4f7f4; color: #4d6c64; text-align: center; font: italic 16px/1.55 'Lora', Georgia, serif; }
  cite { display: block; margin-top: 10px; font-size: 11px; }
  .rail-trending { padding: 18px 14px; border: 1px solid #e9efec; border-radius: 9px; background: white; }
  .rail-trending h2 { margin: 0 0 10px; font-size: 16px; font-weight: 500; }
  .rail-trending a { display: flex; align-items: center; gap: 11px; padding: 12px 0; border-top: 1px solid #edf1ee; }
  .rail-trending a > span:nth-child(2) { display: grid; gap: 4px; flex: 1; }
  .rail-trending strong { font: 500 12px 'Lora', Georgia, serif; }
  .rail-trending small { color: #8a9892; font-size: 10px; }
  .trend-index { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; background: #f2f6f3; font: 12px 'Lora', serif; }
  .rail-trending .muted { font-size: 11px; }
  @media (max-width: 1160px) { .feed-layout { grid-template-columns: minmax(0,1fr) 225px; gap: 18px; padding: 24px 20px; } }
  @media (max-width: 900px) { .feed-layout { display: block; max-width: 760px; margin: auto; } .feed-rail { display: none; } }
  @media (max-width: 720px) { .feed-layout { padding: 22px 14px 24px; } .feed-heading { padding: 0 3px 15px; } .feed-heading h1 { font-size: 22px; } .feed-heading h1 br { display: none; } .feed-heading p:last-child { display: none; } .handwritten { display: none; } .feed-tabs { width: 100%; margin-bottom: 12px; } .feed-tabs a { flex: 1; min-width: auto; padding: 9px 10px; white-space: nowrap; font-size: 11px; } }
</style>
