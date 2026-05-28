import { type Page, expect } from '@playwright/test';

/** Generate a unique username to avoid UNIQUE constraint collisions. */
export function randomUser(prefix = 'e2e') {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 6);
  const uname = `${prefix}_${ts}_${rand}`;
  return {
    username: uname,
    email: `${uname}@test.local`,
    password: 'Test!1234',
    displayName: `Test ${uname}`,
  };
}

/** Register a new user via the UI and land on the feed. */
export async function registerUser(page: Page, user: ReturnType<typeof randomUser>) {
  await page.goto('/register');
  await page.locator('#username').fill(user.username);
  await page.locator('#display_name').fill(user.displayName);
  await page.locator('#email_or_username').fill(user.email);
  await page.locator('#password').fill(user.password);
  await page.getByTestId('register-submit').click();
  // Registration redirects to / on success
  await page.waitForURL('/', { timeout: 10_000 });
  await expect(page.getByTestId('feed-heading')).toBeVisible();
}

/** Login via the UI and land on the feed. */
export async function loginUser(page: Page, user: ReturnType<typeof randomUser>) {
  await page.goto('/login');
  await page.locator('#email_or_username').fill(user.email ?? user.username);
  await page.locator('#password').fill(user.password);
  await page.getByTestId('login-submit').click();
  await page.waitForURL('/', { timeout: 10_000 });
  await expect(page.getByTestId('feed-heading')).toBeVisible();
}
