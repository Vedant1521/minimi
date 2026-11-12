import { NextRequest, NextResponse } from "next/server";
import { MemoryStore } from "@/memory/store";
import { config } from "@/config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const store = new MemoryStore(config.dbPath);

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const session = store.getConversation(params.id);
    if (!session) {
      return NextResponse.json({ error: "Session not found" }, { status: 404 });
    }

    const messages = store.getMessages(params.id, 100);
    return NextResponse.json({
      session,
      messages: messages.map((m) => ({
        ...m,
        citations: m.citations ? JSON.parse(m.citations) : [],
        search_queries: m.search_queries ? JSON.parse(m.search_queries) : [],
        entities: m.entities ? JSON.parse(m.entities) : [],
      })),
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
