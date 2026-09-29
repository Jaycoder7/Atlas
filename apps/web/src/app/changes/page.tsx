"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Link2 } from "lucide-react";
import { useProgram } from "@/components/providers";
import { Card, ErrorState, Loading, PageHeader, Status } from "@/components/ui";
import { api } from "@/lib/api";

type Change={id:string;code:string;title:string;description:string;status:string;schedule_impact_days:number};
type Impact={change:Change;counts:Record<string,number>;affected:Record<string,string[]>;dependency_paths:Record<string,string[]>;projected_schedule_impact_days:number;current_project_finish:string};
type Suggestions={available:boolean;suggestions:{entity_type:string;entity_id:string;confidence:number;rationale:string}[];message?:string};
export default function ChangesPage(){
  const {program}=useProgram(); const [selected,setSelected]=useState(""); const [suggestions,setSuggestions]=useState<Suggestions|null>(null); const [aiBusy,setAiBusy]=useState(false);
  const changes=useQuery({queryKey:["changes",program?.id],queryFn:()=>api<Change[]>(`/programs/${program!.id}/resources/engineering-changes`),enabled:Boolean(program)});
  useEffect(()=>{if(!selected&&changes.data?.length)setSelected(changes.data.at(-1)!.id)},[changes.data,selected]);
  const impact=useQuery({queryKey:["impact",selected],queryFn:()=>api<Impact>(`/changes/${selected}/impact`),enabled:Boolean(selected)});
  async function askAi(){setAiBusy(true);try{setSuggestions(await api<Suggestions>(`/changes/${selected}/suggestions`));}finally{setAiBusy(false)}}
  async function accept(item:Suggestions["suggestions"][number]){await api(`/changes/${selected}/suggestions/accept`,{method:"POST",body:JSON.stringify(item)});setSuggestions(prev=>prev?{...prev,suggestions:prev.suggestions.filter(candidate=>candidate!==item)}:prev);impact.refetch()}
  if(changes.isLoading)return <Loading/>; if(changes.error)return <ErrorState error={changes.error}/>;
  return <><PageHeader eyebrow="Configuration control" title="Engineering changes" description="Authoritative impact comes from explicit relationships and downstream schedule traversal. Local AI may propose—but never create—missing links." action={<select value={selected} onChange={event=>{setSelected(event.target.value);setSuggestions(null)}}>{changes.data?.map(change=><option value={change.id} key={change.id}>{change.code} · {change.title}</option>)}</select>}/>
    {impact.isLoading?<Loading/>:impact.error?<ErrorState error={impact.error}/>:impact.data&&<div className="split"><div className="stack"><Card title={`${impact.data.change.code} · ${impact.data.change.title}`} action={<Status value={impact.data.change.status}/>}><p>{impact.data.change.description}</p><div className="grid cols-3">{Object.entries(impact.data.counts).map(([label,count])=><div className="stat" key={label}><div className="stat-label">{label.replaceAll("_"," ")}</div><div className="stat-value">{count}</div></div>)}</div></Card><Card title="Explainable propagation"><div className="stack">{Object.entries(impact.data.dependency_paths).slice(0,12).map(([id,path])=><div key={id}><span className="code">{path.join(" → ")}</span></div>)}</div></Card></div><div className="stack"><Card title="Projected impact"><div className="stat-value danger">+{impact.data.projected_schedule_impact_days} days</div><p>Deterministic estimate based on the change record and connected schedule graph.</p></Card><Card title="Advisory link suggestions" action={<BrainCircuit size={18}/>}><button className="button" onClick={askAi} disabled={aiBusy}>{aiBusy?"Analyzing locally…":"Ask local Ollama"}</button>{suggestions&&!suggestions.available&&<p className="muted">{suggestions.message}</p>}<div className="stack" style={{marginTop:12}}>{suggestions?.suggestions.map(item=><div className="callout" key={`${item.entity_type}-${item.entity_id}`}><strong>{item.entity_type} · {Math.round(item.confidence*100)}%</strong><p>{item.rationale}</p><button className="button" onClick={()=>accept(item)}><Link2 size={13}/>Accept explicit link</button></div>)}</div></Card></div></div>}
  </>;
}

