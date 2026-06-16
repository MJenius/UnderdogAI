import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const year = searchParams.get("year");
  if (!year) {
    return NextResponse.json({ error: "Missing year parameter" }, { status: 400 });
  }
  const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
  const targetUrl = `${gatewayUrl}/api/v1/historical-upsets?year=${encodeURIComponent(year)}`;
  try {
    const res = await fetch(targetUrl, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch historical upsets" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Internal Gateway Connection Error" }, { status: 500 });
  }
}
