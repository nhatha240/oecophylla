<script lang="ts">
  import { onDestroy } from 'svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import { appendPostImages, MAX_POST_IMAGES } from '$lib/postImages';

  export let files: File[] = [];
  export let existingUrls: string[] = [];
  export let inputId = 'post-images';
  export let locked = false;
  export let allowRemoveExisting = true;
  export let error = '';

  let input: HTMLInputElement;
  let previews: { file: File; url: string }[] = [];
  let dragDepth = 0;
  let dragging = false;

  $: syncPreviews(files);

  $: gallery = [
    ...existingUrls.map((url, index) => ({ key: `existing-${index}-${url}`, url, kind: 'existing' as const, index })),
    ...previews.map(({ url }, index) => ({ key: `selected-${index}-${url}`, url, kind: 'selected' as const, index }))
  ];
  $: imageCount = existingUrls.length + files.length;

  onDestroy(() => previews.forEach(({ url }) => URL.revokeObjectURL(url)));

  function syncPreviews(selectedFiles: File[]) {
    const next = selectedFiles.map((file) => previews.find((preview) => preview.file === file)
      ?? { file, url: URL.createObjectURL(file) });
    for (const preview of previews) {
      if (!next.includes(preview)) URL.revokeObjectURL(preview.url);
    }
    previews = next;
  }

  function addFiles(incoming: File[]) {
    if (locked) return;
    const result = appendPostImages(files, incoming, existingUrls.length);
    if (result.error) {
      error = result.error;
      return;
    }
    if (!incoming.length) return;
    files = result.files;
    error = '';
  }

  function selected(event: Event) {
    const picker = event.currentTarget as HTMLInputElement;
    addFiles(Array.from(picker.files ?? []));
    picker.value = '';
  }

  function removePhoto(kind: 'existing' | 'selected', index: number) {
    if (locked) return;
    if (kind === 'existing') {
      if (allowRemoveExisting) existingUrls = existingUrls.filter((_, item) => item !== index);
    } else {
      files = files.filter((_, item) => item !== index);
    }
    error = '';
  }

  function dragEnter(event: DragEvent) {
    event.preventDefault();
    if (locked) return;
    dragDepth += 1;
    dragging = true;
  }

  function dragLeave(event: DragEvent) {
    event.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) dragging = false;
  }

  function dragOver(event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = locked ? 'none' : 'copy';
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    dragDepth = 0;
    dragging = false;
    addFiles(Array.from(event.dataTransfer?.files ?? []));
  }
</script>

<section class="image-picker" class:dragging aria-label="Ảnh bài viết" data-testid="post-image-picker"
  on:dragenter={dragEnter} on:dragleave={dragLeave} on:dragover={dragOver} on:drop={drop}>
  {#if gallery.length}
    <div class="gallery" class:single={gallery.length === 1} class:pair={gallery.length === 2}
      class:trio={gallery.length === 3} class:many={gallery.length > 4} data-testid="post-image-gallery">
      {#each gallery as photo, position (photo.key)}
        <figure class="photo">
          <img src={photo.url} alt={'Ảnh xem trước ' + (position + 1)} />
          {#if !locked && (photo.kind === 'selected' || allowRemoveExisting)}
            <button type="button" class="remove-photo" aria-label={'Xóa ảnh ' + (position + 1)}
              title="Xóa ảnh" on:click={() => removePhoto(photo.kind, photo.index)}>×</button>
          {/if}
        </figure>
      {/each}
    </div>
  {/if}

  <div class="dropzone" class:has-photos={gallery.length > 0}>
    <div class="image-mark" aria-hidden="true"><Icon name="Image" size={23} /></div>
    <div class="drop-copy">
      <strong>{gallery.length ? 'Thêm ảnh vào bài viết' : 'Thêm ảnh vào bài viết của bạn'}</strong>
      <span>Kéo thả ảnh vào đây hoặc chọn từ thiết bị</span>
    </div>
    <button type="button" class="choose-photo" on:click={() => input.click()}
      disabled={locked || imageCount >= MAX_POST_IMAGES}>Chọn ảnh</button>
    <input bind:this={input} id={inputId} type="file" accept="image/jpeg,image/png,image/webp"
      multiple aria-label="Chọn tệp ảnh" on:change={selected} disabled={locked || imageCount >= MAX_POST_IMAGES} />
  </div>

  <div class="image-meta"><span>JPEG, PNG hoặc WebP · tối đa 5 MB mỗi ảnh</span><span>{imageCount}/{MAX_POST_IMAGES} ảnh</span></div>
  {#if error}<p class="image-error" role="alert">{error}</p>{/if}
  {#if dragging}<div class="drop-overlay" aria-hidden="true"><span>Thả ảnh để thêm vào bài viết</span></div>{/if}
</section>

<style>
  .image-picker { position: relative; display: grid; gap: 9px; min-width: 0; }
  .gallery { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: repeat(2, minmax(0, 1fr)); gap: 3px; height: clamp(240px, 34vw, 390px); overflow: hidden; border: 1px solid #d9e6df; border-radius: 10px; background: white; }
  .gallery.single { display: block; height: auto; aspect-ratio: 1.7; }
  .gallery.pair { grid-template-rows: 1fr; aspect-ratio: 1.65; height: auto; }
  .gallery.trio .photo:first-child { grid-row: span 2; }
  .gallery.many { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .photo { position: relative; min-width: 0; min-height: 0; margin: 0; overflow: hidden; background: #e8efea; }
  .photo img { display: block; width: 100%; height: 100%; object-fit: cover; }
  .remove-photo { position: absolute; top: 10px; right: 10px; width: 32px; height: 32px; display: grid; place-items: center; border: 1px solid #ffffff88; border-radius: 50%; background: #183e3dcc; color: white; font-size: 24px; line-height: 1; cursor: pointer; transition: background .15s, transform .15s; }
  .remove-photo:hover { background: #982e32; transform: scale(1.06); }
  .remove-photo:focus-visible, .choose-photo:focus-visible { outline: 3px solid #58aa8c; outline-offset: 2px; }
  .dropzone { display: flex; align-items: center; gap: 14px; min-height: 104px; padding: 16px 18px; border: 1.5px dashed #a9c8b8; border-radius: 10px; background: linear-gradient(120deg, #f5faf6, #fbfdf9); }
  .dropzone.has-photos { min-height: 83px; border-style: solid; }
  .image-mark { flex: 0 0 46px; width: 46px; height: 46px; display: grid; place-items: center; border-radius: 12px; background: #e0f1e6; color: #197250; }
  .drop-copy { display: grid; gap: 4px; min-width: 0; }
  .drop-copy strong { color: #183b33; font: 600 15px 'Lora', serif; }
  .drop-copy span { color: #69867a; font-size: 12px; line-height: 1.4; }
  .choose-photo { flex: 0 0 auto; margin-left: auto; padding: 9px 16px; border: 1px solid #1d6a54; border-radius: 99px; background: #1d6a54; color: white; font-size: 12px; font-weight: 650; cursor: pointer; }
  .choose-photo:hover:not(:disabled) { background: #11523f; }
  .choose-photo:disabled { opacity: .5; cursor: not-allowed; }
  input[type='file'] { position: absolute; width: 1px; height: 1px; padding: 0; opacity: 0; pointer-events: none; }
  .image-meta { display: flex; justify-content: space-between; gap: 10px; color: #879a91; font-size: 11px; }
  .image-error { margin: 0; color: #aa4348; font-size: 12px; }
  .drop-overlay { position: absolute; z-index: 5; inset: 0; display: grid; place-items: center; border: 2px dashed #187c5e; border-radius: 10px; background: #dff2e9ed; color: #135d46; font: 600 18px 'Lora', serif; pointer-events: none; }
  @media (max-width: 560px) { .dropzone { flex-wrap: wrap; gap: 10px; padding: 14px; } .image-mark { flex-basis: 38px; width: 38px; height: 38px; } .drop-copy { flex: 1 1 calc(100% - 52px); } .choose-photo { margin-left: 48px; } .gallery { height: 285px; } .gallery.pair { aspect-ratio: 1.2; } .gallery.single { aspect-ratio: 1.2; } }
  @media (prefers-reduced-motion: reduce) { .remove-photo { transition: none; } }
</style>
