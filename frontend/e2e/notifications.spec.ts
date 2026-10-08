import { randomUUID } from 'node:crypto';
import { request as apiRequest, test, expect } from '@playwright/test';

test('post owner receives like and comment notifications', async ({ page, baseURL }) => {
  const suffix = randomUUID().replaceAll('-', '').slice(-12);
  const headers = { origin: baseURL!, 'x-requested-with': 'oec-web' };
  const owner = `owner_${suffix}`;
  const actor = `actor_${suffix}`;
  const ownerRegistration = await page.request.post('/api/v1/auth/register', {
    headers,
    data: { username: owner, email: `${owner}@test.local`, display_name: 'Chủ bài viết', password: `${randomUUID()}!Aa1` }
  });
  expect(ownerRegistration.ok()).toBeTruthy();
  const postResponse = await page.request.post('/api/v1/posts', {
    headers,
    data: { content: `Bài viết thông báo ${suffix}`, tags: [], topics: [] }
  });
  expect(postResponse.ok()).toBeTruthy();
  const { id: postId } = await postResponse.json();

  const streamReady = page.waitForResponse((response) => response.url().endsWith('/api/v1/notifications/stream') && response.status() === 200);
  await page.goto('/notifications');
  await streamReady;

  const actorRequest = await apiRequest.newContext({ baseURL: baseURL!, extraHTTPHeaders: headers });
  try {
    const actorRegistration = await actorRequest.post('/api/v1/auth/register', {
      data: { username: actor, email: `${actor}@test.local`, display_name: 'Người bình luận', password: `${randomUUID()}!Aa1` }
    });
    expect(actorRegistration.ok()).toBeTruthy();
    expect((await actorRequest.post(`/api/v1/posts/${postId}/like`)).status()).toBe(201);
    expect((await actorRequest.post(`/api/v1/posts/${postId}/comments`, {
      data: { content: 'Bình luận thử thông báo' }
    })).ok()).toBeTruthy();

    await expect.poll(async () => {
      const response = await page.request.get('/api/v1/notifications');
      const body = await response.json();
      return body.items?.filter((item: { kind: string }) => item.kind === 'liked' || item.kind === 'commented').length;
    }, { timeout: 15_000 }).toBe(2);

    await expect(page.locator('article strong').first()).toContainText(new RegExp(`Người bình luận|${actor}`));
    await expect(page.getByText('đã thích bài viết của bạn', { exact: false })).toBeVisible();
    await expect(page.getByText('đã bình luận về bài viết của bạn', { exact: false })).toBeVisible();
    await expect(page.getByText('Bình luận thử thông báo')).toBeVisible();
    await expect(page.getByRole('link', { name: /Thông báo, 2 chưa đọc/ })).toBeVisible();
    await page.getByRole('button', { name: 'Đánh dấu đã đọc' }).last().click();
    await expect(page.getByRole('link', { name: /Thông báo, 1 chưa đọc/ })).toBeVisible();
    await page.getByRole('link', { name: /đã bình luận về bài viết của bạn/ }).click();
    await expect(page).toHaveURL(new RegExp(`/post/${postId}#comments$`));
  } finally {
    await actorRequest.dispose();
  }
});
