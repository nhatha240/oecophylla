import { readFileSync } from 'node:fs';
import { expect, request, test, type Locator, type Page } from '@playwright/test';
import { randomUser } from './helpers';

const image = {
  name: 'photo.png',
  mimeType: 'image/png',
  buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64')
};

const samplePhotos = ['street', 'city'].map((name) => ({
  name: `${name}.jpg`, mimeType: 'image/jpeg',
  buffer: readFileSync(new URL(`../static/brand/${name}.jpg`, import.meta.url))
}));

function photos(count: number, offset = 0) {
  return Array.from({ length: count }, (_, index) => ({
    ...samplePhotos[(index + offset) % samplePhotos.length], name: `photo-${index + offset + 1}.jpg`
  }));
}

async function expectDecodedImages(images: Locator, count: number) {
  await expect(images).toHaveCount(count);
  await expect.poll(() => images.evaluateAll((elements) => elements.every((element) => {
    const photo = element as HTMLImageElement;
    return photo.complete && photo.naturalWidth > 0;
  }))).toBe(true);
}

async function startPost(page: Page, prefix: string) {
  const registered = await page.request.post('/api/v1/auth/register', { data: randomUser(prefix) });
  expect(registered.status()).toBe(200);
  await page.goto('/post/new');
  await page.locator('#content').fill('Kiểm tra tải nhiều ảnh và giữ nguyên ảnh sau khi tải lại trang.');
}

async function expectStoredPhotos(page: Page, expected: ReturnType<typeof photos>) {
  await expect(page).toHaveURL(/\/post\/[0-9a-f-]+$/);
  const postId = page.url().split('/').at(-1);
  const response = await page.request.get(`/api/v1/posts/${postId}`);
  expect(response.status()).toBe(200);
  const post = await response.json();
  expect(post.media_urls).toHaveLength(expected.length);
  expect(new Set(post.media_urls).size).toBe(expected.length);
  for (let index = 0; index < expected.length; index++) {
    const stored = await page.request.get(post.media_urls[index]);
    expect(stored.status()).toBe(200);
    expect(stored.headers()['content-type']).toContain(expected[index].mimeType);
    expect((await stored.body()).equals(expected[index].buffer)).toBe(true);
  }
  await expectDecodedImages(page.locator('.article-images img'), expected.length);
  await page.reload();
  await expectDecodedImages(page.locator('.article-images img'), expected.length);
  return postId;
}

test('publishes six photos chosen together and preserves every image after reload', async ({ page }) => {
  await startPost(page, 'sixphotos');
  const selected = photos(6);
  const chooserEvent = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Chọn ảnh' }).click();
  const chooser = await chooserEvent;
  expect(chooser.isMultiple()).toBe(true);
  await chooser.setFiles(selected);
  await expectDecodedImages(page.getByTestId('post-image-gallery').locator('img'), 6);
  await expect(page.getByRole('button', { name: 'Chọn ảnh' })).toBeDisabled();
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  await expectStoredPhotos(page, selected);
});

test('combines multiple selections and dropped photos, then removes only the chosen photo', async ({ page }) => {
  await startPost(page, 'addphotos');
  await page.locator('#post-images').setInputFiles(photos(2));
  await page.locator('#post-images').setInputFiles(photos(2, 2));
  await expectDecodedImages(page.getByTestId('post-image-gallery').locator('img'), 4);
  const dropped = photos(2, 4);
  await page.getByTestId('post-image-picker').evaluate((element, images) => {
    const transfer = new DataTransfer();
    for (const photo of images) {
      transfer.items.add(new File([Uint8Array.from(atob(photo.bytes), (character) => character.charCodeAt(0))], photo.name, { type: photo.mimeType }));
    }
    element.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
  }, dropped.map((photo) => ({ name: photo.name, mimeType: photo.mimeType, bytes: photo.buffer.toString('base64') })));
  await expectDecodedImages(page.getByTestId('post-image-gallery').locator('img'), 6);
  await page.getByRole('button', { name: 'Xóa ảnh 3', exact: true }).click();
  await expectDecodedImages(page.getByTestId('post-image-gallery').locator('img'), 5);
  await expect(page.getByRole('button', { name: 'Chọn ảnh' })).toBeEnabled();
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  const selected = photos(6).filter((_, index) => index !== 2);
  const postId = await expectStoredPhotos(page, selected);
  await page.goto(`/post/${postId}/edit`);
  await page.locator('#composer-image-files').setInputFiles(photos(1, 6));
  await expectDecodedImages(page.getByTestId('post-image-gallery').locator('img'), 6);
  await page.getByTestId('composer-submit').click();
  await expectStoredPhotos(page, [...selected, ...photos(1, 6)]);
});

test('rejects seven photos and permits a corrected selection', async ({ page }) => {
  await startPost(page, 'photolimit');
  await page.locator('#post-images').setInputFiles(photos(7));
  await expect(page.getByRole('alert')).toContainText('tối đa 6 ảnh');
  await expect(page.getByTestId('post-image-gallery')).toHaveCount(0);
  await page.locator('#post-images').setInputFiles(photos(2));
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  await expectStoredPhotos(page, photos(2));
});

test('replaces photos when editing a post already holding six images', async ({ page }) => {
  await startPost(page, 'replacephotos');
  await page.locator('#post-images').setInputFiles(photos(6));
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  const postId = await expectStoredPhotos(page, photos(6));
  await page.goto(`/post/${postId}/edit`);
  await page.getByRole('button', { name: 'Xóa ảnh 3', exact: true }).click();
  await page.getByRole('button', { name: 'Xóa ảnh 3', exact: true }).click();
  await page.locator('#composer-image-files').setInputFiles(photos(2, 6));
  await expectDecodedImages(page.getByTestId('post-image-gallery').locator('img'), 6);
  await page.getByTestId('composer-submit').click();
  await expectStoredPhotos(page, [...photos(6).filter((_, index) => index !== 2 && index !== 3), ...photos(2, 6)]);
});

test('retries an interrupted multiple image upload without duplicating stored photos', async ({ page }) => {
  await startPost(page, 'retryphotos');
  await page.locator('#post-images').setInputFiles(photos(3));
  let attempt = 0;
  await page.route('**/api/v1/posts/*/images', (route) => {
    if (route.request().method() === 'POST' && ++attempt === 2) return route.abort('failed');
    return route.continue();
  });
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  await expect(page.getByRole('alert')).toContainText('chưa tải hết ảnh');
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  await expectStoredPhotos(page, photos(3));
  expect(attempt).toBe(4);
});

test('can remove a pending photo and retry an interrupted edit upload', async ({ page }) => {
  await startPost(page, 'retryedit');
  await page.locator('#post-images').setInputFiles(photos(2));
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  const postId = await expectStoredPhotos(page, photos(2));
  await page.goto(`/post/${postId}/edit`);
  await page.locator('#composer-image-files').setInputFiles(photos(3, 2));
  let attempt = 0;
  await page.route('**/api/v1/posts/*/images', (route) => {
    if (route.request().method() === 'POST' && ++attempt === 2) return route.abort('failed');
    return route.continue();
  });
  await page.getByTestId('composer-submit').click();
  await expect(page.getByRole('alert')).toContainText('Vui lòng thử lưu lại');
  await expectDecodedImages(page.getByTestId('post-image-gallery').locator('img'), 5);
  await page.getByRole('button', { name: 'Xóa ảnh 4', exact: true }).click();
  await page.getByTestId('composer-submit').click();
  await expectStoredPhotos(page, photos(5).filter((_, index) => index !== 3));
});

test('member uploads post images, avatar, and profile cover', async ({ page }) => {
  const user = randomUser('images');
  const registered = await page.request.post('/api/v1/auth/register', { data: user });
  expect(registered.status()).toBe(200);
  const id = (await registered.json()).user.id as string;

  await page.goto('/post/new');
  await page.locator('#content').fill('Bài viết có ảnh từ thiết bị');
  await expect(page.getByRole('button', { name: 'Chọn ảnh' })).toBeVisible();
  await page.locator('#post-images').setInputFiles(image);
  await expect(page.getByTestId('post-image-gallery').locator('img')).toHaveCount(1);
  await page.getByTestId('post-image-picker').evaluate((element, bytes) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([Uint8Array.from(atob(bytes), (character) => character.charCodeAt(0))], 'dropped.png', { type: 'image/png' }));
    element.dispatchEvent(new DragEvent('dragenter', { bubbles: true, dataTransfer: transfer }));
    element.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
  }, image.buffer.toString('base64'));
  await expect(page.getByTestId('post-image-gallery').locator('img')).toHaveCount(2);
  await page.getByRole('button', { name: 'Xóa ảnh 1' }).click();
  await expect(page.getByTestId('post-image-gallery').locator('img')).toHaveCount(1);
  await page.getByRole('button', { name: 'Đăng bài viết' }).click();
  await expect(page).toHaveURL(/\/post\/[0-9a-f-]+$/);
  await expect(page.getByAltText('Ảnh bài viết 1')).toBeVisible();
  const postId = page.url().split('/').at(-1);
  await page.goto(`/post/${postId}/edit`);
  await page.locator('#composer-image-files').setInputFiles(image);
  await expect(page.getByTestId('post-image-gallery').locator('img')).toHaveCount(2);
  await page.getByTestId('composer-submit').click();
  await expect(page).toHaveURL(`/post/${postId}`);
  await expect(page.getByAltText('Ảnh bài viết 2')).toBeVisible();

  await page.goto(`/profile/${id}`);
  await page.getByRole('button', { name: 'Chỉnh sửa hồ sơ' }).click();
  await page.locator('#profile-avatar-file').setInputFiles(image);
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  await page.locator('#profile-cover-file').setInputFiles(image);
  await expect(page.getByRole('status')).toContainText('Đã tải ảnh lên.');
  await page.getByRole('button', { name: 'Lưu thay đổi' }).click();
  await page.reload();
  await expect(page.getByAltText('Ảnh bìa hồ sơ')).toBeVisible();
  await expect(page.locator('.profile-head .avatar img')).toBeVisible();
});

test('rejects another member uploads and spoofed image bytes', async ({ page, baseURL }) => {
  const owner = await page.request.post('/api/v1/auth/register', { data: randomUser('imageowner') });
  expect(owner.status()).toBe(200);
  const ownerId = (await owner.json()).user.id as string;
  const created = await page.request.post('/api/v1/posts', { data: { content: 'Owner post', tags: [], media_urls: [] } });
  expect(created.status()).toBe(200);
  const postId = (await created.json()).id as string;

  const originUrl = new URL(baseURL ?? 'http://localhost:4173').origin;
  const otherContext = await request.newContext({ baseURL: originUrl });
  const other = await otherContext.post('/api/v1/auth/register', { data: randomUser('imageother') });
  expect(other.status()).toBe(200);
  const otherId = (await other.json()).user.id as string;
  const current = await otherContext.get('/api/v1/auth/me');
  expect(current.status()).toBe(200);
  expect((await current.json()).user.id).toBe(otherId);

  const origin = { origin: originUrl };
  const blockedCover = await otherContext.put(`/api/v1/users/${ownerId}/cover`, { headers: origin, multipart: { cover: image } });
  expect(blockedCover.status()).toBe(403);
  const blockedPost = await otherContext.post(`/api/v1/posts/${postId}/images`, { headers: origin, multipart: { image } });
  expect(blockedPost.status()).toBe(403);
  const spoofed = await otherContext.put(`/api/v1/users/${otherId}/cover`, {
    headers: origin,
    multipart: { cover: { name: 'fake.png', mimeType: 'image/png', buffer: Buffer.from('<svg/>') } }
  });
  expect(spoofed.status(), await spoofed.text()).toBe(400);
  await otherContext.dispose();
});

test('accepts an image larger than the former proxy limit', async ({ page, baseURL }) => {
  const registered = await page.request.post('/api/v1/auth/register', { data: randomUser('largeimage') });
  expect(registered.status()).toBe(200);
  const created = await page.request.post('/api/v1/posts', { data: { content: 'Large image', tags: [], media_urls: [] } });
  expect(created.status()).toBe(200);
  const postId = (await created.json()).id as string;
  const upload = await page.request.post(`/api/v1/posts/${postId}/images`, {
    headers: { origin: new URL(baseURL ?? 'http://localhost:4173').origin },
    multipart: {
      image: { ...image, buffer: Buffer.concat([image.buffer, Buffer.alloc(1024 * 1024)]) }
    }
  });
  expect(upload.status(), await upload.text()).toBe(200);
});
