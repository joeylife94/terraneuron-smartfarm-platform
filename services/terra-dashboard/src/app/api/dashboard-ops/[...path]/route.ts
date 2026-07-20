import { NextRequest, NextResponse } from 'next/server';
import {
  ACCESS_COOKIE,
  callOps,
  clearSessionCookies,
  copyUpstreamResponse,
  forbiddenOrigin,
  isAllowedOpsPath,
  isSameOrigin,
  REFRESH_COOKIE,
  rotateRefreshToken,
  setSessionCookies,
} from '@/lib/server/ops-session';

export const dynamic = 'force-dynamic';

type RouteContext = { params: { path: string[] } };

async function handle(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const segments = context.params.path;
  if (!isAllowedOpsPath(segments)) {
    return NextResponse.json({ status: 'error', message: 'Unsupported Terra-Ops route' }, { status: 404 });
  }

  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method) && !isSameOrigin(request)) {
    return forbiddenOrigin();
  }

  const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();
  const path = `/${segments.join('/')}${request.nextUrl.search}`;
  let accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  let rotated = null;

  if (!accessToken && refreshToken) {
    rotated = await rotateRefreshToken(refreshToken);
    accessToken = rotated?.access_token;
  }

  if (!accessToken) {
    const response = NextResponse.json({ status: 'error', message: 'Authentication required' }, { status: 401 });
    clearSessionCookies(response);
    return response;
  }

  let upstream = await forward(request, path, accessToken, body);
  if (upstream.status === 401 && refreshToken && !rotated) {
    rotated = await rotateRefreshToken(refreshToken);
    if (rotated) {
      upstream = await forward(request, path, rotated.access_token, body);
    }
  }

  const response = await copyUpstreamResponse(upstream);
  if (rotated) {
    setSessionCookies(request, response, rotated);
  } else if (upstream.status === 401) {
    clearSessionCookies(response);
  }
  return response;
}

async function forward(
  request: NextRequest,
  path: string,
  accessToken: string,
  body?: ArrayBuffer,
): Promise<Response> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };
  const contentType = request.headers.get('content-type');
  if (contentType) headers['Content-Type'] = contentType;

  return callOps(path, {
    method: request.method,
    headers,
    body,
  });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
