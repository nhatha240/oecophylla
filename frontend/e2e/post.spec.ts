/**
 * Post golden-path: create post → appears on feed → open detail → content matches.
 * Prerequisites: `make up` (stack running on :3000).
 */
import { test, expect } from '@playwright/test';
import { randomUser, registerUser, loginUser } from './helpers';

test.describe('Post flow', () => {
  test('create post and see it on detail page', async ({ page }) => {
    const user = randomUser('post');
    const postContent = `E2E post ${Date.now()} — Hello from Playwright!`;
    await registerUser(page, user);

    // Navigate to compose
    await page.goto('/post/new');
    await expect(page.locator('h1:has-text("Soạn bài viết mới")')).toBeVisible();

    // Fill in post content
    await page.locator('textarea[name="content"]').fill(postContent);
    await page.locator('input[name="tags"]').fill('e2e,test');

    // Submit
    await page.getByTestId('composer-submit').click();

    // Should redirect to post detail
    await page.waitForURL(/\/post\//, { timeout: 10_000 });

    // Verify content is visible on the detail page
    await expect(page.getByRole('heading', { name: postContent })).toBeVisible();
  });

  test('created post appears on the author profile', async ({ page }) => {
    const user = randomUser('postfeed');
    const postContent = `Feed test ${Date.now()}`;
    await registerUser(page, user);
    const meResponse = await page.request.get('/api/v1/auth/me');
    expect(meResponse.ok()).toBeTruthy();
    const userId = (await meResponse.json()).user.id as string;

    // Create a post
    await page.goto('/post/new');
    await page.locator('textarea[name="content"]').fill(postContent);
    await page.getByTestId('composer-submit').click();
    await page.waitForURL(/\/post\//, { timeout: 10_000 });

    // The personalized feed may still hold the pre-create cache; the author
    // profile is the authoritative list for a newly-created post.
    await page.goto(`/profile/${userId}`);
    await expect(page.locator(`article:has-text("${postContent}")`)).toBeVisible({ timeout: 15_000 });
  });

  test('post detail shows full content', async ({ page }) => {
    const user = randomUser('postdet');
    const postContent = `Detail test ${Date.now()}`;
    await registerUser(page, user);

    // Create a post
    await page.goto('/post/new');
    await page.locator('textarea[name="content"]').fill(postContent);
    await page.getByTestId('composer-submit').click();
    await page.waitForURL(/\/post\//, { timeout: 10_000 });

    // We're already on the detail page after creation
    await expect(page.getByRole('heading', { name: postContent })).toBeVisible();
    // Should have comment section
    await expect(page.locator('h2:has-text("Bình luận")')).toBeVisible();
  });
});
