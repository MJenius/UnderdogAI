import { NextResponse } from "next/server";
import { Pool } from "pg";

const pool = new Pool({
  host: process.env.POSTGRES_HOST || "localhost",
  port: parseInt(process.env.POSTGRES_PORT || "5433"),
  database: process.env.POSTGRES_DB || "analytical_sandbox",
  user: process.env.POSTGRES_USER || "postgres",
  password: process.env.POSTGRES_PASSWORD || "postgres",
});

const nameMapping: Record<string, string> = {
  "USA": "United States",
  "IR Iran": "Iran",
  "Korea Republic": "South Korea",
  "Türkiye": "Turkey",
  "Czechia": "Czech Republic",
  "Côte d'Ivoire": "Ivory Coast",
  "Congo DR": "DR Congo",
  "Cabo Verde": "Cape Verde",
  "Brunei Darussalam": "Brunei",
  "The Gambia": "Gambia",
  "Hong Kong, China": "Hong Kong",
  "China PR": "China",
};

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const year = searchParams.get("year");
  if (!year) {
    return NextResponse.json({ error: "Missing year parameter" }, { status: 400 });
  }
  const yearInt = parseInt(year);
  if (yearInt < 1993) {
    switch (yearInt) {
      case 1970:
        return NextResponse.json([
          "Belgium",
          "Brazil",
          "Bulgaria",
          "Czechoslovakia",
          "El Salvador",
          "England",
          "Israel",
          "Italy",
          "Mexico",
          "Morocco",
          "Peru",
          "Romania",
          "Soviet Union",
          "Sweden",
          "Uruguay",
          "West Germany"
        ]);
      default:
        return NextResponse.json([]);
    }
  }
  try {
    const client = await pool.connect();
    try {
      const query = `
        SELECT DISTINCT country_full AS team
        FROM public.raw_fifa_rankings
        WHERE rank_date = (
            SELECT MAX(rank_date)
            FROM public.raw_fifa_rankings
            WHERE rank_date <= MAKE_DATE($1, 1, 1)
        )
        ORDER BY team ASC;
      `;
      const result = await client.query(query, [yearInt]);
      const teams = result.rows.map((row) => nameMapping[row.team] || row.team);
      return NextResponse.json(Array.from(new Set(teams)).sort());
    } finally {
      client.release();
    }
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : String(err) }, { status: 500 });
  }
}
