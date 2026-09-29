"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";

type Field = { name: string; label: string; type?: "text" | "number" | "date" | "textarea" | "select"; required?: boolean; defaultValue?: string | number; options?: { label: string; value: string }[] };

export function ResourceCreate({ programId, resource, title, fields, onCreated }: { programId: string; resource: string; title: string; fields: Field[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(fields.map((field) => {
      const value = form.get(field.name);
      return [field.name, field.type === "number" ? Number(value) : value];
    }));
    try { await api(`/programs/${programId}/resources/${resource}`, { method: "POST", body: JSON.stringify(payload) }); setOpen(false); onCreated(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create resource"); }
    finally { setBusy(false); }
  }
  if (!open) return <button className="button primary" onClick={() => setOpen(true)}><Plus size={14}/> {title}</button>;
  return <div className="card" style={{position: "fixed", inset: "12% max(16px, calc(50% - 300px)) auto", zIndex: 60, boxShadow: "0 24px 80px rgba(12,35,50,.25)"}}><div className="card-head"><h2>{title}</h2><button className="button" onClick={() => setOpen(false)}>Close</button></div><form className="card-body stack" onSubmit={submit}><div className="form-grid">{fields.map((field) => <div className="field" key={field.name}><label>{field.label}</label>{field.type === "textarea" ? <textarea name={field.name} defaultValue={field.defaultValue} required={field.required}/> : field.type === "select" ? <select name={field.name} defaultValue={field.defaultValue} required={field.required}>{field.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input name={field.name} type={field.type || "text"} defaultValue={field.defaultValue} required={field.required}/>}</div>)}</div>{error && <div className="error" style={{padding: 0}}>{error}</div>}<button className="button primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button></form></div>;
}

