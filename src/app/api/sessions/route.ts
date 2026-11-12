import { NextRequest, NextResponse } from "next/server";
import { MemoryStore } from "@/memory/store";
import { config } from "@/config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const store = new MemoryStore(config.dbPath);

export async function GET() {
  try {
    const sessions = store.listConversations(50);
    return NextResponse.json({ sessions });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const conv = store.createConversation(body.id, body.title);
    return NextResponse.json({ session: conv });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
