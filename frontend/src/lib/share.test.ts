import { describe, expect, it, vi } from 'vitest';

import { canonicalPostUrl, shareExternally } from './share';

describe('shareExternally', () => {
  const payload = {
    title: 'Oecophylla',
    text: 'Một bài viết đáng đọc',
    url: 'https://example.test/post/post-1'
  };

  it('uses Web Share and reports success', async () => {
    const nativeShare = vi.fn().mockResolvedValue(undefined);
    const writeText = vi.fn();

    await expect(shareExternally({ nativeShare, writeText }, payload)).resolves.toBe('shared');
    expect(nativeShare).toHaveBeenCalledWith(payload);
    expect(writeText).not.toHaveBeenCalled();
  });

  it('does not copy or record a user-cancelled share', async () => {
    const nativeShare = vi.fn().mockRejectedValue(new DOMException('cancelled', 'AbortError'));
    const writeText = vi.fn();

    await expect(shareExternally({ nativeShare, writeText }, payload)).resolves.toBe('cancelled');
    expect(writeText).not.toHaveBeenCalled();
  });

  it('falls back to the clipboard when Web Share is unavailable', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);

    await expect(shareExternally({ writeText }, payload)).resolves.toBe('copied');
    expect(writeText).toHaveBeenCalledWith(payload.url);
  });

  it('falls back to the clipboard after a non-cancellation Web Share error', async () => {
    const nativeShare = vi.fn().mockRejectedValue(new Error('share unavailable'));
    const writeText = vi.fn().mockResolvedValue(undefined);

    await expect(shareExternally({ nativeShare, writeText }, payload)).resolves.toBe('copied');
    expect(writeText).toHaveBeenCalledWith(payload.url);
  });

  it('rejects when no external share mechanism succeeds', async () => {
    await expect(shareExternally({}, payload)).rejects.toThrow('Không thể chia sẻ liên kết');
  });
});

describe('canonicalPostUrl', () => {
  it('normalizes a trailing slash before building the post URL', () => {
    expect(canonicalPostUrl('https://example.test/', 'post-1')).toBe(
      'https://example.test/post/post-1'
    );
  });
});
