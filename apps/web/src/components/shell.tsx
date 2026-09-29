"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Boxes, CalendarRange, FlaskConical, GitBranch, Gauge, Lightbulb, LogIn, RefreshCw, ShieldAlert } from "lucide-react";
import { useProgram } from "./providers";

const navigation = [
  ["/dashboard", "Dashboard", Gauge], ["/timeline", "Timeline", CalendarRange],
  ["/dependencies", "Dependencies", GitBranch], ["/hardware", "Hardware", Boxes],
  ["/requirements", "Requirements", Activity], ["/validation", "Validation", FlaskConical],
  ["/risks", "Risks", ShieldAlert], ["/changes", "Changes", RefreshCw],
  ["/scenario", "Scenario", Lightbulb],
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { programs, program, setProgramId } = useProgram();
  const authEnabled = process.env.NEXT_PUBLIC_AUTH_MODE === "auth0";
  return <div className="app">
    <aside className="sidebar">
      <Link className="brand" href="/dashboard"><span className="brand-mark">A</span><span>Atlas</span></Link>
      <nav className="nav">{navigation.map(([href, label, Icon]) =>
        <Link key={href} href={href} className={pathname === href ? "active" : ""}><Icon size={17}/><span>{label}</span></Link>
      )}</nav>
      <div className="sidebar-foot">Engineering-program intelligence<br/>Local MVP · v0.1</div>
    </aside>
    <main className="main">
      <header className="topbar">
        <div className="program-select"><label>Active program</label><select value={program?.id || ""} onChange={(event) => setProgramId(event.target.value)}>{programs.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
        <div className="top-actions"><span className="status on_track">Connected</span>{authEnabled ? <a className="button" href="/auth/login"><LogIn size={14}/> Sign in / switch org</a> : <span className="button">Demo admin</span>}</div>
      </header>
      <div className="content">{children}</div>
    </main>
  </div>;
}
