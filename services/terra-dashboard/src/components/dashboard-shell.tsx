'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { AuthProvider, useAuth } from '@/lib/auth-context';

const protectedPaths = ['/actions', '/crops'];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ShellContent>{children}</ShellContent>
    </AuthProvider>
  );
}

function ShellContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const protectedRoute = protectedPaths.some((path) => pathname === path || pathname.startsWith(`${path}/`));

  async function handleLogout() {
    await logout();
    router.push('/login');
    router.refresh();
  }

  let page = children;
  if (protectedRoute && loading) page = <SessionLoading />;
  if (protectedRoute && !loading && !user) page = <LoginRequired />;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-50 bg-terra-800 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 min-h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xl">🌱</span>
            <span className="font-bold text-lg tracking-tight">TerraNeuron</span>
            <span className="text-terra-300 text-sm hidden sm:inline">Smart Farm Platform</span>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/" className="hover:text-terra-300 transition">대시보드</Link>
            <Link href="/sensors" className="hover:text-terra-300 transition">센서</Link>
            <Link href="/crops" className="hover:text-terra-300 transition">작물</Link>
            <Link href="/actions" className="hover:text-terra-300 transition">제어</Link>
            <Link href="/alerts" className="hover:text-terra-300 transition">알림</Link>
          </nav>
          <div className="flex items-center gap-3 text-xs">
            {loading ? (
              <span className="text-terra-300">세션 확인 중</span>
            ) : user ? (
              <>
                <span className="hidden lg:inline text-terra-100">
                  {user.username} · {user.roles.join(', ')}
                </span>
                <button onClick={handleLogout} className="rounded border border-terra-400 px-3 py-1.5 hover:bg-terra-700">
                  로그아웃
                </button>
              </>
            ) : (
              <Link href="/login" className="rounded bg-white px-3 py-1.5 font-medium text-terra-800 hover:bg-terra-50">
                로그인
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">{page}</main>

      <footer className="border-t border-gray-200 py-4 text-center text-xs text-gray-400">
        TerraNeuron v2.0 — Hybrid AI Smart Farm Platform
      </footer>
    </div>
  );
}

function SessionLoading() {
  return (
    <div className="max-w-lg mx-auto mt-16 card card-body text-center space-y-3" aria-live="polite">
      <div className="text-3xl animate-pulse">🔐</div>
      <h1 className="text-lg font-semibold text-gray-900">세션을 확인하고 있습니다</h1>
      <p className="text-sm text-gray-500">인증 확인이 끝날 때까지 보호된 화면과 API 요청을 시작하지 않습니다.</p>
    </div>
  );
}

function LoginRequired() {
  return (
    <div className="max-w-lg mx-auto mt-16 card card-body text-center space-y-4">
      <div className="text-4xl">🔐</div>
      <h1 className="text-xl font-semibold text-gray-900">로그인이 필요한 화면입니다</h1>
      <p className="text-sm text-gray-500">
        보호된 Terra-Ops 데이터와 제어 기능은 인증된 사용자에게만 제공됩니다.
      </p>
      <Link href="/login" className="inline-flex justify-center rounded-lg bg-terra-600 px-4 py-2 text-white hover:bg-terra-700">
        로그인으로 이동
      </Link>
    </div>
  );
}
