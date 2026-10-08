export const TOPIC_OPTIONS = [
  { key: 'tech', label: 'Công nghệ', icon: 'Cpu' },
  { key: 'science', label: 'Khoa học', icon: 'Atom' },
  { key: 'sports', label: 'Thể thao', icon: 'Trophy' },
  { key: 'politics', label: 'Chính trị', icon: 'Globe' },
  { key: 'entertainment', label: 'Giải trí', icon: 'Music' },
  { key: 'health', label: 'Sức khỏe', icon: 'Heart' },
  { key: 'business', label: 'Kinh doanh', icon: 'ChartBar' },
  { key: 'culture', label: 'Văn hóa', icon: 'Book' },
  { key: 'education', label: 'Giáo dục', icon: 'Book' },
  { key: 'environment', label: 'Môi trường', icon: 'Heart' }
] as const;

const topicMetadata = new Map<string, { label: string; icon: string }>([
  ...TOPIC_OPTIONS.map(({ key, label, icon }) => [key, { label, icon }] as const),
  ['ai', { label: 'AI', icon: 'Cpu' }],
  ['news', { label: 'Tin tức', icon: 'Globe' }]
]);

export type SidebarTopic = {
  key: string;
  label: string;
  icon: string;
  href: string;
  source: 'selected' | 'activity';
};

function sidebarTopic(key: string, source: SidebarTopic['source']): SidebarTopic {
  const metadata = topicMetadata.get(key);
  return {
    key,
    label: metadata?.label ?? key,
    icon: metadata?.icon ?? 'Tag',
    href: `/topic/${encodeURIComponent(key)}`,
    source
  };
}

export function buildSidebarTopics(
  topicPrefs: string[] | undefined,
  topicWeights: Record<string, number> | null,
  activityLimit = 3
): SidebarTopic[] {
  const selectedKeys = [...new Set((topicPrefs ?? []).map((topic) => topic.trim()).filter((topic) => topic && topic !== 'general'))];
  const selected = selectedKeys.map((key) => sidebarTopic(key, 'selected'));
  const selectedSet = new Set(selectedKeys);
  const activity = Object.entries(topicWeights ?? {})
    .filter(([key, weight]) => key && key !== 'general' && !selectedSet.has(key) && Number.isFinite(weight) && weight > 0)
    .sort(([keyA, weightA], [keyB, weightB]) => weightB - weightA || keyA.localeCompare(keyB))
    .slice(0, activityLimit)
    .map(([key]) => sidebarTopic(key, 'activity'));
  return [...selected, ...activity];
}
