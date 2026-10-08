import { randomUUID } from 'node:crypto';
import { expect, test, type Page } from '@playwright/test';

async function discussion(page: Page, baseURL: string) {
  const username = `delete_${randomUUID().replaceAll('-', '').slice(-12)}`;
  const headers = { origin: baseURL, 'x-requested-with': 'oec-web' };
  const registration = await page.request.post('/api/v1/auth/register', {
    headers, data: { username, display_name: 'Minh Anh', email: `${username}@test.local`, password: `${randomUUID()}!Aa1` },
  });
  expect(registration.ok()).toBeTruthy();
  const post = await page.request.post('/api/v1/posts', {
    headers, data: { content: 'Một cuộc thảo luận về không gian xanh trong thành phố.', tags: [], topics: [] },
  });
  expect(post.ok()).toBeTruthy();
  const { id: postId } = await post.json();
  const parent = await page.request.post(`/api/v1/posts/${postId}/comments`, {
    headers, data: { content: 'Mình nghĩ những khu vườn nhỏ có thể tạo nên thay đổi lớn cho cộng đồng.', parent_comment_id: null },
  });
  expect(parent.ok()).toBeTruthy();
  const { id: commentId } = await parent.json();
  const reply = await page.request.post(`/api/v1/posts/${postId}/comments`, {
    headers, data: { content: 'Cùng bắt đầu từ khu phố của mình nhé!', parent_comment_id: commentId },
  });
  expect(reply.ok()).toBeTruthy();
  await page.goto(`/post/${postId}`);
  return { commentId, postId };
}

test('cancel and Escape keep the comment and restore keyboard focus', async ({ page, baseURL }) => {
  await discussion(page, baseURL!);
  let deletes = 0;
  page.on('request', (request) => { if (request.method() === 'DELETE') deletes++; });
  const trigger = page.getByRole('button', { name: 'Xóa', exact: true }).first();
  const modal = page.getByRole('dialog', { name: 'Xóa bình luận?', exact: true });
  await trigger.click();
  await expect(modal).toBeVisible();
  await expect(modal.getByText('Mình nghĩ những khu vườn nhỏ có thể tạo nên thay đổi lớn cho cộng đồng.', { exact: true })).toBeVisible();
  await expect(modal.getByText('Các câu trả lời bên dưới cũng sẽ bị ẩn.', { exact: true })).toBeVisible();
  await expect(modal.getByRole('button', { name: 'Hủy', exact: true })).toBeFocused();
  await modal.getByRole('button', { name: 'Hủy', exact: true }).click();
  await expect(modal).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.keyboard.press('Escape');
  await expect(modal).not.toBeVisible();
  await expect(trigger).toBeFocused();
  expect(deletes).toBe(0);
  await page.reload();
  await expect(page.locator('.comments').getByText('Mình nghĩ những khu vườn nhỏ có thể tạo nên thay đổi lớn cho cộng đồng.', { exact: true })).toBeVisible();
});

test('delete shows progress, keeps errors in the modal, and can retry successfully', async ({ page, baseURL }) => {
  const { commentId } = await discussion(page, baseURL!);
  let release!: () => void;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  let attempts = 0;
  await page.route(`**/api/v1/comments/${commentId}`, async (route) => {
    if (route.request().method() !== 'DELETE') { await route.continue(); return; }
    attempts++;
    if (attempts > 1) { await route.continue(); return; }
    await hold;
    await route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ error: { code: 'FORBIDDEN' } }) });
  });
  await page.getByRole('button', { name: 'Xóa', exact: true }).first().click();
  const modal = page.getByRole('dialog', { name: 'Xóa bình luận?', exact: true });
  await expect(modal).toBeVisible();
  await modal.getByRole('button', { name: 'Xóa bình luận', exact: true }).click();
  try {
    await expect(modal.getByRole('button', { name: 'Đang xóa…', exact: true })).toBeDisabled();
    await expect(modal.getByRole('button', { name: 'Hủy', exact: true })).toBeDisabled();
    await page.keyboard.press('Escape');
    await expect(modal).toBeVisible();
  } finally { release(); }
  await expect(modal.getByRole('alert')).toHaveText('Không thể xóa bình luận. Vui lòng thử lại.');
  await modal.getByRole('button', { name: 'Xóa bình luận', exact: true }).click();
  await expect(modal).not.toBeVisible();
  await expect(page.locator('.comments').getByText('Mình nghĩ những khu vườn nhỏ có thể tạo nên thay đổi lớn cho cộng đồng.', { exact: true })).not.toBeVisible();
  await expect(page.locator('.comments').getByText('Cùng bắt đầu từ khu phố của mình nhé!', { exact: true })).not.toBeVisible();
  expect(attempts).toBe(2);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Thảo luận (0)', exact: true })).toBeVisible();
});
