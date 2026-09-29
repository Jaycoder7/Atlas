"use client";

import { useQuery } from "@tanstack/react-query";
import { useProgram } from "@/components/providers";
import { ResourceCreate } from "@/components/resource-create";
import { ErrorState, formatDate, Loading, PageHeader, Status } from "@/components/ui";
import { api } from "@/lib/api";
import type { Snapshot } from "@/lib/types";

export default function HardwarePage() {
  const { program } = useProgram();
  const query = useQuery({ queryKey: ["snapshot", program?.id], queryFn: () => api<Snapshot>(`/programs/${program!.id}/snapshot`), enabled: Boolean(program) });
  if (query.isLoading) return <Loading/>; if (query.error) return <ErrorState error={query.error}/>; if (!query.data || !program) return null;
  const revisions = Object.fromEntries(query.data.resources["hardware-revisions"].map((item) => [item.id, item.code]));
  const units = query.data.resources["hardware-units"];
  return <><PageHeader eyebrow="Prototype control" title="Hardware inventory" description="Track revision, custody, allocation, availability, and failure state for every physical engineering sample." action={<ResourceCreate programId={program.id} resource="hardware-units" title="Add prototype" onCreated={() => query.refetch()} fields={[{name:"serial_number",label:"Serial number",required:true},{name:"revision_id",label:"Revision",type:"select",required:true,options:Object.entries(revisions).map(([value,label])=>({value,label:String(label)}))},{name:"current_owner",label:"Current owner",required:true},{name:"available_date",label:"Available date",type:"date",required:true},{name:"status",label:"Status",type:"select",defaultValue:"available",options:["available","allocated","testing","failed","obsolete"].map(value=>({value,label:value}))}]}/>}/>
    {query.data.hardware_warnings.length > 0 && <div className="callout warning" style={{marginBottom:16}}>{query.data.hardware_warnings.length} allocation warning{query.data.hardware_warnings.length === 1 ? "" : "s"} require attention: {query.data.hardware_warnings.map((item) => String(item.type).replaceAll("_"," ")).join(", ")}.</div>}
    <div className="grid cols-4" style={{marginBottom:16}}>{units.map((unit) => <div className="card stat" key={unit.id}><div className="row between"><span className="code">{unit.serial_number}</span><Status value={unit.status}/></div><div className="stat-value" style={{fontSize:20}}>{revisions[unit.revision_id] || "Unknown rev"}</div><div className="stat-note">{unit.current_owner} · available {formatDate(unit.available_date)}</div>{unit.current_test && <p style={{fontSize:12}}>Current: {unit.current_test}</p>}{unit.failure_state && <p className="danger" style={{fontSize:12}}>{unit.failure_state}</p>}</div>)}</div>
    <div className="card table-wrap"><table><thead><tr><th>Unit</th><th>Revision</th><th>Owner</th><th>Current test</th><th>Available</th><th>Status</th></tr></thead><tbody>{units.map((unit) => <tr key={unit.id}><td className="code">{unit.serial_number}</td><td>{revisions[unit.revision_id]}</td><td>{unit.current_owner}</td><td>{unit.current_test || "—"}</td><td>{formatDate(unit.available_date)}</td><td><Status value={unit.status}/></td></tr>)}</tbody></table></div>
  </>;
}
