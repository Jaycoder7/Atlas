import { NextRequest, NextResponse } from "next/server";
import { auth0, authEnabled } from "@/lib/auth0";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const base = process.env.API_INTERNAL_URL || "http://localhost:8000/api/v1";
  const upstream = new URL(`${base}/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => upstream.searchParams.append(key, value));
  const headers = new Headers({ "content-type": request.headers.get("content-type") || "application/json" });
  if (authEnabled) {
    try {
      const { token } = await auth0.getAccessToken();
      if (token) headers.set("authorization", `Bearer ${token}`);
    } catch {
      // The backend returns the authoritative 401 when an Auth0 session is absent or expired.
    }
  }
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.text();
  const response = await fetch(upstream, { method: request.method, headers, body, cache: "no-store" });
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") || "application/json" },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
