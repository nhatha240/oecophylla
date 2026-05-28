/**
 * Auth golden-path: register → feed, logout → login page, login → feed.
 * Prerequisites: `make up` (stack running on :3000).
 */
import { test, expect } from '@playwright/test';
import { randomUser, registerUser, loginUser } from './helpers';

test.describe('Authentication flow', () => {
  const user = randomUser('auth');

  test('register lands on feed', async ({ page }) => {
    await registerUser(page, user);
    // Should see the feed breadcrumb
    await expect(page.getByTestId('feed-heading')).toBeVisible();
    // Should see sidebar user name
    await expect(page.locator(`text=${user.displayName}`)).toBeVisible();
  });

  test('logout redirects to login', async ({ page }) => {
    // Already logged in from previous test — but Playwright isolates contexts,
    // so we register fresh here.
    const u = randomUser('authout');
    await registerUser(page, u);

    // Find and click the logout button in the sidebar
    await page.locator('button:has-text("Đăng xuất")').click();
    await page.waitForURL('/login', { timeout: 10_000 });
    await expect(page.locator('h1:has-text("Chào mừng trở lại")')).toBeVisible();
  });

  test('login lands on feed', async ({ page }) => {
    // Register first so we have credentials
    const u = randomUser('authin');
    await registerUser(page, u);

    // Log out
    await page.locator('button:has-text("Đăng xuất")').click();
    await page.waitForURL('/login', { timeout: 10_000 });

    // Log back in
    await loginUser(page, u);
    await expect(page.locator(`text=${u.displayName}`)).toBeVisible();
  });
});
