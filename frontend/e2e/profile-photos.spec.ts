import { readFileSync } from 'node:fs';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { randomUser } from './helpers';

const avatar = { name: 'avatar.jpg', mimeType: 'image/jpeg', buffer: readFileSync(new URL('../static/brand/street.jpg', import.meta.url)) };
const cover = { name: 'cover.jpg', mimeType: 'image/jpeg', buffer: readFileSync(new URL('../static/brand/city.jpg', import.meta.url)) };

async function openEditor(page: Page) {
  const registered = await page.request.post('/api/v1/auth/register', { data: randomUser('profilephotos') });
  expect(registered.status()).toBe(200);
  const id = (await registered.json()).user.id as string;
  await page.goto(`/profile/${id}`);
  await page.getByRole('button', { name: 'Chỉnh sửa hồ sơ', exact: true }).click();
  return id;
}

async function dropPhotos(target: Locator, photos: (typeof avatar)[]) {
  await target.evaluate((element, items) => {
    const transfer = new DataTransfer();
    for (const photo of items) {
      transfer.items.add(new File([Uint8Array.from(atob(photo.bytes), (character) => character.charCodeAt(0))], photo.name, { type: photo.mimeType }));
    }
    element.dispatchEvent(new DragEvent('dragenter', { bubbles: true, dataTransfer: transfer }));
    element.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
  }, photos.map((photo) => ({ name: photo.name, mimeType: photo.mimeType, bytes: photo.buffer.toString('base64') })));
}

async function expectDecoded(photo: Locator) {
  await expect(photo).toBeVisible();
  await expect.poll(() => photo.evaluate((element) => {
    const image = element as HTMLImageElement;
    return image.complete && image.naturalWidth > 0;
  })).toBe(true);
}

test('profile photo buttons, live preview and dropped avatar persist after saving', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1080 });
  const id = await openEditor(page);
  let releaseUpload = () => {};
  const uploadGate = new Promise<void>((resolve) => { releaseUpload = resolve; });
  await page.route(`**/api/v1/users/${id}/cover`, async (route) => { await uploadGate; await route.continue(); });
  try {
    const chooserEvent = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Thêm ảnh bìa', exact: true }).click();
    const chooser = await chooserEvent;
    expect(chooser.isMultiple()).toBe(false);
    await chooser.setFiles(cover);
    await expect(page.getByRole('status')).toContainText('Đang tải ảnh bìa');
    await expect(page.getByAltText('Ảnh bìa xem trước')).toHaveAttribute('src', /^blob:/);
    await expectDecoded(page.getByAltText('Ảnh bìa xem trước'));
    await expect(page.getByRole('button', { name: 'Lưu thay đổi', exact: true })).toBeDisabled();
  } finally { releaseUpload(); }
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  await page.unroute(`**/api/v1/users/${id}/cover`);
  await dropPhotos(page.getByTestId('profile-avatar-dropzone'), [avatar]);
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  await expectDecoded(page.getByAltText('Ảnh đại diện xem trước'));
  await page.locator('#name').fill('Minh An');
  const biography = 'Yêu những câu chuyện nhỏ, những góc phố quen và các cuộc trò chuyện tử tế.';
  await page.locator('#bio').fill(biography);
  await expect(page.locator('.label-row > span')).toHaveText(`${biography.length}/280`);
  await page.locator('.editing-panel').screenshot({ path: '/tmp/oecophylla-profile-editor-desktop.png' });
  await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Minh An', exact: true })).toBeVisible();
  await page.reload();
  await expectDecoded(page.getByAltText('Ảnh bìa hồ sơ'));
  await expectDecoded(page.locator('.profile-head .avatar img'));
  const profile = await page.request.get(`/api/v1/users/${id}`);
  const saved = await profile.json();
  expect(saved.display_name).toBe('Minh An');
  expect(saved.bio).toContain('những câu chuyện nhỏ');
  for (const [url, source] of [[saved.avatar_url, avatar], [saved.cover_url, cover]] as const) {
    const stored = await page.request.get(url);
    expect(stored.status()).toBe(200);
    expect((await stored.body()).equals(source.buffer)).toBe(true);
  }
});

test('profile photo editor fits mobile and uploads both images', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openEditor(page);
  const chooserEvent = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Thêm ảnh đại diện', exact: true }).click();
  await (await chooserEvent).setFiles(avatar);
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  await dropPhotos(page.getByTestId('profile-cover-dropzone'), [cover]);
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  await expectDecoded(page.getByAltText('Ảnh bìa xem trước'));
  await expectDecoded(page.getByAltText('Ảnh đại diện xem trước'));
  await page.locator('#name').fill('Minh An');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator('.editing-panel').screenshot({ path: '/tmp/oecophylla-profile-editor-mobile.png' });
  await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click();
  await page.reload();
  await expectDecoded(page.getByAltText('Ảnh bìa hồ sơ'));
  await expectDecoded(page.locator('.profile-head .avatar img'));
});

test('invalid drops and failed uploads keep the previous photo and permit retry', async ({ page }) => {
  const id = await openEditor(page);
  await dropPhotos(page.getByTestId('profile-avatar-dropzone'), [avatar, cover]);
  await expect(page.getByRole('alert')).toContainText('Mỗi lần chỉ chọn một ảnh');
  await expect(page.getByAltText('Ảnh đại diện xem trước')).toHaveCount(0);
  await page.locator('#profile-avatar-file').setInputFiles({ name: 'bad.svg', mimeType: 'image/svg+xml', buffer: Buffer.from('<svg/>') });
  await expect(page.getByRole('alert')).toContainText('JPEG, PNG hoặc WebP');
  await page.locator('#profile-avatar-file').setInputFiles(avatar);
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  const previousUrl = await page.getByAltText('Ảnh đại diện xem trước').getAttribute('src');
  await page.route(`**/api/v1/users/${id}/avatar`, (route) => route.abort('failed'), { times: 1 });
  await page.locator('#profile-avatar-file').setInputFiles(cover);
  await expect(page.getByRole('alert')).toContainText('Không tải được ảnh');
  await expect(page.getByAltText('Ảnh đại diện xem trước')).toHaveAttribute('src', previousUrl!);
  await expect(page.getByRole('button', { name: 'Đổi ảnh đại diện', exact: true })).toBeEnabled();
  await page.locator('#profile-avatar-file').setInputFiles(cover);
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  await expect(page.getByAltText('Ảnh đại diện xem trước')).not.toHaveAttribute('src', previousUrl!);
  await expectDecoded(page.getByAltText('Ảnh đại diện xem trước'));
});
