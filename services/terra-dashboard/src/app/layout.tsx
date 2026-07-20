import type { Metadata } from 'next';
import { DashboardShell } from '@/components/dashboard-shell';
import './globals.css';

export const metadata: Metadata = {
  title: 'TerraNeuron Dashboard',
  description: '스마트팜 실시간 모니터링 대시보드',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="antialiased">
        <DashboardShell>{children}</DashboardShell>
      </body>
    </html>
  );
}
