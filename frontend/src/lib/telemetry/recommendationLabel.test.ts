import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { deriveLabelV2, QUALIFIED_READ_MS } from './recommendationLabel';

const fixture = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL('../../../../tests/fixtures/recommendation_telemetry/label-v2-cases.json', import.meta.url),
    ),
    'utf8',
  ),
);

describe('engagement-label-v2 shared fixture', () => {
  it('uses the generated QUALIFIED_READ_MS default from the contract fixture', () => {
    expect(QUALIFIED_READ_MS).toBe(fixture.qualified_read_ms);
  });

  for (const labelCase of fixture.label_cases) {
    it(`resolves ${labelCase.id}`, () => {
      expect(
        deriveLabelV2(labelCase.events, {
          defaults: fixture.event_defaults,
          labelWindowClosed: labelCase.label_window_closed,
          qualifiedReadMs: fixture.qualified_read_ms,
        }),
      ).toMatchObject(labelCase.expected);
    });
  }

  for (const orderingCase of fixture.ordering_cases) {
    it(`orders and resolves ${orderingCase.id}`, () => {
      const result = deriveLabelV2(orderingCase.input_events, {
        defaults: fixture.event_defaults,
        labelWindowClosed: orderingCase.label_window_closed,
        qualifiedReadMs: fixture.qualified_read_ms,
      });
      expect(result.processing_order).toEqual(orderingCase.expected.processing_order);
      expect(result.semantic).toBe(orderingCase.expected.semantic);
    });
  }

  for (const retryCase of fixture.event_retry_cases) {
    it(`rejects ${retryCase.id}`, () => {
      expect(() => deriveLabelV2([retryCase.first, retryCase.retry], {
        defaults: fixture.event_defaults,
        labelWindowClosed: true,
        qualifiedReadMs: fixture.qualified_read_ms,
      })).toThrow('conflicting duplicate event');
    });
  }

  it('deduplicates recursively equal JSON payloads regardless of object key order', () => {
    const first = {
      event_id: '30000000-0000-4000-8000-000000000090',
      event_type: 'click',
      occurred_at: '2026-08-30T03:00:00Z',
      metadata: { target: 'post_detail', context: { source: 'feed', position: 1 } },
    };
    const retry = {
      metadata: { context: { position: 1, source: 'feed' }, target: 'post_detail' },
      occurred_at: '2026-08-30T03:00:00Z',
      event_type: 'click',
      event_id: '30000000-0000-4000-8000-000000000090',
    };

    const result = deriveLabelV2([first, retry], {
      defaults: fixture.event_defaults,
      labelWindowClosed: true,
      qualifiedReadMs: fixture.qualified_read_ms,
    });

    expect(result.semantic).toBe('click');
    expect(result.accepted_events).toBe(1);
    expect(result.deduplicated_events).toBe(1);
  });
});
