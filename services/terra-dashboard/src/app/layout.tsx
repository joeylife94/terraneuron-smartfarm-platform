import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TerraNeuron Dashboard',
  description: '스마트팜 실시간 모니터링 대시보드',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="antialiased">
        <div className="min-h-screen flex flex-col">
          {/* ── 상단 네비게이션 ── */}
          <header className="sticky top-0 z-50 bg-terra-800 text-white shadow-lg">
            <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-xl">🌱</span>
                <span className="font-bold text-lg tracking-tight">TerraNeuron</span>
                <span className="text-terra-300 text-sm hidden sm:inline">Smart Farm Platform</span>
              </div>
              <nav className="flex items-center gap-6 text-sm">
                <a href="/" className="hover:text-terra-300 transition">대시보드</a>
                <a href="/sensors" className="hover:text-terra-300 transition">센서</a>
                <a href="/crops" className="hover:text-terra-300 transition">작물</a>
                <a href="/actions" className="hover:text-terra-300 transition">제어</a>
                <a href="/alerts" className="hover:text-terra-300 transition">알림</a>
              </nav>
            </div>
          </header>

          {/* ── 메인 콘텐츠 ── */}
          <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
            {children}
          </main>

          {/* ── 푸터 ── */}
          <footer className="border-t border-gray-200 py-4 text-center text-xs text-gray-400">
            TerraNeuron v2.0 — Hybrid AI Smart Farm Platform
          </footer>
        </div>
      </body>
    </html>
  );
}
