<script lang="ts">
  import { tick } from 'svelte';
  import { searchUsers } from '$lib/api';
  import { insertMention, mentionAtCaret } from '$lib/mentions';
  import type { Profile } from '$lib/types';

  export let value = '';
  export let name: string | undefined = undefined;
  export let id: string | undefined = undefined;
  export let rows = 3;
  export let maxlength = 2000;
  export let placeholder = '';
  export let ariaLabel = 'Nội dung';
  export let required = false;
  export let minHeight = 'auto';

  let textarea: HTMLTextAreaElement;
  let suggestions: Profile[] = [];
  let visible = false;
  let activeIndex = 0;
  let searchTimer: ReturnType<typeof setTimeout>;
  let searchVersion = 0;

  function refresh(): void {
    clearTimeout(searchTimer);
    const mention = mentionAtCaret(value, textarea.selectionStart);
    if (!mention || mention.query.length < 2) {
      visible = false;
      suggestions = [];
      searchVersion++;
      return;
    }
    const version = ++searchVersion;
    searchTimer = setTimeout(async () => {
      try {
        const result = await searchUsers(fetch, mention.query, 6);
        if (version !== searchVersion) return;
        suggestions = result.items;
        activeIndex = 0;
        visible = suggestions.length > 0;
      } catch {
        if (version === searchVersion) visible = false;
      }
    }, 180);
  }

  async function choose(person: Profile): Promise<void> {
    const updated = insertMention(value, textarea.selectionStart, person.username);
    value = updated.value;
    visible = false;
    suggestions = [];
    searchVersion++;
    await tick();
    textarea.focus();
    textarea.setSelectionRange(updated.caret, updated.caret);
  }

  function keydown(event: KeyboardEvent): void {
    if (!visible) return;
    if (event.key === 'Escape') { visible = false; return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = (activeIndex + (event.key === 'ArrowDown' ? 1 : -1) + suggestions.length) % suggestions.length;
    } else if (event.key === 'Enter' && suggestions[activeIndex]) {
      event.preventDefault();
      void choose(suggestions[activeIndex]);
    }
  }
  function keyup(event: KeyboardEvent): void {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) refresh();
  }
</script>

<div class="mention-field">
  <textarea bind:this={textarea} bind:value {name} {id} {rows} {maxlength} {placeholder} {required}
    aria-label={ariaLabel} aria-autocomplete="list"
    style:min-height={minHeight} on:input={refresh} on:click={refresh} on:keyup={keyup} on:keydown={keydown}></textarea>
  {#if visible}
    <div class="mention-menu" role="listbox" aria-label="Gắn tên người dùng">
      {#each suggestions as person, index (person.id)}
        <button type="button" role="option" aria-selected={index === activeIndex}
          class:active={index === activeIndex} on:mousedown|preventDefault
          on:click={() => choose(person)}>
          <span class="initial">{(person.display_name ?? person.username).slice(0, 1).toUpperCase()}</span>
          <span><strong>{person.display_name ?? person.username}</strong><small>@{person.username}</small></span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .mention-field { width: 100%; position: relative; }
  textarea { display: block; width: 100%; padding: 12px; resize: vertical; border: 1px solid #dfe8e3; border-radius: 8px; outline: 0; color: #173d36; background: white; font: 12px/1.6 'Lora', serif; }
  textarea:focus { border-color: #4e8e7e; box-shadow: 0 0 0 3px #e3f1eb; }
  .mention-menu { position: absolute; z-index: 20; top: 100%; left: 0; right: 0; margin-top: 4px; padding: 5px; border: 1px solid #dfe8e3; border-radius: 9px; background: white; box-shadow: 0 12px 28px #173d361c; }
  .mention-menu button { display: flex; align-items: center; gap: 9px; width: 100%; padding: 7px; border: 0; border-radius: 6px; background: transparent; text-align: left; color: #234b41; cursor: pointer; }
  .mention-menu button:hover, .mention-menu button.active { background: #edf4ef; }
  .initial { display: grid; place-items: center; width: 29px; height: 29px; border-radius: 50%; background: #dcece5; color: #1d5b54; font: 600 13px 'Lora', serif; }
  .mention-menu strong, .mention-menu small { display: block; font-size: 11px; }
  .mention-menu small { color: #799087; }
</style>
