"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { navigation } from "@/components/layout/nav";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const { user, ready, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (ready && !user) router.replace("/login");
  }, [ready, user, router]);

  if (!ready || !user) {
    return <main className="screen-message" aria-live="polite">Checking your session…</main>;
  }

  const initials = user.display_name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard" aria-label="CloudDesk overview">
          <span className="brand-mark" aria-hidden="true">C</span>
          <span className="brand-copy">
            <span className="brand-name">CloudDesk</span>
            <span className="brand-subtitle">Support console</span>
          </span>
        </Link>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list" aria-label="Main navigation">
          {navigation.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                className="nav-link"
                href={item.href}
                key={item.href}
                aria-current={active ? "page" : undefined}
                title={item.label}
              >
                <span className="nav-symbol" aria-hidden="true">{item.symbol}</span>
                <span className="nav-text">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          {user.role === "viewer" ? "Read-only access" : "Support team access"}
          <br />Ticket workflow console
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          {user.role === "viewer" && <span className="pill">Read only</span>}
          <div className="identity">
            <span className="avatar" aria-hidden="true">{initials}</span>
            <div>
              <div className="identity-name">{user.display_name}</div>
              <div className="identity-role">{user.role}</div>
            </div>
          </div>
          <button className="button" type="button" onClick={() => { signOut(); router.replace("/login"); }}>
            Sign out
          </button>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
