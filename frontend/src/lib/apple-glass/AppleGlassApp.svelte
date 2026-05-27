<script lang="ts">
  import { onMount } from 'svelte';
  import AdminPages from './admin/AdminPages.svelte';
  import AdminShell from './admin/AdminShell.svelte';
  import AuthScreen from './components/AuthScreen.svelte';
  import Explore from './components/Explore.svelte';
  import Feed from './components/Feed.svelte';
  import Icon from './components/Icon.svelte';
  import MobilePreview from './components/MobilePreview.svelte';
  import NotificationsPopover from './components/NotificationsPopover.svelte';
  import Onboarding from './components/Onboarding.svelte';
  import Profile from './components/Profile.svelte';
  import Reader from './components/Reader.svelte';
  import Sidebar from './components/Sidebar.svelte';
  import Toast from './components/Toast.svelte';
  import Topbar from './components/Topbar.svelte';
  import { POSTS, type Post } from './data';

  import './styles/tokens.css';
  import './styles/atoms.css';
  import './styles/shell.css';
  import './styles/feed.css';
  import './styles/pages.css';
  import './styles/admin.css';
  import './styles/responsive.css';
  import './styles/glass.css';

  type Screen = 'auth' | 'onboarding' | 'feed' | 'article' | 'explore' | 'profile' | 'saved' | 'follow' | 'group' | 'admin' | 'mobile';

  let theme: 'light' | 'dark' = 'light';
  let screen: Screen = 'feed';
  let adminPage = 'overview';
  let openPost: Post | null = null;
  let toast = '';
  let notifOpen = false;

  $: crumbs =
    screen === 'feed'
      ? 'Bảng tin <em>· Dành cho bạn</em>'
      : screen === 'explore'
        ? 'Khám phá'
        : screen === 'profile'
          ? 'Hồ sơ của bạn'
          : screen === 'article'
            ? 'Bài viết <em>· chi tiết</em>'
            : screen === 'saved'
              ? 'Đã lưu'
              : screen === 'follow'
                ? 'Đang theo dõi'
                : screen === 'group'
                  ? 'Nhóm'
                  : '';

  $: if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme);
  }

  onMount(() => {
    document.documentElement.setAttribute('data-theme', theme);
  });

  function showToast(message: string) {
    toast = message;
  }

  function nav(next: string) {
    if (next === 'landing') return;
    if (next === 'notif') {
      notifOpen = !notifOpen;
      return;
    }
    screen = next as Screen;
    openPost = null;
  }

  function openArticle(post: Post) {
    openPost = post;
    screen = 'article';
  }
</script>

{#if screen === 'auth'}
  <AuthScreen onContinue={() => (screen = 'onboarding')} />
{:else if screen === 'onboarding'}
  <Onboarding onDone={() => { screen = 'feed'; showToast('Bảng tin của bạn đã sẵn sàng!'); }} />
{:else if screen === 'mobile'}
  <Topbar crumbs="Mobile preview" search={false} {theme} onTheme={() => (theme = theme === 'dark' ? 'light' : 'dark')} />
  <MobilePreview onBack={() => (screen = 'feed')} />
{:else if screen === 'admin'}
  <AdminShell page={adminPage} onNav={(page) => (adminPage = page)} onExit={() => (screen = 'feed')}>
    <AdminPages page={adminPage} onJump={(page) => (adminPage = page)} />
  </AdminShell>
{:else}
  <div class="app">
    <Sidebar active={screen === 'article' ? 'feed' : screen} counts={{ notif: 3 }} onNav={nav} />
    <div>
      <Topbar crumbs={crumbs} search {theme} onTheme={() => (theme = theme === 'dark' ? 'light' : 'dark')} onAdmin={() => { screen = 'admin'; adminPage = 'overview'; }} onNotif={() => (notifOpen = !notifOpen)}>
        <button slot="right" class="btn ghost sm" on:click={() => (screen = 'mobile')}><Icon name="Globe" size={13} /> Xem mobile</button>
      </Topbar>
      {#if screen === 'feed'}
        <Feed onOpenPost={openArticle} toast={showToast} />
      {:else if screen === 'article'}
        <Reader post={openPost ?? POSTS[0]} onBack={() => (screen = 'feed')} toast={showToast} />
      {:else if screen === 'explore'}
        <Explore onOpenPost={openArticle} />
      {:else if screen === 'profile'}
        <Profile />
      {:else}
        <div class="placeholder">
          <h2 class="serif">{screen === 'saved' ? 'Đã lưu' : screen === 'follow' ? 'Đang theo dõi' : 'Nhóm'}</h2>
          <p class="muted">Màn hình này được phác thảo cho giai đoạn tiếp theo.</p>
          <button class="btn emerald sm" on:click={() => (screen = 'feed')}><Icon name="ArrowLeft" size={12} /> Trở về bảng tin</button>
        </div>
      {/if}
    </div>
    <NotificationsPopover open={notifOpen} onClose={() => (notifOpen = false)} />
  </div>
{/if}

{#if toast}
  <Toast message={toast} onClose={() => (toast = '')} />
{/if}

<style>
  .placeholder {
    max-width: 720px;
    margin: 60px auto;
    padding: 0 32px;
    text-align: center;
  }
  .placeholder h2 {
    font-weight: 500;
    font-size: 32px;
    letter-spacing: -0.015em;
    margin: 0 0 8px;
  }
</style>
