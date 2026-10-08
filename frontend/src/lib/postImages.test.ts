import { describe, expect, it } from 'vitest';
import { appendPostImages } from './postImages';

const photo = (name = 'photo.png', type = 'image/png', bytes = 10) =>
  new File([new Uint8Array(bytes)], name, { type });

describe('appendPostImages', () => {
  it('adds dropped files without replacing previously selected images', () => {
    const first = photo('first.png');
    const second = photo('second.png');
    expect(appendPostImages([first], [second], 0)).toEqual({ files: [first, second], error: null });
  });

  it('counts existing image URLs toward the six image limit', () => {
    const current = [photo('first.png')];
    const result = appendPostImages(current, [photo('second.png')], 5);
    expect(result.files).toEqual(current);
    expect(result.error).toMatch(/6 ảnh/);
  });

  it('rejects unsupported, empty and oversized files without changing selection', () => {
    const current = [photo()];
    for (const invalid of [photo('bad.svg', 'image/svg+xml'), photo('empty.png', 'image/png', 0), photo('large.png', 'image/png', 5 * 1024 * 1024 + 1)]) {
      const result = appendPostImages(current, [invalid], 0);
      expect(result.files).toEqual(current);
      expect(result.error).toMatch(/JPEG, PNG hoặc WebP/);
    }
  });
});
