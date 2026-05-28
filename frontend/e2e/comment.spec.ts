/**
 * Comment golden-path: open a post → add comment → comment appears.
 * Prerequisites: `make up` (stack running on :3000).
 */
import { test, expect } from '@playwright/test';
import { randomUser, registerUser } from './helpers';

test.describe('Comment flow', () => {
  const user = randomUser('cmt');
  const postContent = `Comment-test post ${Date.now()}`;
  const commentText = `Nice article! ${Date.now()}`;

  test('create post, then add a comment', async ({ page }) => {
    // Register & login
    await registerUser(page, user);

    // Create a post first
    await page.goto('/post/new');
    await page.locator('textarea[name="content"]').fill(postContent);
    await page.locator('button[type="submit"]:has-text("Đăng")').click();
    await page.waitForURL(/\/post\//, { timeout: 10_000 });

    // We're now on the post detail page — fill in comment
    const commentArea = page.locator('textarea[placeholder="Viết bình luận của bạn…"]');
    await expect(commentArea).toBeVisible();
    await commentArea.fill(commentText);

    // Submit comment
    await page.locator('button:has-text("Gửi")').click();

    // Comment should appear in the list (SSE or DOM update)
    await expect(page.locator(`text=${commentText}`)).toBeVisible({ timeout: 10_000 });
  });
});
