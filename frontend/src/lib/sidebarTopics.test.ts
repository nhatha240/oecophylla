import { describe, expect, it } from 'vitest';
import { buildSidebarTopics } from './sidebarTopics';

describe('sidebar topics', () => {
  it('shows saved topics first and adds distinct positive topics learned from actions', () => {
    const topics = buildSidebarTopics(
      ['tech', 'science', 'tech'],
      { sports: 3, tech: 2, culture: 1, general: 10, environment: 0, health: -2 }
    );

    expect(topics.map(({ key, source }) => [key, source])).toEqual([
      ['tech', 'selected'], ['science', 'selected'], ['sports', 'activity'], ['culture', 'activity']
    ]);
    expect(topics[0]).toMatchObject({ label: 'Công nghệ', href: '/topic/tech' });
  });

  it('does not display the same fixed topics for a new user with no preferences or activity', () => {
    expect(buildSidebarTopics([], null)).toEqual([]);
  });

  it('uses exact topic keys in links and safely encodes unfamiliar topics', () => {
    expect(buildSidebarTopics(['AI & ML'], {})[0]).toMatchObject({
      label: 'AI & ML', href: '/topic/AI%20%26%20ML'
    });
  });
});
