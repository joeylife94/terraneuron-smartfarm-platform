import 'server-only';

import { createHash } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';

export const ACCESS_COOKIE = 'terraneuron_access_token';
export const REFRESH_COOKIE = 'terraneuron_refresh_token';

const AUTH_COOKIE_PATH = '/api/dashboard';
const ALLOWED_OPS_ROOTS = new Set(['actions', 'crops', 'farms']);
const OPS_BASE = (process.env.TERRA_OPS_INTERNAL_URL ?? 'http://terra-ops:8080/api').replace(/\/+$/, '');
const OPS_TIMEOUT_MS = positiveMilliseconds(process.env.TERRA_OPS_BFF_TIMEOUT_MS, 5_000);
const refreshFlights = new Map<string, Promise<OpsTokenEnvelope | null>>();

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
    signal: init?.signal ?? AbortSignal.timeout(OPS_TIMEOUT_MS),
    headers: {
      Accept: 'application/json',
      ...init?.headers,
    },
  });
}

/**
 * Coalesces refresh attempts using the same bearer credential while a rotation
 * is in flight in this Dashboard process. The entry is removed immediately
 * after settlement so replay detection remains owned by Terra-Ops.
 */
export async function rotateRefreshToken(refreshToken: string): Promise<OpsTokenEnvelope | null> {
  const key = createHash('sha256').update(refreshToken).digest('hex');
  const existing = refreshFlights.get(key);
  if (existing) return existing;

  const flight = rotateRefreshTokenOnce(refreshToken);
  refreshFlights.set(key, flight);
  try {
    return await flight;
  } finally {
    if (refreshFlights.get(key) === flight) refreshFlights.delete(key);
  }
}

async function rotateRefreshTokenOnce(refreshToken: string): Promise<OpsTokenEnvelope | null> {
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
    secure: publicOrigin(request).startsWith('https://'),
    sameSite: 'strict' as const,
    path: AUTH_COOKIE_PATH,
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

export function clearAccessCookie(response: NextResponse): void {
  expireCookie(response, ACCESS_COOKIE);
}

export function clearSessionCookies(response: NextResponse): void {
  expireCookie(response, ACCESS_COOKIE);
  expireCookie(response, REFRESH_COOKIE);
}

function expireCookie(response: NextResponse, name: string): void {
  response.cookies.set(name, '', {
    httpOnly: true,
    sameSite: 'strict',
    path: AUTH_COOKIE_PATH,
    maxAge: 0,
  });
}

export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get('origin');
  return !origin || origin === publicOrigin(request);
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
  if (path.length === 0 || !ALLOWED_OPS_ROOTS.has(path[0])) return false;
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

function positiveMilliseconds(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback;
}

function publicOrigin(request: NextRequest): string {
  const configured = process.env.DASHBOARD_PUBLIC_ORIGIN?.trim();
  if (!configured) return request.nextUrl.origin;

  try {
    const origin = new URL(configured);
    if (!['http:', 'https:'].includes(origin.protocol)) throw new Error('unsupported protocol');
    return origin.origin;
  } catch {
    throw new Error('DASHBOARD_PUBLIC_ORIGIN must be an absolute HTTP(S) origin');
  }
}
