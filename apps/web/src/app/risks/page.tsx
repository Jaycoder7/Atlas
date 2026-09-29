"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useProgram } from "@/components/providers";
import { ResourceCreate } from "@/components/resource-create";
import { ErrorState, Loading, PageHeader, Status } from "@/components/ui";
import { api } from "@/lib/api";
import type { Risk } from "@/lib/types";

export default function RisksPage() {
  const { program } = useProgram();
  const [filter, setFilter] = useState("all");
  const query = useQuery({ queryKey:["risks",program?.id],queryFn:()=>api<Risk[]>(`/programs/${program!.id}/resources/risks`),enabled:Boolean(program) });
  if(query.isLoading)return <Loading/>; if(query.error)return <ErrorState error={query.error}/>; if(!program)return null;
  const risks=[...(query.data||[])].sort((a,b)=>b.score-a.score); const visible=filter==="all"?risks:risks.filter(risk=>risk.severity===filter||risk.status===filter);
  return <><PageHeader eyebrow="Program exposure" title="Risk register" description="Probability and impact produce a consistent 25-point score while affected work remains directly traceable." action={<div className="row"><select value={filter} onChange={event=>setFilter(event.target.value)}><option value="all">All risks</option>{["critical","high","medium","low","open","mitigating","accepted","closed"].map(value=><option value={value} key={value}>{value}</option>)}</select><ResourceCreate programId={program.id} resource="risks" title="Add risk" onCreated={()=>query.refetch()} fields={[{name:"code",label:"Risk ID",required:true},{name:"description",label:"Description",type:"textarea",required:true},{name:"probability",label:"Probability (1–5)",type:"number",defaultValue:3,required:true},{name:"impact",label:"Impact (1–5)",type:"number",defaultValue:3,required:true},{name:"owner",label:"Owner",required:true},{name:"mitigation",label:"Mitigation",type:"textarea"},{name:"status",label:"Status",type:"select",defaultValue:"open",options:["open","mitigating","accepted","closed"].map(value=>({value,label:value}))}]}/></div>}/>
    <div className="grid cols-4" style={{marginBottom:16}}>{["critical","high","medium","low"].map((severity)=><div className="card stat" key={severity}><div className="stat-label">{severity} risks</div><div className="stat-value">{risks.filter(risk=>risk.severity===severity).length}</div><Status value={severity}/></div>)}</div>
    <div className="card table-wrap"><table><thead><tr><th>Risk</th><th>Probability</th><th>Impact</th><th>Score</th><th>Owner</th><th>Mitigation</th><th>Status</th></tr></thead><tbody>{visible.map(risk=><tr key={risk.id}><td><span className="code">{risk.code}</span><br/><strong>{risk.description}</strong></td><td>{risk.probability}/5</td><td>{risk.impact}/5</td><td><Status value={risk.severity}/> <strong>{risk.score}</strong></td><td>{risk.owner}</td><td className="muted">{risk.mitigation}</td><td><Status value={risk.status}/></td></tr>)}</tbody></table></div>
  </>;
}
