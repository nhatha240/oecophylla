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
});
