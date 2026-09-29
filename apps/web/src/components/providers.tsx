"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Program } from "@/lib/types";

type ProgramContextValue = { programs: Program[]; program?: Program; setProgramId: (id: string) => void; loading: boolean };
const ProgramContext = createContext<ProgramContextValue>({ programs: [], setProgramId: () => {}, loading: true });

export function useProgram() { return useContext(ProgramContext); }

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1 } } }));
  const [programs, setPrograms] = useState<Program[]>([]);
  const [programId, setProgramIdState] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api<Program[]>("/programs").then((items) => {
      setPrograms(items);
      const saved = localStorage.getItem("atlas-program");
      setProgramIdState(items.some((item) => item.id === saved) ? saved! : items[0]?.id || "");
    }).finally(() => setLoading(false));
  }, []);
  const setProgramId = (id: string) => { localStorage.setItem("atlas-program", id); setProgramIdState(id); queryClient.clear(); };
  const value = useMemo(() => ({ programs, program: programs.find((item) => item.id === programId), setProgramId, loading }), [programs, programId, loading]);
  return <QueryClientProvider client={queryClient}><ProgramContext.Provider value={value}>{children}</ProgramContext.Provider></QueryClientProvider>;
}
