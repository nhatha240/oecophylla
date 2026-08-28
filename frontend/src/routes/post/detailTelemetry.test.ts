import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('post detail telemetry migration', () => {
  it('does not increment the legacy view counter from the server load', () => {
    const source = readFileSync(new URL('./[id]/+page.server.ts', import.meta.url), 'utf8');
    expect(source).not.toContain(`/posts/\${params.id}/view`);
  });
});
