import { describe, expect, it } from 'vitest';
import { insertMention, mentionAtCaret, splitMentions } from './mentions';

describe('mentions', () => {
  it('finds the active username after @ at the caret', () => {
    expect(mentionAtCaret('Chào @minh', 10)).toEqual({ start: 5, query: 'minh' });
    expect(mentionAtCaret('Chào @minh bạn', 14)).toBeNull();
    expect(mentionAtCaret('mail@example.com', 16)).toBeNull();
  });

  it('accepts Vietnamese display names while searching for a user', () => {
    expect(mentionAtCaret('Chào @Hà', 8)).toEqual({ start: 5, query: 'Hà' });
    expect(insertMention('Chào @Hà', 8, 'ha_nguyen')).toEqual({ value: 'Chào @ha_nguyen ', caret: 16 });
  });

  it('inserts a selected user without changing later text', () => {
    expect(insertMention('Chào @mi nhé', 8, 'minh')).toEqual({ value: 'Chào @minh nhé', caret: 11 });
  });

  it('splits mentions into safe text and username tokens', () => {
    expect(splitMentions('Chào @minh và @lan!')).toEqual([
      { text: 'Chào ' }, { username: 'minh' }, { text: ' và ' }, { username: 'lan' }, { text: '!' }
    ]);
    expect(splitMentions('mail@example.com')).toEqual([{ text: 'mail@example.com' }]);
  });
});
