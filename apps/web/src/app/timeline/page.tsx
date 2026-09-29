"use client";

import { useQuery } from "@tanstack/react-query";
import { useProgram } from "@/components/providers";
import { ResourceCreate } from "@/components/resource-create";
import { Card, ErrorState, formatDate, Loading, PageHeader, Status } from "@/components/ui";
import { api } from "@/lib/api";
import type { Schedule } from "@/lib/types";

export default function TimelinePage() {
  const { program } = useProgram();
  const query = useQuery({ queryKey: ["schedule", program?.id], queryFn: () => api<Schedule>(`/schedule/analyze?program_id=${program!.id}`), enabled: Boolean(program) });
  if (query.isLoading) return <Loading/>;
  if (query.error) return <ErrorState error={query.error}/>;
  const data = query.data;
  if (!data) return <Loading label="Select a program"/>;
  const starts = data.tasks.map((item) => new Date(item.forecast_start).getTime());
  const ends = data.tasks.map((item) => new Date(item.forecast_finish).getTime());
  const min = Math.min(...starts), max = Math.max(...ends), range = Math.max(1, max - min);
  return <>
    <PageHeader eyebrow="Integrated master schedule" title="Timeline & critical path" description="Forecast dates propagate across finish-to-start dependencies using the Monday–Friday program calendar." action={program&&<ResourceCreate programId={program.id} resource="tasks" title="Add task" onCreated={()=>query.refetch()} fields={[{name:"code",label:"Task ID",required:true},{name:"name",label:"Task name",required:true},{name:"owner",label:"Owner",required:true},{name:"duration_days",label:"Duration (business days)",type:"number",defaultValue:1,required:true},{name:"baseline_start",label:"Baseline start",type:"date",required:true},{name:"baseline_end",label:"Baseline finish",type:"date",required:true},{name:"status",label:"Status",type:"select",defaultValue:"not_started",options:["not_started","in_progress","blocked","complete"].map(value=>({value,label:value.replaceAll("_"," ")}))}]}/>}/>
    <div className="grid cols-3" style={{marginBottom: 16}}>
      <Card><div className="metric"><span>Program finish</span><strong>{formatDate(data.project_finish)}</strong></div></Card>
      <Card><div className="metric"><span>Target finish</span><strong>{formatDate(data.target_finish)}</strong></div></Card>
      <Card><div className="metric"><span>Forecast variance</span><strong className={data.variance_days > 0 ? "danger" : ""}>{data.variance_days} business days</strong></div></Card>
    </div>
    <Card title="Forecast schedule">
      <div>{data.tasks.map((task) => { const left = ((new Date(task.forecast_start).getTime() - min) / range) * 100; const width = Math.max(1.2, ((new Date(task.forecast_finish).getTime() - new Date(task.forecast_start).getTime()) / range) * 100); return <div className="gantt-row" key={task.id}><div className="gantt-label"><span className="code">{task.code}</span> {task.name}</div><div className="gantt-track"><span className={`gantt-bar ${task.is_critical ? "critical" : ""}`} style={{left: `${left}%`, width: `${width}%`}}/></div><span className="muted">{task.slack_days}d slack</span></div>; })}</div>
    </Card>
    <div className="card table-wrap" style={{marginTop: 16}}><table><thead><tr><th>Task</th><th>Forecast</th><th>Latest finish</th><th>Slack</th><th>Path</th></tr></thead><tbody>{data.tasks.map((task) => <tr key={task.id}><td><span className="code">{task.code}</span><br/>{task.name}</td><td>{formatDate(task.forecast_start)} – {formatDate(task.forecast_finish)}</td><td>{formatDate(task.latest_finish)}</td><td>{task.slack_days}d</td><td>{task.is_critical ? <Status value="critical"/> : <Status value="on_track"/>}</td></tr>)}</tbody></table></div>
  </>;
}
