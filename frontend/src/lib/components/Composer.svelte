<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let action = '/post/new';
  export let error: string | null = null;
</script>

<form method="post" action={action} class="composer">
  <div class="avatar s40">O</div>
  <div class="right">
    <textarea
      name="content"
      rows="3"
      maxlength="4000"
      placeholder="Bạn muốn chia sẻ tin tức hoặc góc nhìn gì hôm nay?"
    ></textarea>
    <div class="composer-suggest">
      <span class="chip outline">#Công nghệ</span>
      <span class="chip outline">#AI</span>
      <span class="chip outline">#Báo chí số</span>
    </div>
    <input name="tags" placeholder="thẻ, ngăn cách bởi dấu phẩy" class="input" />
    {#if error}<p class="field err-msg" style="margin-top: 10px;"><Icon name="AlertCircle" size={12} /> {error}</p>{/if}
    <div class="composer-foot">
      <div class="composer-actions">
        <button class="icon-btn" type="button" title="Thêm ảnh"><Icon name="Image" size={16} /></button>
        <button class="icon-btn" type="button" title="Thêm liên kết"><Icon name="Link" size={16} /></button>
        <button class="icon-btn" type="button" title="Thêm chủ đề"><Icon name="Tag" size={16} /></button>
      </div>
      <span class="t-meta" style="margin-left: auto;">Hiển thị công khai · có kiểm duyệt</span>
      <button class="btn emerald sm" type="submit">Đăng <Icon name="Send" size={12} /></button>
    </div>
  </div>
</form>
