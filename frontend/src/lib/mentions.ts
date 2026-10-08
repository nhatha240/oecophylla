export type MentionPart = { text: string } | { username: string };

export function mentionAtCaret(value: string, caret: number): { start: number; query: string } | null {
  const before = value.slice(0, caret);
  const match = /(?:^|[\s(])@([\p{L}\p{M}\p{N}_]*)$/u.exec(before);
  if (!match) return null;
  return { start: caret - match[1].length - 1, query: match[1] };
}

export function insertMention(value: string, caret: number, username: string): { value: string; caret: number } {
  const active = mentionAtCaret(value, caret);
  if (!active) return { value, caret };
  const suffix = value.slice(caret);
  const separator = suffix.startsWith(' ') ? '' : ' ';
  const prefix = `${value.slice(0, active.start)}@${username}${separator}`;
  return { value: prefix + suffix, caret: prefix.length + (suffix.startsWith(' ') ? 1 : 0) };
}

export function splitMentions(value: string): MentionPart[] {
  const parts: MentionPart[] = [];
  const pattern = /(^|[^a-zA-Z0-9_@])@([a-zA-Z0-9_]{3,30})\b/g;
  let position = 0;
  for (const match of value.matchAll(pattern)) {
    const start = (match.index ?? 0) + match[1].length;
    if (start > position) parts.push({ text: value.slice(position, start) });
    parts.push({ username: match[2] });
    position = start + match[2].length + 1;
  }
  if (position < value.length) parts.push({ text: value.slice(position) });
  return parts.length ? parts : [{ text: value }];
}
