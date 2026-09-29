"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Background, Controls, Edge, MarkerType, MiniMap, Node, ReactFlow } from "@xyflow/react";
import { useProgram } from "@/components/providers";
import { ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Schedule } from "@/lib/types";

type Dependency = { id: string; predecessor_id: string; successor_id: string };
export default function DependenciesPage() {
  const { program } = useProgram();
  const schedule = useQuery({ queryKey: ["schedule", program?.id], queryFn: () => api<Schedule>(`/schedule/analyze?program_id=${program!.id}`), enabled: Boolean(program) });
  const dependencies = useQuery({ queryKey: ["dependencies", program?.id], queryFn: () => api<Dependency[]>(`/programs/${program!.id}/dependencies`), enabled: Boolean(program) });
  const graph = useMemo(() => {
    const critical = new Set(schedule.data?.critical_path || []);
    const nodes: Node[] = (schedule.data?.tasks || []).map((task, index) => ({ id: task.id, position: { x: (index % 8) * 190, y: Math.floor(index / 8) * 120 }, data: { label: `${task.code}\n${task.name}` }, style: { width: 165, whiteSpace: "pre-line", border: `1px solid ${critical.has(task.id) ? "#bc3c4a" : "#b7c8d3"}`, borderLeft: `5px solid ${critical.has(task.id) ? "#bc3c4a" : "#0b8f87"}`, background: "white", borderRadius: 8, padding: 9 } }));
    const edges: Edge[] = (dependencies.data || []).map((edge) => ({ id: edge.id, source: edge.predecessor_id, target: edge.successor_id, markerEnd: { type: MarkerType.ArrowClosed }, animated: critical.has(edge.predecessor_id) && critical.has(edge.successor_id), style: { stroke: critical.has(edge.predecessor_id) && critical.has(edge.successor_id) ? "#bc3c4a" : "#7890a1" } }));
    return { nodes, edges };
  }, [schedule.data, dependencies.data]);
  if (schedule.isLoading || dependencies.isLoading) return <Loading/>;
  if (schedule.error || dependencies.error) return <ErrorState error={(schedule.error || dependencies.error)!}/>;
  return <><PageHeader eyebrow="Program graph" title="Dependency network" description="Inspect the finish-to-start relationships that drive schedule propagation. Critical-path edges are highlighted and animated."/><div className="card node-panel"><ReactFlow nodes={graph.nodes} edges={graph.edges} fitView minZoom={0.2}><Background/><MiniMap pannable zoomable/><Controls/></ReactFlow></div></>;
}

