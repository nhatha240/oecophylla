import { randomUUID } from 'node:crypto';
import { request as apiRequest, test, expect } from '@playwright/test';

test('sidebar follows saved topics and a reader’s post actions', async ({ page, baseURL }) => {
  const suffix = randomUUID().replaceAll('-', '').slice(-12);
  const headers = { origin: baseURL!, 'x-requested-with': 'oec-web' };
  const reader = `reader_${suffix}`;
  expect((await page.request.post('/api/v1/auth/register', {
    headers,
    data: { username: reader, email: `${reader}@test.local`, password: `${randomUUID()}!Aa1` }
  })).ok()).toBeTruthy();

  await page.goto('/settings');
  const sidebar = page.getByRole('complementary', { name: 'Điều hướng chính' });
  await expect(sidebar.getByRole('link', { name: 'Chọn chủ đề yêu thích' })).toBeVisible();
  await page.getByRole('checkbox', { name: 'Công nghệ' }).check();
  await page.getByRole('button', { name: 'Lưu sở thích' }).click();
  await expect(sidebar.getByRole('link', { name: 'Công nghệ' })).toHaveAttribute('href', '/topic/tech');
  await expect(sidebar.getByRole('link', { name: 'Khoa học' })).toHaveCount(0);

  const authorRequest = await apiRequest.newContext({ baseURL: baseURL!, extraHTTPHeaders: headers });
  try {
    const author = `author_${suffix}`;
    expect((await authorRequest.post('/api/v1/auth/register', {
      data: { username: author, email: `${author}@test.local`, password: `${randomUUID()}!Aa1` }
    })).ok()).toBeTruthy();
    const postResponse = await authorRequest.post('/api/v1/posts', {
      data: { content: `Bài khoa học ${suffix}`, tags: [], topics: ['science'] }
    });
    expect(postResponse.ok()).toBeTruthy();
    const { id: postId } = await postResponse.json();

    await page.goto(`/post/${postId}`);
    await page.getByRole('button', { name: 'Thích bài viết' }).click();
    await expect(sidebar.getByRole('link', { name: 'Khoa học' })).toHaveAttribute('href', '/topic/science', { timeout: 12_000 });
    await expect(sidebar.getByRole('link', { name: 'Công nghệ' })).toBeVisible();
  } finally {
    await authorRequest.dispose();
  }
});
