"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CalendarCheck, Flag, GitCommitHorizontal, TestTube2 } from "lucide-react";
import { useProgram } from "@/components/providers";
import { Card, ErrorState, formatDate, Loading, PageHeader, Stat, Status } from "@/components/ui";
import { api } from "@/lib/api";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const { program, loading } = useProgram();
  const query = useQuery({ queryKey: ["dashboard", program?.id], queryFn: () => api<Dashboard>(`/dashboard?program_id=${program!.id}`), enabled: Boolean(program) });
  if (loading || query.isLoading) return <Loading/>;
  if (query.error) return <ErrorState error={query.error}/>;
  if (!query.data) return <Loading label="No program selected"/>;
  const data = query.data;
  return <>
    <PageHeader eyebrow="Executive overview" title="Program health" description="One connected view of schedule pressure, hardware readiness, validation status, and decisions requiring attention." action={<button className="button" onClick={() => query.refetch()}>Refresh analysis</button>}/>
    <div className="grid cols-4">
      <Stat label="Target completion" value={formatDate(data.target_completion)} note="Committed release date"/>
      <Stat label="Forecast completion" value={formatDate(data.forecast_completion)} note={data.program_health.schedule === "at_risk" ? "Schedule intervention required" : "Within available margin"}/>
      <Stat label="Blocked tasks" value={data.counts.blocked_tasks || 0} note={`${data.counts.tasks || 0} total program tasks`}/>
      <Stat label="Open risks" value={data.counts.open_risks || 0} note={`${data.counts.failed_tests || 0} failed validation tests`}/>
    </div>
    <div className="split" style={{marginTop: 16}}>
      <div className="stack">
        <Card title="Cross-functional health">
          {Object.entries(data.program_health).map(([area, status]) => <div className="health-row" key={area}><strong style={{textTransform: "capitalize"}}>{area}</strong><Status value={status}/></div>)}
        </Card>
        <Card title="Critical path" action={<GitCommitHorizontal size={18}/>}>
          <div className="pill-list">{data.critical_path.length ? data.critical_path.map((code) => <span className="pill code" key={code}>{code}</span>) : <span className="muted">No critical tasks detected.</span>}</div>
        </Card>
        {data.top_blocker && <Card title="Top blocker" action={<AlertTriangle size={18} color="#bc3c4a"/>}><div className="row between"><div><div className="code">{data.top_blocker.code}</div><strong>{data.top_blocker.name}</strong><p style={{marginBottom: 0}}>Owner: {data.top_blocker.owner}</p></div><Status value={data.top_blocker.status}/></div></Card>}
      </div>
      <div className="stack">
        <Card title="Current milestone" action={<Flag size={18}/>}>{data.current_milestone ? <div className="metric-list"><div className="metric"><span>Name</span><strong>{String(data.current_milestone.name)}</strong></div><div className="metric"><span>Target</span><strong>{formatDate(String(data.current_milestone.target_date))}</strong></div><div className="metric"><span>Forecast</span><strong>{formatDate(String(data.current_milestone.forecast_date || data.current_milestone.target_date))}</strong></div></div> : <p>No upcoming milestone.</p>}</Card>
        <Card title="Highest risks">
          <div className="stack">{data.highest_risks.map((risk) => <div className="row between" key={risk.id}><div><div className="code">{risk.code}</div><span>{risk.description}</span></div><Status value={risk.severity}/></div>)}</div>
        </Card>
        <Card title="Required decisions" action={<ArrowRight size={18}/>}>
          {data.required_decisions.length ? data.required_decisions.map((decision) => <div key={String(decision.id)}><strong>{String(decision.title)}</strong><p>{String(decision.rationale || "Decision required")}</p></div>) : <p>No unresolved decisions.</p>}
        </Card>
      </div>
    </div>
  </>;
}

