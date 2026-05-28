<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import { user } from '$lib/stores/auth';
  import { apiFetch, ApiException, changePassword, deleteAccount } from '$lib/api';
  import { showToast } from '$lib/stores/toast';
  import type { Profile } from '$lib/types';

  export let data: { profile: Profile };

  let displayName = data.profile.display_name ?? '';
  let bio = data.profile.bio ?? '';
  let avatarUrl = data.profile.avatar_url ?? '';
  let topicPrefs = new Set(data.profile.topic_prefs ?? []);

  let savingProfile = false;
  let savingTopics = false;

  // Change password state
  let currentPassword = '';
  let newPassword = '';
  let confirmNewPassword = '';
  let changingPassword = false;

  // Delete account state
  let showDeleteDialog = false;
  let deletePassword = '';
  let deleteConfirmText = '';
  let deleting = false;

  const allTopics: { key: string; label: string }[] = [
    { key: 'tech', label: 'Công nghệ' },
    { key: 'science', label: 'Khoa học' },
    { key: 'sports', label: 'Thể thao' },
    { key: 'politics', label: 'Chính trị' },
    { key: 'entertainment', label: 'Giải trí' },
    { key: 'health', label: 'Sức khỏe' },
    { key: 'business', label: 'Kinh doanh' },
    { key: 'culture', label: 'Văn hóa' },
    { key: 'education', label: 'Giáo dục' },
    { key: 'environment', label: 'Môi trường' }
  ];

  $: bioLength = bio.length;
  $: passwordMismatch = confirmNewPassword.length > 0 && newPassword !== confirmNewPassword;
  $: passwordTooShort = newPassword.length > 0 && newPassword.length < 8;
  $: canChangePassword = currentPassword.length > 0 && newPassword.length >= 8 && newPassword === confirmNewPassword && !changingPassword;
  $: canDeleteAccount = deletePassword.length > 0 && deleteConfirmText === 'XÓA' && !deleting;

  onMount(() => {
    if (!$user) goto('/login');
  });

  function toggleTopic(key: string) {
    const next = new Set(topicPrefs);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    topicPrefs = next;
  }

  async function saveProfile() {
    if (!$user) return;
    savingProfile = true;
    try {
      await apiFetch(fetch, `/users/${$user.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          display_name: displayName || null,
          bio: bio || null,
          avatar_url: avatarUrl || null
        })
      });
      showToast('Đã lưu hồ sơ.');
    } catch (e) {
      const msg = e instanceof ApiException ? e.code : 'Không lưu được hồ sơ.';
      showToast(msg);
    } finally {
      savingProfile = false;
    }
  }

  async function saveTopics() {
    if (!$user) return;
    savingTopics = true;
    try {
      await apiFetch(fetch, `/users/${$user.id}`, {
        method: 'PUT',
        body: JSON.stringify({ topic_prefs: [...topicPrefs] })
      });
      showToast('Đã lưu sở thích chủ đề.');
    } catch (e) {
      const msg = e instanceof ApiException ? e.code : 'Không lưu được sở thích.';
      showToast(msg);
    } finally {
      savingTopics = false;
    }
  }

  async function handleChangePassword() {
    if (!canChangePassword) return;
    changingPassword = true;
    try {
      await changePassword(fetch, { current_password: currentPassword, new_password: newPassword });
      showToast('Đã đổi mật khẩu.');
      currentPassword = '';
      newPassword = '';
      confirmNewPassword = '';
    } catch (e) {
      if (e instanceof ApiException && e.status === 401) {
        showToast('Mật khẩu hiện tại không đúng.');
      } else {
        showToast('Không đổi được mật khẩu.');
      }
    } finally {
      changingPassword = false;
    }
  }

  async function handleDeleteAccount() {
    if (!canDeleteAccount) return;
    deleting = true;
    try {
      await deleteAccount(fetch, { password: deletePassword });
      showToast('Tài khoản đã bị vô hiệu hóa.');
      await goto('/login');
    } catch (e) {
      if (e instanceof ApiException && e.status === 401) {
        showToast('Mật khẩu không đúng.');
      } else {
        showToast('Không xóa được tài khoản.');
      }
    } finally {
      deleting = false;
    }
  }
</script>

<svelte:head>
  <title>Cài đặt — Oecophylla</title>
</svelte:head>

<div class="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-8">
  <h1 class="text-2xl font-semibold tracking-tight">Cài đặt</h1>

  <!-- Section 1: Hồ sơ -->
  <section class="glass-surface rounded-2xl p-6 flex flex-col gap-5">
    <h2 class="text-lg font-medium">Hồ sơ</h2>

    <div class="flex items-start gap-4">
      <div class="flex-1 flex flex-col gap-1.5">
        <label for="avatar-url" class="text-sm font-medium text-slate-600">Avatar URL</label>
        <input
          id="avatar-url"
          type="text"
          bind:value={avatarUrl}
          placeholder="https://..."
          class="rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white/60 focus:outline-none focus:ring-2 focus:ring-slate-300"
        />
      </div>
      <div class="shrink-0 mt-6">
        {#if avatarUrl}
          <img
            src={avatarUrl}
            alt="Avatar preview"
            class="w-14 h-14 rounded-xl object-cover border border-slate-200"
            on:error={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
          />
        {:else}
          <div class="w-14 h-14 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-400 text-xl font-semibold">
            {(data.profile.username ?? '?').slice(0, 1).toUpperCase()}
          </div>
        {/if}
      </div>
    </div>

    <div class="flex flex-col gap-1.5">
      <label for="display-name" class="text-sm font-medium text-slate-600">Tên hiển thị</label>
      <input
        id="display-name"
        type="text"
        bind:value={displayName}
        placeholder="Tên của bạn"
        maxlength="100"
        class="rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white/60 focus:outline-none focus:ring-2 focus:ring-slate-300"
      />
    </div>

    <div class="flex flex-col gap-1.5">
      <div class="flex items-center justify-between">
        <label for="bio" class="text-sm font-medium text-slate-600">Bio</label>
        <span class="text-xs text-slate-400">{bioLength}/500</span>
      </div>
      <textarea
        id="bio"
        bind:value={bio}
        placeholder="Giới thiệu ngắn về bạn…"
        maxlength="500"
        rows="3"
        class="rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white/60 resize-none focus:outline-none focus:ring-2 focus:ring-slate-300"
      ></textarea>
    </div>

    <div class="flex justify-end">
      <button
        class="btn emerald px-5 py-2 text-sm rounded-xl disabled:opacity-50"
        on:click={saveProfile}
        disabled={savingProfile}
      >
        {savingProfile ? 'Đang lưu…' : 'Lưu hồ sơ'}
      </button>
    </div>
  </section>

  <!-- Section 2: Sở thích chủ đề -->
  <section class="glass-surface rounded-2xl p-6 flex flex-col gap-5">
    <h2 class="text-lg font-medium">Sở thích chủ đề</h2>

    <div class="grid grid-cols-2 gap-3">
      {#each allTopics as t}
        <label class="flex items-center gap-2.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={topicPrefs.has(t.key)}
            on:change={() => toggleTopic(t.key)}
            class="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
          />
          <span class="text-sm">{t.label}</span>
        </label>
      {/each}
    </div>

    <div class="flex justify-end">
      <button
        class="btn emerald px-5 py-2 text-sm rounded-xl disabled:opacity-50"
        on:click={saveTopics}
        disabled={savingTopics}
      >
        {savingTopics ? 'Đang lưu…' : 'Lưu sở thích'}
      </button>
    </div>
  </section>

  <!-- Section 3: Đổi mật khẩu -->
  <section class="glass-surface rounded-2xl p-6 flex flex-col gap-5">
    <h2 class="text-lg font-medium">Đổi mật khẩu</h2>

    <div class="flex flex-col gap-1.5">
      <label for="current-password" class="text-sm font-medium text-slate-600">Mật khẩu hiện tại</label>
      <input
        id="current-password"
        type="password"
        bind:value={currentPassword}
        autocomplete="current-password"
        class="rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white/60 focus:outline-none focus:ring-2 focus:ring-slate-300"
      />
    </div>

    <div class="flex flex-col gap-1.5">
      <label for="new-password" class="text-sm font-medium text-slate-600">Mật khẩu mới</label>
      <input
        id="new-password"
        type="password"
        bind:value={newPassword}
        autocomplete="new-password"
        class="rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white/60 focus:outline-none focus:ring-2 focus:ring-slate-300"
      />
      {#if passwordTooShort}
        <p class="text-xs text-red-500">Mật khẩu phải có ít nhất 8 ký tự.</p>
      {/if}
    </div>

    <div class="flex flex-col gap-1.5">
      <label for="confirm-new-password" class="text-sm font-medium text-slate-600">Xác nhận mật khẩu mới</label>
      <input
        id="confirm-new-password"
        type="password"
        bind:value={confirmNewPassword}
        autocomplete="new-password"
        class="rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white/60 focus:outline-none focus:ring-2 focus:ring-slate-300"
      />
      {#if passwordMismatch}
        <p class="text-xs text-red-500">Mật khẩu xác nhận không khớp.</p>
      {/if}
    </div>

    <div class="flex justify-end">
      <button
        class="btn emerald px-5 py-2 text-sm rounded-xl disabled:opacity-50"
        on:click={handleChangePassword}
        disabled={!canChangePassword}
      >
        {changingPassword ? 'Đang đổi…' : 'Đổi mật khẩu'}
      </button>
    </div>
  </section>

  <!-- Section 4: Xóa tài khoản -->
  <section class="glass-surface rounded-2xl p-6 flex flex-col gap-4">
    <h2 class="text-lg font-medium text-red-600">Vùng nguy hiểm</h2>

    <div class="flex items-center justify-between">
      <div>
        <div class="text-sm font-medium text-red-500">Xóa tài khoản</div>
        <div class="text-xs text-slate-400">Vô hiệu hóa tài khoản. Dữ liệu sẽ không bị xóa cứng.</div>
      </div>
      <button
        class="px-4 py-1.5 text-sm rounded-xl border border-red-300 text-red-500 hover:bg-red-50 transition"
        on:click={() => { showDeleteDialog = true; deletePassword = ''; deleteConfirmText = ''; }}
      >
        Xóa tài khoản
      </button>
    </div>

    {#if showDeleteDialog}
      <div class="rounded-xl border border-red-200 bg-red-50 p-5 flex flex-col gap-4">
        <p class="text-sm text-red-700 font-medium">Hành động này không thể hoàn tác. Tài khoản sẽ bị vô hiệu hóa.</p>

        <div class="flex flex-col gap-1.5">
          <label for="delete-password" class="text-sm font-medium text-slate-600">Nhập mật khẩu để xác nhận</label>
          <input
            id="delete-password"
            type="password"
            bind:value={deletePassword}
            autocomplete="current-password"
            class="rounded-xl border border-red-200 px-3 py-2 text-sm bg-white/60 focus:outline-none focus:ring-2 focus:ring-red-300"
          />
        </div>

        <div class="flex flex-col gap-1.5">
          <label for="delete-confirm" class="text-sm font-medium text-slate-600">Gõ <span class="font-mono font-bold">XÓA</span> để xác nhận</label>
          <input
            id="delete-confirm"
            type="text"
            bind:value={deleteConfirmText}
            placeholder="XÓA"
            class="rounded-xl border border-red-200 px-3 py-2 text-sm bg-white/60 focus:outline-none focus:ring-2 focus:ring-red-300"
          />
        </div>

        <div class="flex justify-end gap-3">
          <button
            class="px-4 py-1.5 text-sm rounded-xl border border-slate-200 hover:bg-slate-50 transition"
            on:click={() => { showDeleteDialog = false; }}
          >
            Hủy
          </button>
          <button
            class="px-4 py-1.5 text-sm rounded-xl bg-red-600 text-white disabled:opacity-50 hover:bg-red-700 transition"
            on:click={handleDeleteAccount}
            disabled={!canDeleteAccount}
          >
            {deleting ? 'Đang xóa…' : 'Xác nhận xóa'}
          </button>
        </div>
      </div>
    {/if}
  </section>
</div>
