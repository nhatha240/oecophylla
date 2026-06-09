/**
 * Single source of truth for the topic vocabulary (frontend side).
 *
 * Keep the slug set in sync with workers/nlp_worker/app/topics.py. Canonical
 * slugs drive the picker and the localized labels here; classification is
 * dynamic, so `topicLabel()` gracefully humanizes any slug the NLP analyzer or
 * LLM emits that isn't in this list (e.g. a coined "space-travel").
 */
export interface TopicOption {
  key: string;
  /** Vietnamese display label. */
  label: string;
}

export const TOPICS: TopicOption[] = [
  { key: 'tech', label: 'Công nghệ' },
  { key: 'science', label: 'Khoa học' },
  { key: 'sports', label: 'Thể thao' },
  { key: 'politics', label: 'Chính trị' },
  { key: 'entertainment', label: 'Giải trí' },
  { key: 'health', label: 'Sức khoẻ' },
  { key: 'business', label: 'Kinh doanh' },
  { key: 'culture', label: 'Văn hoá' },
  { key: 'education', label: 'Giáo dục' },
  { key: 'environment', label: 'Môi trường' },
  { key: 'ai', label: 'AI & Học máy' },
  { key: 'music', label: 'Âm nhạc' },
  { key: 'news', label: 'Tin tức' },
  { key: 'general', label: 'Tổng hợp' }
];

/** slug → Vietnamese label, for O(1) lookup. */
export const TOPIC_LABELS: Record<string, string> = Object.fromEntries(
  TOPICS.map((t) => [t.key, t.label])
);

/**
 * Humanize an unknown/dynamic slug: "space-travel" → "Space Travel".
 * Used as the fallback so AI-coined topics still render readably.
 */
function humanize(slug: string): string {
  return slug
    .split(/[-_]/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/** Display label for any topic slug — localized when known, humanized otherwise. */
export function topicLabel(slug: string): string {
  return TOPIC_LABELS[slug] ?? humanize(slug);
}
