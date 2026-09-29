"use client";

import { useQuery } from "@tanstack/react-query";
import { useProgram } from "@/components/providers";
import { ResourceCreate } from "@/components/resource-create";
import { ErrorState, Loading, PageHeader, Status } from "@/components/ui";
import { api } from "@/lib/api";
import type { Snapshot } from "@/lib/types";

export default function RequirementsPage() {
  const { program } = useProgram();
  const query = useQuery({ queryKey: ["snapshot", program?.id], queryFn: () => api<Snapshot>(`/programs/${program!.id}/snapshot`), enabled: Boolean(program) });
  if (query.isLoading) return <Loading/>; if (query.error) return <ErrorState error={query.error}/>; if (!query.data || !program) return null;
  const requirements = query.data.resources.requirements;
  const tests = Object.fromEntries(query.data.resources.tests.map((item) => [item.id, item]));
  const links = query.data.resources["requirement-test-links"];
  const linked = (requirementId: string) => links.filter((item) => item.requirement_id === requirementId).map((item) => tests[item.test_id]).filter(Boolean);
  return <><PageHeader eyebrow="Verification traceability" title="Requirements" description="Every requirement rolls up the latest status of its required validation evidence." action={<ResourceCreate programId={program.id} resource="requirements" title="Add requirement" onCreated={() => query.refetch()} fields={[{name:"code",label:"Requirement ID",required:true},{name:"title",label:"Title",required:true},{name:"description",label:"Description",type:"textarea"},{name:"status",label:"Initial status",type:"select",defaultValue:"not_tested",options:["not_tested","blocked","verified","failed"].map(value=>({value,label:value.replaceAll("_"," ")}))}]}/>}/>
    <div className="grid cols-4" style={{marginBottom:16}}>{["verified","failed","blocked","not_tested"].map((status) => <div className="card stat" key={status}><div className="stat-label">{status.replaceAll("_"," ")}</div><div className="stat-value">{requirements.filter((item) => item.status === status).length}</div><Status value={status}/></div>)}</div>
    <div className="card table-wrap"><table><thead><tr><th>Requirement</th><th>Description</th><th>Linked validation</th><th>Status</th></tr></thead><tbody>{requirements.map((requirement) => <tr key={requirement.id}><td><span className="code">{requirement.code}</span><br/><strong>{requirement.title}</strong></td><td className="muted">{requirement.description}</td><td><div className="pill-list">{linked(requirement.id).map((test) => <span className="pill code" key={test.id}>{test.code}</span>)}</div></td><td><Status value={requirement.status}/></td></tr>)}</tbody></table></div>
  </>;
}

