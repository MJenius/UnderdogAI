import { NextResponse } from "next/server";
import { gatewayFetch } from "@/lib/gateway";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const home = searchParams.get("home");
  const away = searchParams.get("away");
  const year = searchParams.get("year");
  if (!home || !away) {
    return NextResponse.json({ error: "Missing home or away parameters" }, { status: 400 });
  }
  let targetUrl = `/api/v1/predict?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`;
  if (year) {
    targetUrl += `&year=${encodeURIComponent(year)}`;
  }
  try {
    const res = await gatewayFetch(targetUrl, {}, request.headers.get("x-request-id"));
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch prediction" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Gateway temporarily unavailable" }, { status: 503 });
  }
}
