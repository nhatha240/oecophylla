import { test, expect, request as playwrightRequest } from '@playwright/test';

import { loginUser, randomUser, registerUser } from './helpers';

test('full social and personalized-news journey', async ({ browser }) => {
  test.setTimeout(90_000);
  const authorContext = await browser.newContext();
  const authorPage = await authorContext.newPage();
  const author = randomUser('journey_author');
  const backendSetup = await playwrightRequest.newContext({ baseURL: 'http://localhost:8001' });
  const authorRegistration = await backendSetup.post('/api/v1/auth/register', {
    data: {
      username: author.username,
      display_name: author.displayName,
      email: author.email,
      password: author.password,
    },
  });
  expect(authorRegistration.ok()).toBeTruthy();
  await backendSetup.dispose();
  await loginUser(authorPage, author);

  const meResponse = await authorPage.request.get('/api/v1/auth/me');
  expect(meResponse.ok()).toBeTruthy();
  const authorId = (await meResponse.json()).user.id as string;

  const postContent = `Công nghệ AI trong khoa học — E2E ${Date.now()}`;
  await authorPage.goto('/post/new');
  await authorPage.locator('textarea[name="content"]').fill(postContent);
  await authorPage.locator('input[name="tags"]').fill('tech,ai');
  await authorPage.getByTestId('composer-submit').click();
  await authorPage.waitForURL(/\/post\//);
  const postId = new URL(authorPage.url()).pathname.split('/').pop()!;

  const readerContext = await browser.newContext({
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  await readerContext.addInitScript(() => {
    Object.defineProperty(Navigator.prototype, 'share', {
      configurable: true,
      value: undefined,
    });
  });
  const readerPage = await readerContext.newPage();
  const reader = randomUser('journey_reader');

  // Registration is exercised here; explicit login was exercised by the author.
  await registerUser(readerPage, reader);

  // Follow the author and consume their post from the following feed.
  await readerPage.goto(`/profile/${authorId}`);
  const followResponse = readerPage.waitForResponse(
    (response) => response.url().endsWith(`/api/v1/users/${authorId}/follow`)
      && response.request().method() === 'POST'
  );
  await readerPage.getByRole('button', { name: '+ Theo dõi', exact: true }).click();
  expect((await followResponse).status()).toBe(201);
  await expect(
    readerPage.locator('.profile-head-actions').getByRole('button', { name: 'Đang theo dõi' })
  ).toBeVisible();

  await readerPage.goto('/?feed=following');
  const article = readerPage.locator('article', { hasText: postContent });
  await expect(article).toBeVisible({ timeout: 15_000 });
  const likeButton = article.locator('button.post-action.like');
  await likeButton.click();
  await expect(likeButton).toHaveAttribute('aria-pressed', 'true');

  await article.locator(`a[href="/post/${postId}"]`).first().click();
  await expect(readerPage).toHaveURL(new RegExp(`/post/${postId}$`));

  const comment = `Bình luận hành trình ${Date.now()}`;
  await readerPage.locator('textarea[placeholder="Viết bình luận của bạn…"]').fill(comment);
  await readerPage.getByRole('button', { name: 'Gửi' }).click();
  await expect(readerPage.getByText(comment)).toBeVisible({ timeout: 10_000 });

  // Desktop Chromium uses the clipboard fallback. The backend share is sent
  // only after the copy succeeds, and repeated clicks stay idempotent.
  const shareButton = readerPage.getByTestId('share-button');
  const firstShareResponse = readerPage.waitForResponse(
    (response) => response.url().endsWith(`/api/v1/posts/${postId}/share`)
      && response.request().method() === 'POST'
  );
  await shareButton.click();
  expect((await firstShareResponse).ok()).toBeTruthy();
  await expect(shareButton).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => readerPage.evaluate(() => navigator.clipboard.readText()))
    .toBe(`http://localhost:4173/post/${postId}`);

  const recordedShares: string[] = [];
  readerPage.on('request', (request) => {
    if (request.url().endsWith(`/api/v1/posts/${postId}/share`)) recordedShares.push(request.url());
  });
  await shareButton.click();
  await readerPage.waitForTimeout(250);
  expect(recordedShares).toHaveLength(0);

  // Follow a topic, then request the personalized feed with the refreshed state.
  await readerPage.goto('/settings');
  const technology = readerPage.getByLabel('Công nghệ');
  if (!(await technology.isChecked())) await technology.check();
  const topicUpdate = readerPage.waitForResponse(
    (response) => response.url().includes('/api/v1/users/')
      && response.request().method() === 'PUT'
  );
  await readerPage.getByRole('button', { name: 'Lưu sở thích' }).click();
  expect((await topicUpdate).ok()).toBeTruthy();

  const profileResponse = await readerPage.request.get('/api/v1/auth/me');
  const readerId = (await profileResponse.json()).user.id as string;
  const updatedProfile = await readerPage.request.get(`/api/v1/users/${readerId}`);
  expect((await updatedProfile.json()).topic_prefs).toContain('tech');

  const recommendedFeed = await readerPage.request.get('/api/v1/feed?limit=20');
  expect(recommendedFeed.ok()).toBeTruthy();
  const feedPayload = await recommendedFeed.json();
  expect(Array.isArray(feedPayload.items)).toBeTruthy();
  expect(feedPayload).toHaveProperty('source');

  await readerPage.goto('/');
  await expect(readerPage.getByTestId('feed-heading')).toBeVisible();

  await readerContext.close();
  await authorContext.close();
});
