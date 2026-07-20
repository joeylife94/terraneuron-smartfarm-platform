import { NextRequest, NextResponse } from 'next/server';
import { callOps, clearSessionCookies, forbiddenOrigin, isSameOrigin, REFRESH_COOKIE } from '@/lib/server/ops-session';

export const dynamic = 'force-dynamic';
const LOGOUT_REVOCATION_TIMEOUT_MS = 1_500;

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOrigin(request)) return forbiddenOrigin();

  const response = new NextResponse(null, { status: 204 });
  clearSessionCookies(response);

  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (refreshToken) {
    await callOps('/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken }),
      signal: AbortSignal.timeout(LOGOUT_REVOCATION_TIMEOUT_MS),
    }).catch(() => null);
  }

  return response;
}
