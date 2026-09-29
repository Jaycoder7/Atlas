"use client";

import { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <header className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}
export function Status({ value }: { value?: string }) { const text = value || "unknown"; return <span className={`status ${text}`}>{text.replaceAll("_", " ")}</span>; }
export function Loading({ label = "Loading program intelligence…" }: { label?: string }) { return <div className="card loading">{label}</div>; }
export function ErrorState({ error }: { error: Error }) { return <div className="card error">{error.message}</div>; }
export function Empty({ label }: { label: string }) { return <div className="empty">{label}</div>; }
export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: string }) { return <div className="card stat"><div className="stat-label">{label}</div><div className="stat-value">{value}</div>{note && <div className="stat-note">{note}</div>}</div>; }
export function Card({ title, action, children, className = "" }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) { return <section className={`card ${className}`}>{title && <div className="card-head"><h2>{title}</h2>{action}</div>}<div className="card-body">{children}</div></section>; }
export function formatDate(value?: string) { return value ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${value}T12:00:00`)) : "—"; }

