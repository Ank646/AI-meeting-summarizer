import type { Metadata } from 'next';
import './globals.css';
import AppShell from '@/components/Layout/AppShell';

export const metadata: Metadata = {
  title: 'Nexus — AI Meeting Intelligence',
  description: 'Real-time AI execution intelligence platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // No hardcoded theme class — AppShell applies 'dark' or 'light' to <html> via JS
    <html lang="en" className="dark">
      <body className="h-screen overflow-hidden bg-[var(--bg)] text-[var(--text)]">

        {/* Ambient background glows — softened by CSS in light mode */}
        <div className="ambient-glow pointer-events-none fixed inset-0 overflow-hidden z-0">
          <div
            className="absolute -top-40 -left-20 w-96 h-96 rounded-full opacity-20"
            style={{ background: 'radial-gradient(circle, #7c3aed 0%, transparent 70%)' }}
          />
          <div
            className="absolute top-1/2 -right-32 w-80 h-80 rounded-full opacity-10"
            style={{ background: 'radial-gradient(circle, #06b6d4 0%, transparent 70%)' }}
          />
          <div
            className="absolute -bottom-20 left-1/3 w-72 h-72 rounded-full opacity-10"
            style={{ background: 'radial-gradient(circle, #4f46e5 0%, transparent 70%)' }}
          />
        </div>

        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
