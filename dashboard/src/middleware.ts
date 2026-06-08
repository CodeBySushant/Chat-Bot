import { NextResponse, type NextRequest } from "next/server";

// First-paint guard: redirect unauthenticated users away from the dashboard and
// authenticated users away from auth pages. Full validation happens client-side
// (Bearer tokens) + server-side (the API enforces auth on every request).
const PROTECTED = ["/dashboard", "/knowledge-base", "/documents", "/crawl", "/chatbot", "/conversations", "/leads", "/analytics", "/billing", "/account"];
const AUTH_PAGES = ["/login", "/register"];

export function middleware(req: NextRequest) {
  const authed = req.cookies.get("cb_authed")?.value === "1";
  const { pathname } = req.nextUrl;
  if (!authed && PROTECTED.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  if (authed && AUTH_PAGES.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"] };
