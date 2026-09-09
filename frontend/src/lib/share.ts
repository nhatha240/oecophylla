export interface SharePayload {
  title: string;
  text: string;
  url: string;
}

export interface ShareEnvironment {
  nativeShare?: (payload: SharePayload) => Promise<void>;
  writeText?: (text: string) => Promise<void>;
}

export type ExternalShareResult = 'shared' | 'copied' | 'cancelled';

export function canonicalPostUrl(origin: string, postId: string): string {
  return `${origin.replace(/\/$/, '')}/post/${encodeURIComponent(postId)}`;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === 'AbortError'
    : error instanceof Error && error.name === 'AbortError';
}

export async function shareExternally(
  environment: ShareEnvironment,
  payload: SharePayload
): Promise<ExternalShareResult> {
  if (environment.nativeShare) {
    try {
      await environment.nativeShare(payload);
      return 'shared';
    } catch (error) {
      if (isAbortError(error)) return 'cancelled';
    }
  }

  if (environment.writeText) {
    await environment.writeText(payload.url);
    return 'copied';
  }

  throw new Error('Không thể chia sẻ liên kết');
}

export function browserShareEnvironment(navigatorRef: Navigator): ShareEnvironment {
  return {
    nativeShare: navigatorRef.share
      ? (payload) => navigatorRef.share(payload)
      : undefined,
    writeText: navigatorRef.clipboard?.writeText
      ? (text) => navigatorRef.clipboard.writeText(text)
      : undefined
  };
}
