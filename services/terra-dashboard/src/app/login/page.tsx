'use client';

import Link from 'next/link';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      router.push('/actions');
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="text-center text-gray-400 mt-16">세션 확인 중...</div>;
  }

  if (user) {
    return (
      <div className="max-w-md mx-auto mt-16 card card-body text-center space-y-4">
        <div className="text-4xl">✅</div>
        <h1 className="text-xl font-semibold">이미 로그인되어 있습니다</h1>
        <p className="text-sm text-gray-500">{user.username} · {user.roles.join(', ')}</p>
        <Link href="/actions" className="rounded-lg bg-terra-600 px-4 py-2 text-white hover:bg-terra-700">
          제어 화면으로 이동
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto mt-12 card overflow-hidden">
      <div className="card-header bg-terra-50">
        <h1 className="text-xl font-semibold text-gray-900">TerraNeuron 로그인</h1>
        <p className="text-sm text-gray-500 mt-1">Terra-Ops 사용자 계정으로 인증합니다.</p>
      </div>
      <form onSubmit={handleSubmit} className="card-body space-y-4">
        <label className="block text-sm font-medium text-gray-700">
          사용자명
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            maxLength={50}
            required
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:border-terra-500 focus:ring-2 focus:ring-terra-100"
          />
        </label>
        <label className="block text-sm font-medium text-gray-700">
          비밀번호
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            maxLength={200}
            required
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:border-terra-500 focus:ring-2 focus:ring-terra-100"
          />
        </label>
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-terra-600 px-4 py-2 text-white hover:bg-terra-700 disabled:opacity-50"
        >
          {submitting ? '로그인 중...' : '로그인'}
        </button>
        <p className="text-xs text-gray-400 text-center">
          JWT는 브라우저 JavaScript에 반환되지 않고 HttpOnly 세션 쿠키로 관리됩니다.
        </p>
      </form>
    </div>
  );
}
