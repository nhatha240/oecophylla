<script lang="ts">
  import type { PageData } from './$types';
  import type { Profile } from '$lib/types';
  import { page } from '$app/stores';
  import { apiFetch, followUser, unfollowUser, uploadAvatar, uploadCover } from '$lib/api';
  import { user } from '$lib/stores/auth';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import ProfilePhotoEditor from '$lib/components/ProfilePhotoEditor.svelte';
  export let data: PageData;
  let profile: Profile = data.profile;
  let editing = false;
  let name = profile.display_name ?? '';
  let bio = profile.bio ?? '';
  let avatarUrl = profile.avatar_url ?? '';
  let following = profile.is_following ?? false;
  let saving = false;
  let uploading: 'avatar' | 'cover' | null = null;
  let feedback = '';
  let feedbackError = false;
  $: isOwner = $page.data.user?.id === profile.id;
  function edit() { name = profile.display_name ?? ''; bio = profile.bio ?? ''; avatarUrl = profile.avatar_url ?? ''; feedback = ''; editing = true; }
  async function save() { if (saving || uploading) return; saving = true; feedback = ''; feedbackError = false; try { profile = await apiFetch<Profile>(fetch, '/users/' + profile.id, { method: 'PUT', body: JSON.stringify({ display_name: name || null, bio: bio || null, avatar_url: avatarUrl || null, topic_prefs: profile.topic_prefs }) }); editing = false; feedback = 'Đã lưu thay đổi.'; } catch { feedback = 'Chưa lưu được hồ sơ.'; feedbackError = true; } finally { saving = false; } }
  async function toggleFollow() { saving = true; feedback = ''; feedbackError = false; try { if (following) await unfollowUser(fetch, profile.id); else await followUser(fetch, profile.id); following = !following; } catch { feedback = 'Không thể cập nhật theo dõi.'; feedbackError = true; } finally { saving = false; } }
  async function uploadPhoto(file: File, kind: 'avatar' | 'cover') {
    if (!isOwner || uploading || saving) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size === 0 || file.size > 5 * 1024 * 1024) {
      feedback = 'Chọn ảnh JPEG, PNG hoặc WebP tối đa 5 MB.';
      feedbackError = true;
      return;
    }
    uploading = kind;
    feedback = '';
    feedbackError = false;
    try {
      if (kind === 'avatar') {
        const result = await uploadAvatar(fetch, profile.id, file);
        avatarUrl = result.avatar_url;
        profile = { ...profile, avatar_url: result.avatar_url };
        if ($user?.id === profile.id) $user = { ...$user, avatar_url: result.avatar_url };
      } else {
        const result = await uploadCover(fetch, profile.id, file);
        profile = { ...profile, cover_url: result.cover_url };
      }
      feedback = 'Đã tải ảnh lên.';
    } catch {
      feedback = 'Không tải được ảnh. Vui lòng thử lại.';
      feedbackError = true;
    } finally {
      uploading = null;
    }
  }
</script>
<svelte:head><title>{profile.display_name ?? profile.username} — Oecophylla</title></svelte:head>
<div class="profile-page">
  <header><p class="eyebrow">CỘNG ĐỒNG OECOPHYLLA</p><h1 class="serif">{isOwner ? 'Quản lý hồ sơ' : 'Hồ sơ thành viên'}</h1><p>Một hồ sơ đầy đủ giúp xây dựng những cuộc thảo luận chất lượng.</p></header>
  <div class="profile-grid" class:editing>
    <section class="profile-panel" class:editing-panel={editing}>
      {#if editing}
        <div class="edit-heading"><div><h2 class="serif">Thông tin cá nhân</h2><p>Thêm một chút về bạn để kết nối với cộng đồng.</p></div><span class="editing-badge"><Icon name="Edit" size={12} /> Chỉnh sửa hồ sơ</span></div>
        <ProfilePhotoEditor {avatarUrl} coverUrl={profile.cover_url ?? ''} {name} username={profile.username}
          {uploading} disabled={saving} on:select={({ detail }) => uploadPhoto(detail.file, detail.kind)}
          on:invalid={({ detail }) => { feedback = detail; feedbackError = true; }} />
        {#if feedback}<p class="feedback" class:feedback-error={feedbackError} role={feedbackError ? 'alert' : 'status'}><Icon name={feedbackError ? 'AlertCircle' : 'Check'} size={15} />{feedback}</p>{/if}
        <div class="profile-fields">
          <div class="field-group"><label for="name">Họ tên</label><input id="name" bind:value={name} maxlength="100" autocomplete="name" disabled={saving} placeholder="Tên bạn muốn mọi người gọi" /><small>Tên sẽ hiển thị trên hồ sơ và bài viết của bạn.</small></div>
          <div class="field-group"><div class="label-row"><label for="bio">Đôi nét về bạn</label><span>{bio.length}/280</span></div><textarea id="bio" bind:value={bio} rows="3" maxlength="280" disabled={saving} placeholder="Chia sẻ điều bạn quan tâm, công việc hoặc một câu chuyện ngắn về mình…"></textarea></div>
          <div class="topic-field"><div class="label-row"><p class="field-label">Chủ đề quan tâm</p><a href="/settings">Chỉnh sửa <Icon name="ArrowRight" size={12} /></a></div><div class="chips">{#each profile.topic_prefs as topic}<span>{topic}</span>{:else}<p class="topic-empty">Chọn chủ đề để khám phá những câu chuyện gần với bạn hơn.</p>{/each}</div></div>
          <details class="avatar-url-option"><summary>Thêm ảnh đại diện bằng đường dẫn</summary><label for="avatar">Đường dẫn ảnh đại diện</label><input id="avatar" type="url" bind:value={avatarUrl} disabled={saving || !!uploading} placeholder="https://..." /></details>
        </div>
        <div class="edit-footer"><p><Icon name="Check" size={13} /> Ảnh được lưu ngay sau khi tải lên.</p><div class="buttons"><button type="button" class="pill-outline" disabled={saving || !!uploading} on:click={() => editing = false}>Hủy</button><button type="button" class="pill-primary" disabled={saving || !!uploading} on:click={save}><Icon name="Check" size={15} />{saving ? 'Đang lưu…' : 'Lưu thay đổi'}</button></div></div>
      {:else}
        <div class="cover">{#if profile.cover_url}<img src={profile.cover_url} alt="Ảnh bìa hồ sơ" />{/if}</div>
        <div class="profile-head"><div class="avatar large">{#if profile.avatar_url}<img src={profile.avatar_url} alt="" />{:else}{(profile.display_name ?? profile.username).slice(0,1).toUpperCase()}{/if}</div><div class="buttons">{#if isOwner}<a class="pill-outline" href="/my-posts">Bài viết của tôi</a><button class="pill-outline" on:click={edit}>Chỉnh sửa hồ sơ</button>{:else}<button class={following ? 'pill-outline' : 'pill-primary'} disabled={saving} on:click={toggleFollow}>{following ? 'Đang theo dõi' : 'Theo dõi'}</button>{/if}</div></div>
        <h2 class="serif">{profile.display_name ?? profile.username}</h2><p class="handle">@{profile.username}</p><p class="bio">{profile.bio ?? 'Thành viên Oecophylla đang cùng khám phá những câu chuyện đáng suy ngẫm.'}</p><div class="stats"><div><strong>{data.posts.length}</strong><span>Bài viết</span></div><div><strong>{profile.topic_prefs.length}</strong><span>Chủ đề quan tâm</span></div></div><div class="chips">{#each profile.topic_prefs as topic}<span>{topic}</span>{/each}</div>
        {#if feedback}<p class="feedback" class:feedback-error={feedbackError} role={feedbackError ? 'alert' : 'status'}>{feedback}</p>{/if}
      {/if}
      {#if isOwner}<form class="signout" method="POST" action="/logout"><button type="submit">Đăng xuất</button></form>{/if}
    </section>
    <aside class="profile-rail"><img src="/brand/city.jpg" alt="Thành phố Việt Nam bên sông" /><h3 class="serif">Tri thức kết nối con người</h3><p>Những góc nhìn tử tế cùng tạo nên thay đổi lớn.</p><small>Tham gia từ {new Intl.DateTimeFormat('vi-VN').format(new Date(profile.created_at))}</small></aside>
  </div>
  {#if !editing}<section class="posts"><h2 class="serif">Bài viết</h2>{#if data.posts.length}<div class="post-list">{#each data.posts as post}<a href={'/post/' + post.id}><span class="eyebrow">{post.topics?.[0] ?? 'BÀI VIẾT'}</span><h3 class="serif">{post.content.slice(0, 165)}{post.content.length > 165 ? '…' : ''}</h3><small>{new Intl.DateTimeFormat('vi-VN').format(new Date(post.created_at))}</small></a>{/each}</div>{:else}<p class="empty">Chưa có bài viết nào.</p>{/if}</section>{/if}
</div>
<style>
  .profile-page { max-width: 1160px; margin: auto; padding: 31px 34px 60px; }
  header h1 { margin: 8px 0 3px; font-size: 35px; font-weight: 500; letter-spacing: -.05em; }
  header p:last-child { margin: 0 0 22px; color: #72877e; font: 13px/1.5 'Lora', serif; }
  .profile-grid { display: grid; grid-template-columns: minmax(0,1.5fr) minmax(260px,.8fr); gap: 15px; }
  .profile-panel, .profile-rail { overflow: hidden; border: 1px solid #e7eeea; border-radius: 9px; background: white; }
  .profile-panel { padding: 20px; }
  .profile-grid.editing { grid-template-columns: minmax(0, 1fr) 245px; gap: 20px; }
  .editing-panel { padding: 24px; border-radius: 14px; }
  .edit-heading { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 22px; }
  .profile-panel .edit-heading h2 { margin: 0; font-size: 25px; }
  .edit-heading p { margin: 7px 0 0; color: #809388; font-size: 11px; line-height: 1.7; }
  .editing-badge { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 5px; padding: 7px 9px; border: 1px solid #e0ebe3; border-radius: 6px; background: #f5f8f2; color: #648272; font-size: 10px; }
  .profile-fields { display: grid; gap: 22px; margin-top: 27px; }
  .field-group label, .topic-field .field-label { margin: 0 0 8px; color: #2c5042; font: 600 12px 'Lora', serif; }
  .field-group input, .field-group textarea, .avatar-url-option input { padding: 12px 13px; border-radius: 8px; background: #fcfdfb; color: #1f4539; font-size: 12px; transition: border-color .15s, box-shadow .15s; }
  .field-group input:focus, .field-group textarea:focus, .avatar-url-option input:focus { border-color: #68a087; box-shadow: 0 0 0 3px #e9f3ec; }
  .field-group input::placeholder, .field-group textarea::placeholder { color: #9ca9a1; }
  .field-group textarea { min-height: 104px; line-height: 1.7; }
  .field-group small { display: block; margin-top: 7px; color: #93a095; font-size: 10px; }
  .label-row { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
  .label-row > span { color: #91a296; font-size: 10px; font-variant-numeric: tabular-nums; }
  .label-row a { display: inline-flex; align-items: center; gap: 5px; color: #56836d; font-size: 10px; }
  .topic-field .chips { margin: 0; }
  .topic-empty { margin: 0; color: #91a296; font-size: 11px; line-height: 1.7; }
  .avatar-url-option summary { width: fit-content; color: #6e8879; font-size: 11px; cursor: pointer; }
  .edit-footer { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 26px; padding-top: 19px; border-top: 1px solid #edf1e9; }
  .edit-footer p { display: flex; align-items: center; gap: 5px; margin: 0; color: #90a091; font-size: 10px; line-height: 1.6; }
  .edit-footer p :global(svg) { flex: 0 0 auto; }
  .edit-footer .buttons { flex: 0 0 auto; }
  .edit-footer .pill-primary { gap: 6px; }
  .cover { height: 170px; margin: -20px -20px 0; background: linear-gradient(0deg, #173f3880, transparent), url('/brand/city.jpg') center 62%/cover; overflow: hidden; }
  .cover img { width: 100%; height: 100%; object-fit: cover; }
  .profile-head { display: flex; justify-content: space-between; align-items: end; margin-top: -40px; }
  .avatar { width: 86px; height: 86px; display: grid; place-items: center; overflow: hidden; border: 4px solid white; border-radius: 50%; background: #dcece5; color: #1d5b54; font: 600 35px 'Lora', serif; }
  .avatar.large { width: 98px; height: 98px; }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .profile-panel h2 { margin: 14px 0 0; font-size: 25px; font-weight: 500; }
  .handle { margin: 3px 0 12px; color: #8b9c94; font-size: 11px; }
  .bio { max-width: 540px; color: #5e7369; font: 13px/1.7 'Lora', serif; }
  .stats { display: flex; gap: 0; margin: 20px 0; padding: 16px 0; border-top: 1px solid #edf1ee; border-bottom: 1px solid #edf1ee; }
  .stats div { display: grid; gap: 3px; min-width: 120px; border-right: 1px solid #e5ebe7; }
  .stats div + div { padding-left: 25px; }
  .stats div:last-child { border: 0; }
  .stats strong { font: 600 18px 'Lora', serif; }
  .stats span { color: #83968b; font-size: 10px; }
  .chips { display: flex; gap: 7px; flex-wrap: wrap; margin: 10px 0; }
  .chips span { padding: 7px 11px; border-radius: 20px; background: #edf5f0; color: #35695e; font-size: 10px; }
  .buttons { display: flex; gap: 8px; }
  .profile-rail { padding: 15px; align-self: start; }
  .profile-rail img { width: 100%; height: 170px; object-fit: cover; border-radius: 6px; }
  .profile-rail h3 { margin: 14px 0 5px; font-size: 19px; font-weight: 500; }
  .profile-rail p { color: #71867b; font: italic 13px/1.6 'Lora', serif; }
  .profile-rail small { color: #90a096; }
  .posts { margin-top: 30px; }
  .posts h2 { font-size: 22px; font-weight: 500; }
  .post-list { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 11px; }
  .post-list a { padding: 18px; border: 1px solid #e7eeea; border-radius: 8px; background: white; }
  .post-list h3 { margin: 8px 0; font-size: 16px; font-weight: 500; }
  .post-list small { color: #8fa097; }
  label, .field-label { display: block; margin: 17px 0 7px; font: 600 12px 'Lora', serif; }
  input, textarea { width: 100%; padding: 11px; border: 1px solid #dce7e1; border-radius: 6px; outline: 0; background: #fff; font-size: 12px; }
  textarea { resize: vertical; }
  .feedback { display: flex; align-items: center; gap: 7px; margin: 14px 0 0; padding: 10px 12px; border-radius: 7px; background: #f0f7f1; color: #45756b; font-size: 11px; line-height: 1.6; }
  .feedback-error { background: #fcf0ee; color: #a6534f; }
  .empty { color: #8a9b91; font-size: 12px; }
  @media (max-width: 900px) { .profile-grid { display: block; } .profile-rail { display: none; } }
  @media (max-width: 1100px) { .profile-grid.editing { display: block; } .editing .profile-rail { display: none; } }
  @media (max-width: 720px) { .profile-page { padding: 21px 14px 35px; } header h1 { font-size: 28px; } .post-list { grid-template-columns: 1fr; } .editing-panel { padding: 18px; } .editing-badge { display: none; } .edit-heading { margin-bottom: 18px; } .edit-heading h2 { font-size: 23px; } .edit-footer { flex-wrap: wrap; gap: 14px; } .edit-footer .buttons { width: 100%; } .edit-footer .pill-primary { flex: 1; } }
  @media (prefers-reduced-motion: reduce) { .field-group input, .field-group textarea, .avatar-url-option input { transition: none; } }
  .signout { display: none; }
  @media (max-width: 720px) { .signout { display: block; margin-top: 28px; } .signout button { border: 0; background: transparent; color: #698579; font-size: 12px; text-decoration: underline; } }
</style>
