<script lang="ts">
  import type { PageData } from './$types';
  import type { Profile } from '$lib/types';
  import { page } from '$app/stores';
  import { apiFetch, followUser, unfollowUser } from '$lib/api';
  export let data: PageData;
  let profile: Profile = data.profile;
  let editing = false;
  let name = profile.display_name ?? '';
  let bio = profile.bio ?? '';
  let avatarUrl = profile.avatar_url ?? '';
  let following = profile.is_following ?? false;
  let saving = false;
  let feedback = '';
  $: isOwner = $page.data.user?.id === profile.id;
  function edit() { name = profile.display_name ?? ''; bio = profile.bio ?? ''; avatarUrl = profile.avatar_url ?? ''; editing = true; }
  async function save() { saving = true; feedback = ''; try { profile = await apiFetch<Profile>(fetch, '/users/' + profile.id, { method: 'PUT', body: JSON.stringify({ display_name: name || null, bio: bio || null, avatar_url: avatarUrl || null, topic_prefs: profile.topic_prefs }) }); editing = false; feedback = 'Đã lưu thay đổi.'; } catch { feedback = 'Chưa lưu được hồ sơ.'; } finally { saving = false; } }
  async function toggleFollow() { saving = true; feedback = ''; try { if (following) await unfollowUser(fetch, profile.id); else await followUser(fetch, profile.id); following = !following; } catch { feedback = 'Không thể cập nhật theo dõi.'; } finally { saving = false; } }
</script>
<svelte:head><title>{profile.display_name ?? profile.username} — Oecophylla</title></svelte:head>
<div class="profile-page"><header><p class="eyebrow">CỘNG ĐỒNG OECOPHYLLA</p><h1 class="serif">{isOwner ? 'Quản lý hồ sơ' : 'Hồ sơ thành viên'}</h1><p>Một hồ sơ đầy đủ giúp xây dựng những cuộc thảo luận chất lượng.</p></header><div class="profile-grid"><section class="profile-panel">{#if editing}<h2 class="serif">Thông tin cá nhân</h2><div class="edit-top"><div class="avatar">{#if avatarUrl}<img src={avatarUrl} alt="" />{:else}{(name || profile.username).slice(0,1).toUpperCase()}{/if}</div><p>Chỉnh sửa thông tin hiển thị trên hồ sơ cộng đồng của bạn.</p></div><label for="name">Họ tên</label><input id="name" bind:value={name} maxlength="100" /><label for="avatar">Đường dẫn ảnh đại diện</label><input id="avatar" type="url" bind:value={avatarUrl} placeholder="https://..." /><label for="bio">Tiểu sử</label><textarea id="bio" bind:value={bio} rows="4" maxlength="280"></textarea><p class="field-label">Chủ đề quan tâm</p><div class="chips">{#each profile.topic_prefs as topic}<span>{topic}</span>{/each}</div><div class="buttons"><button class="pill-primary" disabled={saving} on:click={save}>Lưu thay đổi</button><button class="pill-outline" on:click={() => editing = false}>Hủy</button></div>{:else}<div class="cover"></div><div class="profile-head"><div class="avatar large">{#if profile.avatar_url}<img src={profile.avatar_url} alt="" />{:else}{(profile.display_name ?? profile.username).slice(0,1).toUpperCase()}{/if}</div><div class="buttons">{#if isOwner}<a class="pill-outline" href="/my-posts">Bài viết của tôi</a><button class="pill-outline" on:click={edit}>Chỉnh sửa hồ sơ</button>{:else}<button class={following ? 'pill-outline' : 'pill-primary'} disabled={saving} on:click={toggleFollow}>{following ? 'Đang theo dõi' : 'Theo dõi'}</button>{/if}</div></div><h2 class="serif">{profile.display_name ?? profile.username}</h2><p class="handle">@{profile.username}</p><p class="bio">{profile.bio ?? 'Thành viên Oecophylla đang cùng khám phá những câu chuyện đáng suy ngẫm.'}</p><div class="stats"><div><strong>{data.posts.length}</strong><span>Bài viết</span></div><div><strong>{profile.topic_prefs.length}</strong><span>Chủ đề quan tâm</span></div></div><div class="chips">{#each profile.topic_prefs as topic}<span>{topic}</span>{/each}</div>{/if}{#if feedback}<p class="feedback" role="status">{feedback}</p>{/if}{#if isOwner}<form class="signout" method="POST" action="/logout"><button type="submit">Đăng xuất</button></form>{/if}</section><aside class="profile-rail"><img src="/brand/city.jpg" alt="Thành phố Việt Nam bên sông" /><h3 class="serif">Tri thức kết nối con người</h3><p>Những góc nhìn tử tế cùng tạo nên thay đổi lớn.</p><small>Tham gia từ {new Intl.DateTimeFormat('vi-VN').format(new Date(profile.created_at))}</small></aside></div><section class="posts"><h2 class="serif">Bài viết</h2>{#if data.posts.length}<div class="post-list">{#each data.posts as post}<a href={'/post/' + post.id}><span class="eyebrow">{post.topics?.[0] ?? 'BÀI VIẾT'}</span><h3 class="serif">{post.content.slice(0, 165)}{post.content.length > 165 ? '…' : ''}</h3><small>{new Intl.DateTimeFormat('vi-VN').format(new Date(post.created_at))}</small></a>{/each}</div>{:else}<p class="empty">Chưa có bài viết nào.</p>{/if}</section></div>
<style>
  .profile-page { max-width: 1160px; margin: auto; padding: 31px 34px 60px; }
  header h1 { margin: 8px 0 3px; font-size: 35px; font-weight: 500; letter-spacing: -.05em; }
  header p:last-child { margin: 0 0 22px; color: #72877e; font: 13px/1.5 'Lora', serif; }
  .profile-grid { display: grid; grid-template-columns: minmax(0,1.5fr) minmax(260px,.8fr); gap: 15px; }
  .profile-panel, .profile-rail { overflow: hidden; border: 1px solid #e7eeea; border-radius: 9px; background: white; }
  .profile-panel { padding: 20px; }
  .cover { height: 170px; margin: -20px -20px 0; background: linear-gradient(0deg, #173f3880, transparent), url('/brand/city.jpg') center 62%/cover; }
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
  .edit-top { display: flex; gap: 12px; align-items: center; margin-top: 15px; }
  .edit-top p { color: #81948b; font-size: 12px; }
  .profile-panel > .buttons { margin-top: 25px; }
  .feedback { color: #45756b; font-size: 12px; }
  .empty { color: #8a9b91; font-size: 12px; }
  @media (max-width: 900px) { .profile-grid { display: block; } .profile-rail { display: none; } }
  @media (max-width: 720px) { .profile-page { padding: 21px 14px 35px; } header h1 { font-size: 28px; } .post-list { grid-template-columns: 1fr; } }
  .signout { display: none; }
  @media (max-width: 720px) { .signout { display: block; margin-top: 28px; } .signout button { border: 0; background: transparent; color: #698579; font-size: 12px; text-decoration: underline; } }
</style>
