import { NextResponse } from "next/server";
import { gatewayFetch } from "@/lib/gateway";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const res = await gatewayFetch(
      `/api/v1/simulate/status/${encodeURIComponent(id)}`,
      {},
      request.headers.get("x-request-id"),
    );
    if (!res.ok) {
      return NextResponse.json({ task_id: id, status: "UNAVAILABLE" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ task_id: id, status: "UNAVAILABLE" }, { status: 503 });
  }
}
