import { NextResponse } from "next/server";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const gatewayUrl = process.env.GATEWAY_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${gatewayUrl}/api/v1/simulate/status/${id}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ task_id: id, status: "ERROR" });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ task_id: id, status: "ERROR" });
  }
}
