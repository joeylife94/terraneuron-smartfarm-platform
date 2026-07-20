import { NextRequest, NextResponse } from 'next/server';
import {
  callOps,
  copyUpstreamResponse,
  forbiddenOrigin,
  OpsTokenEnvelope,
  setSessionCookies,
} from '@/lib/server/ops-session';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!request.headers.get('origin') ? false : !sameOrigin(request)) {
    return forbiddenOrigin();
  }

  const payload = await request.json().catch(() => null) as {
    username?: unknown;
    password?: unknown;
  } | null;

  if (!payload
      || typeof payload.username !== 'string'
      || typeof payload.password !== 'string'
      || payload.username.trim().length === 0
      || payload.username.length > 50
      || payload.password.length === 0
      || payload.password.length > 200) {
    return NextResponse.json({ status: 'error', message: 'Invalid login request' }, { status: 400 });
  }

  const upstream = await callOps('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: payload.username, password: payload.password }),
  });

  if (!upstream.ok) return copyUpstreamResponse(upstream);

  const tokens = await upstream.json() as OpsTokenEnvelope;
  if (!tokens.access_token || !tokens.refresh_token || !tokens.user) {
    return NextResponse.json({ status: 'error', message: 'Invalid authentication response' }, { status: 502 });
  }

  const response = NextResponse.json({
    status: 'success',
    authenticated: true,
    user: tokens.user,
  }, { headers: { 'Cache-Control': 'no-store' } });
  setSessionCookies(request, response, tokens);
  return response;
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get('origin');
  if (!origin) return true;
  const host = request.headers.get('x-forwarded-host')?.split(',')[0]?.trim()
    || request.headers.get('host');
  if (!host) return false;
  const proto = request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim()
    || (request.nextUrl.protocol === 'https:' ? 'https' : 'http');
  return origin === `${proto}://${host}`;
}
