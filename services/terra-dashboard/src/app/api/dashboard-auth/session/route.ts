import { NextRequest, NextResponse } from 'next/server';
import { ACCESS_COOKIE, REFRESH_COOKIE, rotateRefreshToken, setSessionCookies, validateAccessToken, clearSessionCookies } from '@/lib/server/ops-session';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest): Promise<NextResponse> {
  const current = request.cookies.get(ACCESS_COOKIE)?.value;
  if (current) {
    const user = await validateAccessToken(current);
    if (user) {
      return NextResponse.json({ authenticated: true, user }, { headers: { 'Cache-Control': 'no-store' } });
    }
  }

  const renewal = request.cookies.get(REFRESH_COOKIE)?.value;
  if (renewal) {
    const rotated = await rotateRefreshToken(renewal);
    if (rotated) {
      const user = await validateAccessToken(rotated.access_token);
      if (user) {
        const response = NextResponse.json({ authenticated: true, user }, { headers: { 'Cache-Control': 'no-store' } });
        setSessionCookies(request, response, rotated);
        return response;
      }
    }
  }

  const response = NextResponse.json({ authenticated: false }, { status: 401, headers: { 'Cache-Control': 'no-store' } });
  clearSessionCookies(response);
  return response;
}
