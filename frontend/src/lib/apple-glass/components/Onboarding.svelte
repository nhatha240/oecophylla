<script lang="ts">
  import Icon from './Icon.svelte';
  import { TOPICS } from '../data';

  export let onDone: () => void = () => {};

  let selected = new Set<string>(['ai', 'tech', 'sci']);
  const min = 3;
  $: ok = selected.size >= min;
  $: progress = Math.min(100, 40 + (selected.size / 8) * 60);

  function toggle(id: string) {
    selected = new Set(selected);
    selected.has(id) ? selected.delete(id) : selected.add(id);
  }
</script>

<div class="onboarding" data-screen-label="03 Onboarding">
  <header class="onb-head">
    <div class="brand" style="padding: 0"><div class="brand-mark">O</div><div class="brand-name">Oecophy<em>lla</em></div></div>
    <div class="onb-progress">
      <div class="onb-progress-meta"><span>Bước 2 / 3 · Chủ đề quan tâm</span><span><b>{selected.size}</b> đã chọn</span></div>
      <div class="onb-progress-track"><div class="onb-progress-fill" style={`width: ${progress}%`}></div></div>
    </div>
    <button class="btn ghost sm">Bỏ qua</button>
  </header>
  <div class="onb-body">
    <h1 class="onb-title">Bạn muốn đọc về điều gì?</h1>
    <p class="onb-sub">Oecophylla sẽ dùng các lựa chọn này để khởi tạo news feed cá nhân hóa cho bạn. Bạn có thể thay đổi bất cứ lúc nào trong trang Hồ sơ. Chọn ít nhất {min} chủ đề.</p>
    <div class="topic-grid">
      {#each TOPICS as topic (topic.id)}
        {@const isSelected = selected.has(topic.id)}
        <button class={`topic-card ${isSelected ? 'selected' : ''}`} on:click={() => toggle(topic.id)}>
          <div class="topic-icon"><Icon name={topic.icon} size={20} /></div>
          <div style="flex: 1; min-width: 0"><div class="topic-name">{topic.name}</div><div class="topic-desc">{topic.desc}</div></div>
          <div class="topic-check"><Icon name="Check" size={11} /></div>
        </button>
      {/each}
    </div>
    <div class="card control-note">
      <Icon name="Shield" size={18} style="color: var(--emerald-700); margin-top: 2px" />
      <div><div class="note-title">Bạn vẫn kiểm soát bảng tin của mình</div><div class="note-body">Cá nhân hóa của Oecophylla minh bạch: mỗi bài viết đều có dòng giải thích “được đề xuất vì sao”. Bạn có thể tắt cá nhân hóa, ẩn chủ đề không muốn xem, hoặc chuyển sang chế độ thời gian thực bất cứ lúc nào.</div></div>
    </div>
  </div>
  <footer class="onb-foot">
    <div class="left">{#if ok}<Icon name="Check" size={14} style="color: var(--emerald-500); vertical-align: -2px" /> Đủ điều kiện tiếp tục.{:else}Cần chọn thêm {min - selected.size} chủ đề.{/if}</div>
    <div class="right"><button class="btn ghost">Quay lại</button><button class="btn emerald lg" disabled={!ok} on:click={onDone}>Xây dựng bảng tin của tôi <Icon name="ArrowRight" size={14} /></button></div>
  </footer>
</div>

<style>
  .control-note { margin-top: 32px; padding: 18px 22px; display: flex; gap: 14px; align-items: flex-start; background: var(--emerald-50); border-color: var(--emerald-100); }
  .note-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
  .note-body { font-size: 13px; color: var(--ink-2); line-height: 1.5; }
</style>
