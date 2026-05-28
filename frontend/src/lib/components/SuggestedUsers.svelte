<script lang="ts">
  import { onMount } from 'svelte';
  import { getUserSuggestions, followUser, type SuggestionItem } from '$lib/api';
  import { user } from '$lib/stores/auth';
  import { showToast } from '$lib/stores/toast';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  let suggestions: SuggestionItem[] = [];
  let loading = true;
  let error: string | null = null;

  onMount(async () => {
    try {
      suggestions = await getUserSuggestions(fetch, 5);
    } catch {
      error = 'Không thể tải gợi ý';
    } finally {
      loading = false;
    }
  });

  async function follow(suggestion: SuggestionItem): Promise<void> {
    const prev = suggestions;
    suggestions = suggestions.filter((s) => s.id !== suggestion.id);
    try {
      await followUser(fetch, suggestion.id);
    } catch {
      suggestions = prev;
      showToast('Không theo dõi được. Thử lại sau.');
    }
  }
</script>

{#if $user}
  <div class="rail-card">
    <h4><Icon name="Users" size={16} className="pin" /> Có thể bạn biết</h4>

    {#if loading}
      {#each [1, 2, 3] as _}
        <div class="suggestion-row">
          <div class="avatar s36 skeleton"></div>
          <div style="flex: 1; min-width: 0;">
            <div class="skeleton" style="width: 60%; height: 14px; border-radius: 4px;"></div>
            <div class="skeleton" style="width: 40%; height: 12px; border-radius: 4px; margin-top: 4px;"></div>
          </div>
        </div>
      {/each}
    {:else if error}
      <p class="muted" style="font-size: 13px; padding: 8px 0;">{error}</p>
    {:else if suggestions.length === 0}
      <p class="muted" style="font-size: 13px; padding: 8px 0;">Hãy theo dõi ai đó để thấy gợi ý.</p>
    {:else}
      {#each suggestions as s (s.id)}
        <div class="suggestion-row">
          <a class="avatar s36" href="/profile/{s.id}">
            {s.username.slice(0, 1).toUpperCase()}
          </a>
          <div style="flex: 1; min-width: 0;">
            <a class="suggestion-name" href="/profile/{s.id}">
              {s.display_name ?? s.username}
            </a>
            {#if s.mutual_count > 0}
              <span class="suggestion-meta">{s.mutual_count} người quen theo dõi</span>
            {:else}
              <span class="suggestion-meta">@{s.username}</span>
            {/if}
          </div>
          <button class="glass-chip text-xs" type="button" on:click={() => follow(s)}>
            Theo dõi
          </button>
        </div>
      {/each}
    {/if}
  </div>
{/if}

<style>
  .suggestion-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
  }
  .suggestion-row + .suggestion-row {
    border-top: 1px solid rgba(0, 0, 0, 0.05);
  }
  .suggestion-name {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: var(--text, #1e293b);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .suggestion-name:hover {
    text-decoration: underline;
  }
  .suggestion-meta {
    display: block;
    font-size: 12px;
    color: var(--muted, #94a3b8);
  }
  .skeleton {
    background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
</style>
