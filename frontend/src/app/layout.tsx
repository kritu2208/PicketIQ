import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "../context/ThemeContext";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "PicketIQ — Autonomous Business Signal Investigation Platform",
  description: "When the numbers move, PicketIQ finds out why. Autonomous, evidence-grounded anomaly investigation on enterprise business operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full antialiased" suppressHydrationWarning>
      <body className={`${inter.className} min-h-screen flex flex-col bg-slate-50 dark:bg-[#080c14] text-slate-900 dark:text-slate-100 selection:bg-indigo-500/20 selection:text-indigo-900 dark:selection:bg-indigo-500/30 dark:selection:text-indigo-200 overflow-x-hidden w-full max-w-[100vw] transition-colors duration-200`} suppressHydrationWarning>
        <ThemeProvider>
          {/* Main Command Center Workspace */}
          <main className="flex-1 w-full">
            {children}
          </main>

          {/* Technical Status Strip Footer */}
          <footer className="border-t border-slate-200 dark:border-slate-800/80 bg-white dark:bg-[#070a10] py-3 text-xs text-slate-600 dark:text-slate-400 transition-colors">
            <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
              <span className="text-[11px] font-medium font-mono">PicketIQ &bull; Deterministic Business Telemetry Investigation Engine</span>
              <div className="flex items-center space-x-3 font-mono text-[10px] text-slate-500 dark:text-slate-400">
                <span>PostgreSQL 16</span>
                <span>&bull;</span>
                <span>Deterministic Evidence</span>
                <span>&bull;</span>
                <span>Grounded Citations</span>
              </div>
            </div>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
