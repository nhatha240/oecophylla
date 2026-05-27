import type { Cookies } from '@sveltejs/kit';

type CookieOptions = {
  path: string;
  httpOnly: boolean;
  sameSite: 'lax' | 'strict' | 'none';
  secure: boolean;
  maxAge?: number;
};

export function applyResponseCookies(cookies: Cookies, response: Response): void {
  for (const rawCookie of getSetCookieHeaders(response.headers)) {
    const parsed = parseSetCookie(rawCookie);
    if (!parsed) continue;

    const { name, value, options } = parsed;
    if (value === '' || options.maxAge === 0) {
      cookies.delete(name, {
        path: options.path,
        httpOnly: options.httpOnly,
        sameSite: options.sameSite,
        secure: options.secure,
      });
      continue;
    }

    cookies.set(name, value, options);
  }
}

function getSetCookieHeaders(headers: Headers): string[] {
  const headerBag = headers as Headers & {
    getSetCookie?: () => string[];
    raw?: () => Record<string, string[]>;
  };

  if (typeof headerBag.getSetCookie === 'function') {
    return headerBag.getSetCookie();
  }

  if (typeof headerBag.raw === 'function') {
    return headerBag.raw()['set-cookie'] ?? [];
  }

  const combined = headers.get('set-cookie');
  return combined ? splitSetCookieHeader(combined) : [];
}

function splitSetCookieHeader(header: string): string[] {
  const parts: string[] = [];
  let start = 0;
  let inExpires = false;

  for (let i = 0; i < header.length; i += 1) {
    const char = header[i];
    const rest = header.slice(i).toLowerCase();

    if (!inExpires && rest.startsWith('expires=')) {
      inExpires = true;
    }

    if (inExpires && char === ';') {
      inExpires = false;
    }

    if (!inExpires && char === ',') {
      parts.push(header.slice(start, i).trim());
      start = i + 1;
    }
  }

  parts.push(header.slice(start).trim());
  return parts.filter(Boolean);
}

function parseSetCookie(header: string): { name: string; value: string; options: CookieOptions } | null {
  const segments = header.split(';').map((segment) => segment.trim()).filter(Boolean);
  const [pair, ...attrs] = segments;
  if (!pair) return null;

  const eqIndex = pair.indexOf('=');
  if (eqIndex <= 0) return null;

  const name = pair.slice(0, eqIndex);
  const value = pair.slice(eqIndex + 1);
  const options: CookieOptions = {
    path: '/',
    httpOnly: false,
    sameSite: 'lax',
    secure: false,
  };

  for (const attr of attrs) {
    const [rawKey, ...rawValue] = attr.split('=');
    const key = rawKey.toLowerCase();
    const attrValue = rawValue.join('=');

    if (key === 'path' && attrValue) options.path = attrValue;
    if (key === 'max-age' && attrValue) options.maxAge = Number(attrValue);
    if (key === 'httponly') options.httpOnly = true;
    if (key === 'secure') options.secure = true;
    if (key === 'samesite' && attrValue) options.sameSite = normalizeSameSite(attrValue);
  }

  return { name, value, options };
}

function normalizeSameSite(value: string): 'lax' | 'strict' | 'none' {
  const lower = value.toLowerCase();
  if (lower === 'strict' || lower === 'none') return lower;
  return 'lax';
}
