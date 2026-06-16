import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const home = searchParams.get("home");
  const away = searchParams.get("away");
  const year = searchParams.get("year");
  if (!home || !away) {
    return NextResponse.json({ error: "Missing home or away parameters" }, { status: 400 });
  }
  const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
  let targetUrl = `${gatewayUrl}/api/v1/sensitivity?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`;
  if (year) {
    targetUrl += `&year=${encodeURIComponent(year)}`;
  }
  try {
    const res = await fetch(targetUrl, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch sensitivity analysis" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Internal Gateway Connection Error" }, { status: 500 });
  }
}
