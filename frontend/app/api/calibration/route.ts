import { NextResponse } from "next/server";

export async function GET() {
  const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
  const targetUrl = `${gatewayUrl}/api/v1/calibration`;
  try {
    const res = await fetch(targetUrl, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch calibration" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Internal Gateway Connection Error" }, { status: 500 });
  }
}
