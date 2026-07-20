import 'server-only';

import { NextRequest, NextResponse } from 'next/server';

export const ACCESS_COOKIE = 'terraneuron_access_token';
export const REFRESH_COOKIE = 'terraneuron_refresh_token';

const OPS_BASE = (process.env.TERRA_OPS_INTERNAL_URL ?? 'http://terra-ops:8080/api').replace(/\/+$/, '');

export interface SessionUser {
  username: string;
  roles: string[];
}

export interface OpsTokenEnvelope {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  refresh_expires_in: number;
  user?: SessionUser;
}

export interface ValidatedSession {
  status: string;
  valid: boolean;
  user: SessionUser;
}

export async function callOps(path: string, init?: RequestInit): Promise<Response> {
  if (!path.startsWith('/')) {
    throw new Error('Terra-Ops path must be absolute');
  }

  return fetch(`${OPS_BASE}${path}`, {
    ...init,
    cache: 'no-store',
    redirect: 'manual',
    headers: {
      Accept: 'application/json',
      ...init?.headers,
    },
  });
}

export async function rotateRefreshToken(refreshToken: string): Promise<OpsTokenEnvelope | null> {
  const response = await callOps('/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refreshToken }),
  });

  if (!response.ok) return null;
  const payload = await response.json() as Partial<OpsTokenEnvelope>;
  return isTokenEnvelope(payload) ? payload : null;
}

export async function validateAccessToken(accessToken: string): Promise<SessionUser | null> {
  const response = await callOps('/auth/validate', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) return null;
  const payload = await response.json() as Partial<ValidatedSession>;
  if (!payload.valid || !payload.user || typeof payload.user.username !== 'string' || !Array.isArray(payload.user.roles)) {
    return null;
  }
  return payload.user;
}

export function setSessionCookies(
  request: NextRequest,
  response: NextResponse,
  tokens: OpsTokenEnvelope,
): void {
  const common = {
    httpOnly: true,
    secure: externalProtocol(request) === 'https',
    sameSite: 'strict' as const,
    path: '/',
  };

  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    ...common,
    maxAge: positiveSeconds(tokens.expires_in),
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    ...common,
    maxAge: positiveSeconds(tokens.refresh_expires_in),
  });
}

export function clearSessionCookies(response: NextResponse): void {
  response.cookies.set(ACCESS_COOKIE, '', {
    httpOnly: true,
    sameSite: 'strict',
    path: '/',
    maxAge: 0,
  });
  response.cookies.set(REFRESH_COOKIE, '', {
    httpOnly: true,
    sameSite: 'strict',
    path: '/',
    maxAge: 0,
  });
}

export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get('origin');
  if (!origin) return true;

  const forwardedHost = request.headers.get('x-forwarded-host')?.split(',')[0]?.trim();
  const host = forwardedHost || request.headers.get('host');
  if (!host) return false;

  return origin === `${externalProtocol(request)}://${host}`;
}

export async function copyUpstreamResponse(upstream: Response): Promise<NextResponse> {
  const body = upstream.status === 204 ? null : await upstream.arrayBuffer();
  const response = new NextResponse(body, { status: upstream.status });

  for (const header of ['content-type', 'location', 'www-authenticate']) {
    const value = upstream.headers.get(header);
    if (value) response.headers.set(header, value);
  }
  response.headers.set('Cache-Control', 'no-store');
  return response;
}

export function isAllowedOpsPath(path: string[]): boolean {
  if (path.length === 0) return false;
  if (!new Set(['actions', 'crops', 'farms']).has(path[0])) return false;
  return path.every((segment) => /^[A-Za-z0-9._~-]+$/.test(segment) && segment !== '..');
}

export function authError(message = 'Authentication required'): NextResponse {
  return NextResponse.json({ status: 'error', message }, {
    status: 401,
    headers: { 'Cache-Control': 'no-store' },
  });
}

export function forbiddenOrigin(): NextResponse {
  return NextResponse.json({ status: 'error', message: 'Cross-origin request rejected' }, {
    status: 403,
    headers: { 'Cache-Control': 'no-store' },
  });
}

function isTokenEnvelope(payload: Partial<OpsTokenEnvelope>): payload is OpsTokenEnvelope {
  return typeof payload.access_token === 'string'
    && typeof payload.refresh_token === 'string'
    && Number.isFinite(payload.expires_in)
    && Number.isFinite(payload.refresh_expires_in);
}

function positiveSeconds(value: number): number {
  return Math.max(1, Math.floor(value));
}

function externalProtocol(request: NextRequest): 'http' | 'https' {
  const forwarded = request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim();
  if (forwarded === 'https') return 'https';
  if (forwarded === 'http') return 'http';
  return request.nextUrl.protocol === 'https:' ? 'https' : 'http';
}
