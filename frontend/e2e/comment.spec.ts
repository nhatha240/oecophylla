/** Live API regression: receipt-only comment responses must render without crashing,
 * including when background recommendation batches fail. Requires the local stack. */
import { randomUUID } from 'node:crypto';
import { test, expect } from '@playwright/test';

for (const batchFails of [false, true]) {
  test(`comments remain usable when telemetry batch ${batchFails ? 'fails' : 'succeeds'}`, async ({ page, baseURL }) => {
    const username = `cmt_${randomUUID().replaceAll('-', '').slice(-12)}`;
    const headers = { origin: baseURL!, 'x-requested-with': 'oec-web' };
    const registration = await page.request.post('/api/v1/auth/register', {
      headers,
      data: { username, email: `${username}@test.local`, display_name: 'Comment regression', password: `${randomUUID()}!Aa1` },
    });
    expect(registration.ok()).toBeTruthy();
    const post = await page.request.post('/api/v1/posts', {
      headers, data: { content: `Comment regression ${username}`, tags: [], topics: [] },
    });
    expect(post.ok()).toBeTruthy();
    const { id } = await post.json();
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    if (batchFails) {
      await page.route('**/api/v1/interactions/events/batch', (route) => route.fulfill({
        status: 503, contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'UNAVAILABLE', message: 'Test batch outage' } }),
      }));
    }
    const batchResponse = page.waitForResponse((response) => response.url().endsWith('/interactions/events/batch'));
    await page.goto(`/post/${id}`);
    await page.locator('.reading-region').scrollIntoViewIfNeeded();
    expect((await batchResponse).status()).toBe(batchFails ? 503 : 200);
    const texts = Array.from({ length: 12 }, (_, index) => `Live comment ${index + 1}`);
    for (const text of texts) {
      await page.getByRole('textbox', { name: 'Bình luận', exact: true }).fill(text);
      const submitted = page.waitForResponse((response) => response.url().endsWith(`/posts/${id}/comments`) && response.request().method() === 'POST');
      await page.getByRole('button', { name: 'Gửi bình luận', exact: true }).click();
      expect((await submitted).status()).toBe(200);
      await expect(page.locator('.comments').getByText(text, { exact: true })).toBeVisible();
      await expect(page.getByRole('textbox', { name: 'Bình luận', exact: true })).toHaveValue('');
    }
    await expect(page.getByRole('button', { name: 'Thích bài viết' })).toBeEnabled();
    await expect(page.getByRole('heading', { name: 'Thảo luận (12)', exact: true })).toBeVisible();
    await page.reload();
    await expect(page.locator('.comments').getByText(texts[0], { exact: true })).toBeVisible();
    await expect(page.locator('.comments').getByText(texts[11], { exact: true })).toBeVisible();
    expect(errors).toEqual([]);
  });
}

async function createTestPost(page: import('@playwright/test').Page, baseURL: string) {
  const username = `cmt_${randomUUID().replaceAll('-', '').slice(-12)}`;
  const headers = { origin: baseURL, 'x-requested-with': 'oec-web' };
  const registration = await page.request.post('/api/v1/auth/register', {
    headers, data: { username, email: `${username}@test.local`, password: `${randomUUID()}!Aa1` },
  });
  expect(registration.ok()).toBeTruthy();
  const post = await page.request.post('/api/v1/posts', {
    headers, data: { content: `Comment regression ${username}`, tags: [], topics: [] },
  });
  expect(post.ok()).toBeTruthy();
  return { id: (await post.json()).id as string, headers };
}

test('can submit another comment while the comment list refresh is delayed', async ({ page, baseURL }) => {
  const { id } = await createTestPost(page, baseURL!);
  await page.goto(`/post/${id}`);
  let release!: () => void;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  let refreshStarted!: () => void;
  const started = new Promise<void>((resolve) => { refreshStarted = resolve; });
  let heldFirstRefresh = false;
  const staleResponse = page.waitForResponse((response) => response.headers()['x-test-stale-refresh'] === 'true');
  await page.route(`**/api/v1/posts/${id}/comments?*`, async (route) => {
    if (heldFirstRefresh) { await route.continue(); return; }
    heldFirstRefresh = true;
    const response = await route.fetch();
    refreshStarted();
    await hold;
    await route.fulfill({ response, headers: { ...response.headers(), 'x-test-stale-refresh': 'true' } });
  });
  try {
    await page.getByRole('textbox', { name: 'Bình luận', exact: true }).fill('First comment with slow refresh');
    await page.getByRole('button', { name: 'Gửi bình luận', exact: true }).click();
    await started;
    await expect(page.locator('.comments').getByText('First comment with slow refresh', { exact: true })).toBeVisible();
    await page.getByRole('textbox', { name: 'Bình luận', exact: true }).fill('Second comment with slow refresh');
    await expect(page.getByRole('button', { name: 'Gửi bình luận', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: 'Gửi bình luận', exact: true }).click();
    await expect(page.locator('.comments').getByText('Second comment with slow refresh', { exact: true })).toBeVisible();
  } finally {
    release();
  }
  await (await staleResponse).finished();
  // Let the late response and Svelte's render settle before checking for lost comments.
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.locator('.comments').getByText('First comment with slow refresh', { exact: true })).toBeVisible();
  await expect(page.locator('.comments').getByText('Second comment with slow refresh', { exact: true })).toBeVisible();
});

test('comment reads do not consume the write allowance', async ({ page, baseURL }) => {
  const { id, headers } = await createTestPost(page, baseURL!);
  for (let i = 0; i < 20; i++) {
    const read = await page.request.get(`/api/v1/posts/${id}/comments`, { headers });
    expect(read.status()).toBe(200);
  }
  for (let i = 0; i < 3; i++) {
    const sent = await page.request.post(`/api/v1/posts/${id}/comments`, {
      headers, data: { content: `Consecutive comment ${i}`, parent_comment_id: null },
    });
    expect(sent.status()).toBe(200);
  }
});
