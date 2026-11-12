import { describe, it, expect } from "vitest";
import { POST } from "@/app/api/chat/route";
import { NextRequest } from "next/server";

describe("Streaming API (/api/chat SSE)", () => {
  it("returns 400 when message is empty", async () => {
    const req = new NextRequest("http://localhost:3000/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: "   " }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error).toBeDefined();
  });

  it("streams SSE response with event frames", async () => {
    const req = new NextRequest("http://localhost:3000/api/chat", {
      method: "POST",
      body: JSON.stringify({
        conversationId: "stream-test-conv",
        message: "Hello world!",
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toContain("text/event-stream");
    expect(res.headers.get("X-Conversation-Id")).toBe("stream-test-conv");

    const reader = res.body?.getReader();
    expect(reader).toBeDefined();

    const decoder = new TextDecoder();
    let accumulated = "";

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        accumulated += decoder.decode(value, { stream: true });
      }
    }

    expect(accumulated).toContain("event: status");
    expect(accumulated).toContain("event: token");
    expect(accumulated).toContain("event: done");
  });
});
