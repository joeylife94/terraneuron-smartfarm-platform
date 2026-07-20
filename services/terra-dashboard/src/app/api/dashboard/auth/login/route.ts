import { NextRequest, NextResponse } from 'next/server';
import {
  callOps,
  copyUpstreamResponse,
  forbiddenOrigin,
  isSameOrigin,
  OpsTokenEnvelope,
  setSessionCookies,
} from '@/lib/server/ops-session';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOrigin(request)) return forbiddenOrigin();

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
