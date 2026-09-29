import type { Metadata } from "next";
import "@/app/globals.css";
import "@xyflow/react/dist/style.css";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";

export const metadata: Metadata = { title: "Atlas | Program Intelligence", description: "Connected program intelligence for complex hardware development" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
