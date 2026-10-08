export const MAX_POST_IMAGES = 6;
export const MAX_POST_IMAGE_BYTES = 5 * 1024 * 1024;

const acceptedTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);

export function appendPostImages(
  current: File[],
  incoming: File[],
  existingCount: number,
): { files: File[]; error: string | null } {
  if (incoming.length === 0) return { files: current, error: null };
  if (incoming.some((file) => !acceptedTypes.has(file.type) || file.size === 0 || file.size > MAX_POST_IMAGE_BYTES)) {
    return { files: current, error: 'Chọn ảnh JPEG, PNG hoặc WebP; mỗi ảnh tối đa 5 MB.' };
  }
  if (existingCount + current.length + incoming.length > MAX_POST_IMAGES) {
    return { files: current, error: 'Mỗi bài viết có tối đa 6 ảnh.' };
  }
  return { files: [...current, ...incoming], error: null };
}
