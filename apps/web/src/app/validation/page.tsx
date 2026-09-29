"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, ShieldX } from "lucide-react";
import { useProgram } from "@/components/providers";
import { ErrorState, Loading, PageHeader, Status } from "@/components/ui";
import { api } from "@/lib/api";
import type { Snapshot } from "@/lib/types";

export default function ValidationPage() {
  const { program } = useProgram(); const queryClient = useQueryClient(); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: ["snapshot", program?.id], queryFn: () => api<Snapshot>(`/programs/${program!.id}/snapshot`), enabled: Boolean(program) });
  async function thermalFailure() {
    if (!program) return; setBusy(true); setMessage("");
    try { const result = await api<{created:boolean}>("/test-runs", { method:"POST", body:JSON.stringify({external_run_id:`thermal-failure-${Date.now()}`,program_id:program.id,test_code:"TEST-021",hardware_serial:"P1-003",measured_value:{temperature_c:52.8,regulator_voltage_v:2.71,limit_v:3.1},status:"fail"}) }); setMessage(result.created ? "Thermal failure ingested. Requirements, hardware, tasks, risks, and schedule were updated atomically." : "This run was already processed."); await query.refetch(); queryClient.invalidateQueries(); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Failure submission failed"); } finally { setBusy(false); }
  }
  if (query.isLoading) return <Loading/>; if (query.error) return <ErrorState error={query.error}/>; if (!query.data) return null;
  const tests = query.data.resources.tests;
  const links = query.data.resources["requirement-test-links"];
  const requirements = Object.fromEntries(query.data.resources.requirements.map((item)=>[item.id,item]));
  return <><PageHeader eyebrow="Automated evidence" title="Validation campaigns" description="Validation results arrive through the same authenticated, idempotent API used by the Python test runner." action={<button className="button danger" onClick={thermalFailure} disabled={busy}><ShieldX size={15}/>{busy ? "Submitting…" : "Run Rev C thermal failure"}</button>}/>
    {message && <div className="callout warning" style={{marginBottom:16}}>{message}</div>}
    <div className="grid cols-4" style={{marginBottom:16}}>{["pass","fail","blocked","not_run"].map((status)=><div className="card stat" key={status}><div className="stat-label">{status.replaceAll("_"," ")}</div><div className="stat-value">{tests.filter(item=>item.status===status).length}</div><Status value={status}/></div>)}</div>
    <div className="card table-wrap"><table><thead><tr><th>Test</th><th>Procedure</th><th>Requirement evidence</th><th>Status</th></tr></thead><tbody>{tests.map((test)=><tr key={test.id}><td className="code">{test.code}</td><td><strong>{test.name}</strong><br/><span className="muted">{test.description}</span></td><td><div className="pill-list">{links.filter(link=>link.test_id===test.id).map(link=><span className="pill code" key={link.id}>{requirements[link.requirement_id]?.code}</span>)}</div></td><td><Status value={test.status}/></td></tr>)}</tbody></table></div>
  </>;
}

