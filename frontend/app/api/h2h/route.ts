import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const teamA = searchParams.get("team_a");
  const teamB = searchParams.get("team_b");
  const year = searchParams.get("year");
  if (!teamA || !teamB) {
    return NextResponse.json({ error: "Missing team_a or team_b parameters" }, { status: 400 });
  }
  const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
  let targetUrl = `${gatewayUrl}/api/v1/h2h?team_a=${encodeURIComponent(teamA)}&team_b=${encodeURIComponent(teamB)}`;
  if (year) {
    targetUrl += `&year=${encodeURIComponent(year)}`;
  }
  try {
    const res = await fetch(targetUrl, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch H2H data" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Internal Gateway Connection Error" }, { status: 500 });
  }
}
