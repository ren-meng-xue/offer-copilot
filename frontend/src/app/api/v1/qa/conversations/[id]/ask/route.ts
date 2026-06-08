import { type NextRequest } from "next/server";

const backendBase = process.env.BACKEND_PROXY_TARGET || "http://127.0.0.1:8080";

// Next.js API route takes precedence over next.config.ts rewrites, so this
// handler intercepts POST /api/v1/qa/conversations/:id/ask before the generic
// rewrite proxy applies. That proxy has an implicit ~120-second upstream
// timeout which kills long-lived SSE streams; here we pipe the body directly.
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const { searchParams } = request.nextUrl;
  const qs = searchParams.toString();
  const upstream = `${backendBase}/api/v1/qa/conversations/${id}/ask${qs ? `?${qs}` : ""}`;

  const forwarded = new Headers();
  for (const [k, v] of request.headers.entries()) {
    const lower = k.toLowerCase();
    if (
      lower === "host" ||
      lower === "connection" ||
      lower === "transfer-encoding"
    ) {
      continue;
    }
    forwarded.set(k, v);
  }

  const body = await request.text();

  const upstreamRes = await fetch(upstream, {
    method: "POST",
    headers: forwarded,
    body,
  });

  return new Response(upstreamRes.body, {
    status: upstreamRes.status,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
    },
  });
}
