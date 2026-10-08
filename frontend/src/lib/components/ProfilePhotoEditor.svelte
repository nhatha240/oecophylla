<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  type PhotoKind = 'avatar' | 'cover';
  export let avatarUrl = '';
  export let coverUrl = '';
  export let name = '';
  export let username = '';
  export let uploading: PhotoKind | null = null;
  export let disabled = false;

  const dispatch = createEventDispatcher<{
    select: { file: File; kind: PhotoKind };
    invalid: string;
  }>();
  let avatarInput: HTMLInputElement;
  let coverInput: HTMLInputElement;
  let dragging: PhotoKind | null = null;
  const dragDepth = { avatar: 0, cover: 0 };
  let previewUrl = '';
  let previewKind: PhotoKind | null = null;

  $: locked = disabled || uploading !== null;
  $: avatarPreview = uploading === 'avatar' && previewKind === 'avatar' ? previewUrl : avatarUrl;
  $: coverPreview = uploading === 'cover' && previewKind === 'cover' ? previewUrl : coverUrl;

  onDestroy(clearPreview);

  function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = '';
    previewKind = null;
  }

  function selectFiles(files: File[], kind: PhotoKind) {
    if (locked || !files.length) return;
    if (files.length !== 1) {
      dispatch('invalid', 'Mỗi lần chỉ chọn một ảnh đại diện hoặc một ảnh bìa.');
      return;
    }
    clearPreview();
    previewKind = kind;
    previewUrl = URL.createObjectURL(files[0]);
    dispatch('select', { file: files[0], kind });
  }

  function selected(event: Event, kind: PhotoKind) {
    const input = event.currentTarget as HTMLInputElement;
    selectFiles(Array.from(input.files ?? []), kind);
    input.value = '';
  }

  function dragEnter(event: DragEvent, kind: PhotoKind) {
    event.preventDefault();
    if (locked || !event.dataTransfer?.types.includes('Files')) return;
    dragDepth[kind] += 1;
    dragging = kind;
  }

  function dragLeave(event: DragEvent, kind: PhotoKind) {
    event.preventDefault();
    dragDepth[kind] = Math.max(0, dragDepth[kind] - 1);
    if (!dragDepth[kind] && dragging === kind) dragging = null;
  }

  function dragOver(event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = locked ? 'none' : 'copy';
  }

  function dropped(event: DragEvent, kind: PhotoKind) {
    event.preventDefault();
    dragDepth[kind] = 0;
    dragging = null;
    selectFiles(Array.from(event.dataTransfer?.files ?? []), kind);
  }
</script>

<div class="photo-editor" aria-busy={!!uploading}>
  <section class="cover-editor" class:has-photo={!!coverPreview} class:dragging={dragging === 'cover'}
    aria-label="Tải ảnh bìa" data-testid="profile-cover-dropzone"
    on:dragenter={(event) => dragEnter(event, 'cover')}
    on:dragleave={(event) => dragLeave(event, 'cover')}
    on:dragover={dragOver} on:drop={(event) => dropped(event, 'cover')}>
    {#if coverPreview}<img class="cover-photo" src={coverPreview} alt="Ảnh bìa xem trước" />{/if}
    <div class="cover-toolbar">
      <span class="photo-label"><Icon name="Image" size={13} /> Ảnh bìa</span>
      <button type="button" class="cover-button" disabled={locked} on:click={() => coverInput.click()}>
        <Icon name="Camera" size={15} /> {coverUrl ? 'Đổi ảnh bìa' : 'Thêm ảnh bìa'}
      </button>
    </div>
    {#if !coverPreview}
      <div class="cover-placeholder"><Icon name="Image" size={28} />
        <strong>Một khung hình, một góc nhìn</strong><span>Kéo thả ảnh của bạn vào đây</span>
      </div>
    {:else}<span class="cover-hint">Kéo thả ảnh mới để thay ảnh bìa</span>{/if}
    {#if dragging === 'cover'}<div class="drop-overlay" aria-hidden="true">Thả ảnh để đổi ảnh bìa</div>{/if}
    {#if uploading === 'cover'}<div class="upload-overlay" role="status"><span class="spinner"></span>Đang tải ảnh bìa…</div>{/if}
  </section>

  <div class="identity-row">
    <section class="avatar-editor" class:dragging={dragging === 'avatar'}
      aria-label="Tải ảnh đại diện" data-testid="profile-avatar-dropzone"
      on:dragenter={(event) => dragEnter(event, 'avatar')}
      on:dragleave={(event) => dragLeave(event, 'avatar')}
      on:dragover={dragOver} on:drop={(event) => dropped(event, 'avatar')}>
      <div class="avatar-photo">
        {#if avatarPreview}<img src={avatarPreview} alt="Ảnh đại diện xem trước" />{:else}<span>{(name || username || '?').slice(0, 1).toUpperCase()}</span>{/if}
        {#if dragging === 'avatar'}<div class="avatar-overlay" aria-hidden="true">Thả ảnh</div>{/if}
        {#if uploading === 'avatar'}<div class="avatar-overlay" role="status"><span class="spinner"></span><span class="sr-only">Đang tải ảnh đại diện…</span></div>{/if}
      </div>
      <button type="button" class="camera-button" aria-label="Thay ảnh đại diện" title="Thay ảnh đại diện"
        disabled={locked} on:click={() => avatarInput.click()}><Icon name="Camera" size={14} /></button>
    </section>
    <div class="identity-copy"><strong>{name || username}</strong><span>@{username}</span></div>
    <button type="button" class="avatar-button" disabled={locked} on:click={() => avatarInput.click()}>
      <Icon name="Image" size={15} /> {avatarUrl ? 'Đổi ảnh đại diện' : 'Thêm ảnh đại diện'}
    </button>
  </div>
  <p class="photo-help">Kéo thả ảnh vào khung ảnh bìa hoặc ảnh đại diện. JPEG, PNG, WebP · tối đa 5 MB.</p>
  <input bind:this={avatarInput} id="profile-avatar-file" type="file" accept="image/jpeg,image/png,image/webp"
    aria-label="Tệp ảnh đại diện" disabled={locked} on:change={(event) => selected(event, 'avatar')} />
  <input bind:this={coverInput} id="profile-cover-file" type="file" accept="image/jpeg,image/png,image/webp"
    aria-label="Tệp ảnh bìa" disabled={locked} on:change={(event) => selected(event, 'cover')} />
</div>

<style>
  .photo-editor { --photo-green: #1d6956; --photo-ink: #183d34; }
  .cover-editor { position: relative; height: 205px; overflow: hidden; border: 1px solid #dce9e0; border-radius: 12px; background: radial-gradient(ellipse at 100% 0%, #c8ded0 0%, transparent 60%), linear-gradient(120deg, #f2f6ed, #deeee4); }
  .cover-editor::before, .cover-editor::after { position: absolute; content: ''; width: 250px; height: 180px; right: -100px; bottom: -100px; border: 1px solid #94b7a355; border-radius: 50%; transform: rotate(-30deg); }
  .cover-editor::after { right: -50px; bottom: -110px; }
  .cover-photo { width: 100%; height: 100%; object-fit: cover; }
  .cover-toolbar { position: absolute; z-index: 1; inset: 14px 14px auto; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .photo-label { display: inline-flex; align-items: center; gap: 6px; color: #406452; font-size: 11px; font-weight: 600; }
  .has-photo .photo-label { padding: 6px 9px; border-radius: 20px; background: #18382f88; color: white; }
  .cover-button, .avatar-button, .camera-button { display: inline-flex; justify-content: center; align-items: center; gap: 7px; border: 1px solid #d2e0d6; background: #ffffffed; color: var(--photo-ink); font-size: 11px; font-weight: 600; cursor: pointer; transition: background .15s; }
  .cover-button { padding: 9px 12px; border-radius: 8px; box-shadow: 0 2px 8px #183d3408; }
  button:hover:not(:disabled) { background: #edf6ef; }
  button:disabled { opacity: .55; cursor: wait; }
  button:focus-visible { outline: 3px solid #54a17f; outline-offset: 3px; }
  .cover-placeholder { position: absolute; inset: 60px 20px 35px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; color: #638974; }
  .cover-placeholder strong { color: #426854; font: 500 18px 'Lora', serif; }
  .cover-placeholder span { color: #6d8878; font-size: 11px; }
  .cover-hint { position: absolute; right: 15px; bottom: 13px; padding: 5px 9px; border-radius: 5px; background: #153f3588; color: #ffffffe5; font-size: 10px; }
  .identity-row { position: relative; z-index: 2; display: flex; align-items: center; gap: 14px; margin: -35px 16px 0; }
  .avatar-editor { position: relative; width: 100px; height: 100px; flex: 0 0 100px; }
  .avatar-photo { display: grid; position: relative; width: 100%; height: 100%; overflow: hidden; place-items: center; border: 5px solid white; border-radius: 50%; background: #d7eade; box-shadow: 0 3px 12px #183d3410; color: var(--photo-green); font: 500 36px 'Lora', serif; }
  .avatar-photo img { width: 100%; height: 100%; object-fit: cover; }
  .camera-button { position: absolute; bottom: 4px; right: 2px; width: 29px; height: 29px; border: 2px solid white; border-radius: 50%; background: var(--photo-green); color: white; }
  .camera-button:hover:not(:disabled) { background: #14523f; }
  .identity-copy { display: grid; min-width: 0; gap: 4px; margin-top: 28px; }
  .identity-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--photo-ink); font: 600 18px 'Lora', serif; }
  .identity-copy span { overflow: hidden; text-overflow: ellipsis; color: #819489; font-size: 11px; }
  .avatar-button { flex: 0 0 auto; margin: 30px 0 0 auto; padding: 9px 11px; border-radius: 8px; }
  .photo-help { margin: 13px 16px 0; color: #82988c; font-size: 10px; line-height: 1.7; }
  input[type='file'] { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
  .drop-overlay, .upload-overlay { position: absolute; z-index: 3; inset: 0; display: flex; align-items: center; justify-content: center; gap: 10px; background: #e7f4eced; color: var(--photo-green); font-size: 13px; font-weight: 600; pointer-events: none; }
  .drop-overlay { border: 2px dashed var(--photo-green); border-radius: 11px; }
  .avatar-overlay { position: absolute; inset: 0; display: grid; place-items: center; background: #e2f2e9dd; color: var(--photo-green); font: 600 12px 'Be Vietnam Pro', sans-serif; pointer-events: none; }
  .avatar-editor.dragging .avatar-photo { border-color: #61a581; }
  .spinner { display: block; width: 20px; height: 20px; border: 2px solid #94b9a5; border-top-color: var(--photo-green); border-radius: 50%; animation: spin .8s linear infinite; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (max-width: 560px) { .cover-editor { height: 185px; } .cover-toolbar { inset: 12px 12px auto; } .identity-row { gap: 11px; flex-wrap: wrap; margin-left: 10px; margin-right: 10px; } .avatar-editor { width: 88px; height: 88px; flex-basis: 88px; } .identity-copy { flex: 1; } .identity-copy strong { font-size: 17px; } .avatar-button { margin: 2px 0 0 99px; } .photo-help { margin-left: 10px; margin-right: 10px; } .cover-hint { bottom: 8px; font-size: 9px; } }
  @media (prefers-reduced-motion: reduce) { button { transition: none; } .spinner { animation: none; } }
</style>
