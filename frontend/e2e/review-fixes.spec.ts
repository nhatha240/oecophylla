import { expect, test } from '@playwright/test';
import { randomUser } from './helpers';

test('authenticated settings survives avatar upload, profile save, and reload', async ({ page }) => {
  const user = randomUser('review');
  const registered = await page.request.post('/api/v1/auth/register', { data: user });
  expect(registered.status()).toBe(200);
  const id = (await registered.json()).user.id as string;

  await page.goto('/settings');
  await expect(page.locator('#display-name')).toBeVisible();
  await page.locator('#avatar-file').setInputFiles({
    name: 'avatar.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64')
  });
  const uploaded = page.waitForResponse((response) => response.url().includes(`/users/${id}/avatar`) && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Tải avatar lên' }).click();
  expect((await uploaded).status()).toBe(200);
  await expect(page.locator('#avatar-url')).toHaveValue(new RegExp(`/api/v1/users/${id}/avatar\\?v=`));

  const name = `Updated ${user.username}`;
  await page.locator('#display-name').fill(name);
  await page.locator('#bio').fill('Profile saved after avatar upload');
  const saved = page.waitForResponse((response) => response.url().endsWith(`/api/v1/users/${id}`) && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Lưu hồ sơ', exact: true }).click();
  expect((await saved).status()).toBe(200);
  await page.reload();
  await expect(page.locator('#display-name')).toHaveValue(name);
  await expect(page.locator('#bio')).toHaveValue('Profile saved after avatar upload');
  await expect(page.locator('#avatar-url')).toHaveValue(new RegExp(`/api/v1/users/${id}/avatar\\?v=`));
});
