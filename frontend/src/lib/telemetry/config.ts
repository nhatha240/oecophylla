import { env } from '$env/dynamic/public';
import { QUALIFIED_READ_MS } from './recommendationLabel';

export function isRecommendationTelemetryEnabled(): boolean {
  return env.PUBLIC_RECOMMENDATION_TELEMETRY_ENABLED === 'true';
}

export function recommendationLabelVersion(): 'v1' | 'v2' {
  return env.PUBLIC_RECOMMENDATION_LABEL_VERSION === 'v2' ? 'v2' : 'v1';
}

export function recommendationQualifiedReadMs(): number {
  const configured = Number(env.PUBLIC_QUALIFIED_READ_MS);
  return Number.isInteger(configured) && configured > 0 && configured <= 1_800_000
    ? configured
    : QUALIFIED_READ_MS;
}
