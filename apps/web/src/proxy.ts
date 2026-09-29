import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { auth0, authEnabled } from "@/lib/auth0";

export async function proxy(request: NextRequest) {
  return authEnabled ? auth0.middleware(request) : NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)"],
};
