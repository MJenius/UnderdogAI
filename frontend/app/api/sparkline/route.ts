import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const team = searchParams.get("team");
  if (!team) {
    return NextResponse.json({ error: "Missing team parameter" }, { status: 400 });
  }
  const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
  const targetUrl = `${gatewayUrl}/api/v1/sparkline?team=${encodeURIComponent(team)}`;
  try {
    const res = await fetch(targetUrl, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch sparkline data" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Internal Gateway Connection Error" }, { status: 500 });
  }
}
