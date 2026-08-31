export const QUALIFIED_READ_MS = 10_000;
export const LABEL_CONTRACT_VERSION = 'engagement-label-v2';

type Semantic =
  | 'exposure'
  | 'click'
  | 'qualified_read'
  | 'positive'
  | 'strong_positive'
  | 'negative'
  | 'strong_negative';

type EventValue = Record<string, unknown>;

interface ResolveOptions {
  defaults?: EventValue;
  labelWindowClosed: boolean;
  qualifiedReadMs: number;
}

export interface LabelResultV2 {
  semantic: Semantic;
  training_target: number | null;
  accepted_events: number;
  deduplicated_events: number;
  reversed_event_types: string[];
  processing_order: string[];
}

const precedence: Semantic[] = [
  'strong_negative',
  'strong_positive',
  'positive',
  'qualified_read',
  'click',
  'negative',
  'exposure',
];
const reversals: Record<string, string> = {
  unlike: 'like',
  unsave: 'save',
  unshare: 'share',
  unhide: 'hide',
};

function canonicalJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (typeof value === 'object' && value !== null) {
    return Object.fromEntries(
      Object.entries(value as EventValue)
        .filter(([, item]) => item !== undefined)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalJson(item)]),
    );
  }
  return value;
}

function payload(event: EventValue): string {
  return JSON.stringify(canonicalJson(event));
}

function duration(event: EventValue): number | null {
  const metadata = typeof event.metadata === 'object' && event.metadata !== null
    ? event.metadata as EventValue
    : {};
  const value = event.continuous_visible_ms ?? metadata.continuous_visible_ms ?? event.dwell_ms;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function deriveLabelV2(events: EventValue[], options: ResolveOptions): LabelResultV2 {
  if (!Number.isInteger(options.qualifiedReadMs) || options.qualifiedReadMs <= 0) {
    throw new Error('qualifiedReadMs must be a positive integer');
  }
  const unique = new Map<string, EventValue>();
  const anonymous: EventValue[] = [];
  let deduplicated = 0;
  for (const rawEvent of events) {
    const event = { ...(options.defaults ?? {}), ...rawEvent };
    const eventId = event.event_id;
    if (typeof eventId !== 'string') {
      anonymous.push(event);
      continue;
    }
    const existing = unique.get(eventId);
    if (!existing) unique.set(eventId, event);
    else if (payload(existing) === payload(event)) deduplicated += 1;
    else throw new Error(`conflicting duplicate event: ${eventId}`);
  }
  const accepted = [...unique.values(), ...anonymous].sort((left, right) => {
    for (const key of ['occurred_at', 'ingested_at', 'event_id']) {
      const comparison = String(left[key] ?? '').localeCompare(String(right[key] ?? ''));
      if (comparison !== 0) return comparison;
    }
    return 0;
  });

  const active: Record<string, boolean> = { like: false, save: false, share: false, hide: false };
  const candidates = new Set<Semantic>();
  const reversed: string[] = [];
  let visible = false;
  for (const event of accepted) {
    const eventType = String(event.event_type ?? '');
    if (eventType in active) active[eventType] = true;
    else if (eventType in reversals) {
      const reversedType = reversals[eventType];
      active[reversedType] = false;
      if (!reversed.includes(reversedType)) reversed.push(reversedType);
    } else if (eventType === 'visible') visible = true;
    else if (eventType === 'click') candidates.add('click');
    else if (eventType === 'comment') candidates.add('positive');
    else if (eventType === 'report') candidates.add('strong_negative');

    const measured = duration(event);
    if ((eventType === 'view' || eventType === 'dwell') && measured !== null && measured >= options.qualifiedReadMs) {
      candidates.add('qualified_read');
    }
  }
  if (active.hide) candidates.add('strong_negative');
  if (active.save || active.share) candidates.add('strong_positive');
  if (active.like) candidates.add('positive');
  if (visible) candidates.add(options.labelWindowClosed ? 'negative' : 'exposure');
  if (candidates.size === 0) candidates.add(options.labelWindowClosed ? 'negative' : 'exposure');

  const semantic = precedence.find((item) => candidates.has(item))!;
  const trainingTarget = semantic === 'exposure'
    ? null
    : Number(['click', 'qualified_read', 'positive', 'strong_positive'].includes(semantic));
  return {
    semantic,
    training_target: trainingTarget,
    accepted_events: accepted.length,
    deduplicated_events: deduplicated,
    reversed_event_types: reversed,
    processing_order: accepted.map((event) => String(event.event_id ?? '')),
  };
}

export function parseQualifiedReadMs(value: string | undefined): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 && parsed <= 1_800_000
    ? parsed
    : QUALIFIED_READ_MS;
}
