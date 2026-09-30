import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: {} }));

import { env } from '$env/dynamic/public';
import {
  isRecommendationTelemetryEnabled,
  recommendationLabelVersion,
  recommendationQualifiedReadMs,
} from './config';

describe('recommendation telemetry configuration', () => {
  afterEach(() => {
    env.PUBLIC_RECOMMENDATION_TELEMETRY_ENABLED = '';
    env.PUBLIC_RECOMMENDATION_LABEL_VERSION = '';
    env.PUBLIC_QUALIFIED_READ_MS = '';
  });

  it('uses the server-matched public qualified-read threshold', () => {
    env.PUBLIC_RECOMMENDATION_TELEMETRY_ENABLED = 'true';
    env.PUBLIC_RECOMMENDATION_LABEL_VERSION = 'v2';
    env.PUBLIC_QUALIFIED_READ_MS = '12345';

    expect(isRecommendationTelemetryEnabled()).toBe(true);
    expect(recommendationLabelVersion()).toBe('v2');
    expect(recommendationQualifiedReadMs()).toBe(12_345);
  });

  it('falls back to v1 and the shared default for invalid values', () => {
    env.PUBLIC_RECOMMENDATION_TELEMETRY_ENABLED = 'false';
    env.PUBLIC_RECOMMENDATION_LABEL_VERSION = 'unknown';
    env.PUBLIC_QUALIFIED_READ_MS = '-1';

    expect(isRecommendationTelemetryEnabled()).toBe(false);
    expect(recommendationLabelVersion()).toBe('v1');
    expect(recommendationQualifiedReadMs()).toBe(10_000);
  });
});
