import { NextRequest, NextResponse } from 'next/server';
import {
  ACCESS_COOKIE,
  authError,
  callOps,
  clearAccessCookie,
  copyUpstreamResponse,
  forbiddenOrigin,
  isAllowedOpsPath,
  isSameOrigin,
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

  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!accessToken) return authError();

  const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();
  const path = `/${segments.join('/')}${request.nextUrl.search}`;
  const upstream = await forward(request, path, accessToken, body);
  const response = await copyUpstreamResponse(upstream);

  // Keep the refresh cookie so the browser's serialized session route can
  // rotate once and retry the original request. The proxy never rotates.
  if (upstream.status === 401) clearAccessCookie(response);
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
