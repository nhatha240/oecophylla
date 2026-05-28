/**
 * Search golden-path: search for posts → results appear; switch to users tab.
 * Prerequisites: `make up` (stack running on :3000), seed data loaded.
 */
import { test, expect } from '@playwright/test';

test.describe('Search', () => {
  test('search page loads with query', async ({ page }) => {
    await page.goto('/search?q=tech');
    // Should show either results or "Không tìm thấy" — page itself must load
    await expect(page).toHaveURL(/\/search\?q=tech/);
    // Tabs should be visible
    await expect(page.locator('button:has-text("Bài viết")')).toBeVisible();
    await expect(page.locator('button:has-text("Người dùng")')).toBeVisible();
  });

  test('switch to users tab', async ({ page }) => {
    await page.goto('/search?q=a');
    await page.locator('button:has-text("Người dùng")').click();
    await expect(page).toHaveURL(/type=user/);
  });

  test('empty query shows placeholder', async ({ page }) => {
    await page.goto('/search');
    await expect(page.locator('text=Nhập từ khoá để tìm kiếm')).toBeVisible();
  });
});
