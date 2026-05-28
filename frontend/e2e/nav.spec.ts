/**
 * Navigation smoke test: all main routes return 200 (or redirect for auth-gated pages).
 * Prerequisites: `make up` (stack running on :3000).
 */
import { test, expect } from '@playwright/test';

test.describe('Route smoke tests', () => {
  test('home page loads', async ({ page }) => {
    const res = await page.goto('/');
    expect(res?.status()).toBe(200);
    await expect(page.getByTestId('feed-heading')).toBeVisible();
  });

  test('login page loads', async ({ page }) => {
    const res = await page.goto('/login');
    expect(res?.status()).toBe(200);
    await expect(page.locator('h1:has-text("Chào mừng trở lại")')).toBeVisible();
  });

  test('register page loads', async ({ page }) => {
    const res = await page.goto('/register');
    expect(res?.status()).toBe(200);
    await expect(page.locator('h1:has-text("Tạo tài khoản Oecophylla")')).toBeVisible();
  });

  test('search page loads', async ({ page }) => {
    const res = await page.goto('/search');
    expect(res?.status()).toBe(200);
    await expect(page.locator('text=Nhập từ khoá để tìm kiếm')).toBeVisible();
  });

  test('settings redirects to login when unauthenticated', async ({ page }) => {
    await page.goto('/settings');
    // Auth-gated: should redirect to /login
    await expect(page).toHaveURL(/\/login/);
  });

  test('notifications redirects to login when unauthenticated', async ({ page }) => {
    await page.goto('/notifications');
    await expect(page).toHaveURL(/\/login/);
  });
});
