import { NextResponse } from "next/server";
import { gatewayFetch } from "@/lib/gateway";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await gatewayFetch("/api/v1/simulate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }, request.headers.get("x-request-id"));
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to trigger simulation" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Gateway temporarily unavailable" }, { status: 503 });
  }
}
