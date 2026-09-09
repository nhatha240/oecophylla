import { expect, test } from '@playwright/test';
import { randomUser, registerUser } from './helpers';

test('post owner edits content from the profile card', async ({ page }) => {
  const user = randomUser('postedit');
  await registerUser(page, user);

  const me = await page.request.get('/api/v1/auth/me');
  const userId = (await me.json()).user.id as string;
  const original = `Bài trước khi sửa ${Date.now()}`;
  const updated = `Bài sau khi sửa ${Date.now()}`;

  await page.goto('/post/new');
  await page.locator('textarea[name="content"]').fill(original);
  await page.getByTestId('composer-submit').click();
  await page.waitForURL(/\/post\//);

  await page.goto(`/profile/${userId}`);
  const article = page.locator('article', { hasText: original });
  await article.getByRole('link', { name: 'Sửa bài viết' }).click();
  await expect(page).toHaveURL(/\/edit$/);
  await page.locator('textarea[name="content"]').fill(updated);
  await page.getByRole('button', { name: 'Lưu thay đổi' }).click();

  await expect(page).toHaveURL(/\/post\/[^/]+$/);
  await expect(page.getByRole('heading', { name: updated })).toBeVisible();
});
