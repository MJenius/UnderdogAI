import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
  try {
    const body = await request.json();
    const res = await fetch(`${gatewayUrl}/api/v1/simulate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to trigger simulation" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Internal Gateway Connection Error" }, { status: 500 });
  }
}
