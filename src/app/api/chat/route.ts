import { NextRequest } from "next/server";
import { AgentOrchestrator } from "@/agent/orchestrator";
import crypto from "crypto";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Global singleton orchestrator for Route Handlers
const orchestrator = new AgentOrchestrator();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const message = (body.message || "").trim();
    const conversationId = body.conversationId || crypto.randomUUID();
    const timezone = body.timezone || "UTC";

    if (!message) {
      return new Response(JSON.stringify({ error: "Message content cannot be empty." }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        try {
          for await (const event of orchestrator.processTurnStream(conversationId, message, timezone)) {
            const payload = `event: ${event.type}\ndata: ${JSON.stringify(event.data || {})}\n\n`;
            controller.enqueue(encoder.encode(payload));
          }
        } catch (err: unknown) {
          const errMsg = err instanceof Error ? err.message : String(err);
          const errorPayload = `event: error\ndata: ${JSON.stringify({ error: errMsg })}\n\n`;
          controller.enqueue(encoder.encode(errorPayload));
        } finally {
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Conversation-Id": conversationId,
      },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
