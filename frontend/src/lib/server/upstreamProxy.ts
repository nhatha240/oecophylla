import { env } from '$env/dynamic/private';

const excludedHeaders = [
  'host', 'connection', 'keep-alive', 'transfer-encoding', 'upgrade',
  'proxy-authorization', 'proxy-authenticate', 'te', 'trailer', 'content-length',
  'forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-real-ip'
];

export async function proxyToEnvoy(request: Request, url: URL, path: string, requiredPrefix: string): Promise<Response> {
  const method = request.method;
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const requestOrigin = request.headers.get('origin');
    const fetchSite = request.headers.get('sec-fetch-site');
    if ((requestOrigin && requestOrigin !== url.origin) || fetchSite === 'cross-site') {
      return new Response('Forbidden', { status: 403 });
    }
  }

  const origin = env.ENVOY_URL ?? env.API_ENDPOINT ?? 'http://localhost:8080';
  const target = new URL(path + url.search, origin);
  if (!target.pathname.startsWith(requiredPrefix)) {
    return new Response('Bad request', { status: 400 });
  }

  const headers = new Headers(request.headers);
  for (const name of excludedHeaders) headers.delete(name);
  headers.set('x-requested-with', 'oec-web');
  const response = await fetch(target, {
    method,
    headers,
    body: method === 'GET' || method === 'HEAD' ? undefined : await request.arrayBuffer(),
    redirect: 'manual'
  });
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers });
}
