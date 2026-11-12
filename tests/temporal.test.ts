import { describe, it, expect } from "vitest";
import { TemporalEngine } from "@/memory/temporal";

describe("TemporalEngine (Timezone & Date Parsing)", () => {
  it("computes exact UTC day boundaries for UTC timezone", () => {
    const engine = new TemporalEngine("UTC");
    const bounds = engine.getDayBoundariesUtc(2026, 11, 9, "UTC");
    expect(bounds.startUtc).toBe("2026-11-09T00:00:00.000Z");
    expect(bounds.endUtc).toBe("2026-11-09T23:59:59.999Z");
  });

  it("computes exact UTC day boundaries across negative timezone offsets (America/New_York)", () => {
    const engine = new TemporalEngine("America/New_York");
    // In November, New York is in EST (UTC-5)
    const bounds = engine.getDayBoundariesUtc(2026, 11, 9, "America/New_York");
    expect(bounds.startUtc).toBe("2026-11-09T05:00:00.000Z");
    expect(bounds.endUtc).toBe("2026-11-10T04:59:59.999Z");
  });

  it("computes exact UTC day boundaries across positive timezone offsets (Asia/Kolkata)", () => {
    const engine = new TemporalEngine("Asia/Kolkata");
    // Kolkata is UTC+5:30
    const bounds = engine.getDayBoundariesUtc(2026, 11, 9, "Asia/Kolkata");
    expect(bounds.startUtc).toBe("2026-11-08T18:30:00.000Z");
    expect(bounds.endUtc).toBe("2026-11-09T18:29:59.999Z");
  });

  it("resolves explicit calendar date '3 November' (Scenario B)", () => {
    const engine = new TemporalEngine("UTC");
    const ref = new Date("2026-11-12T12:00:00.000Z");
    const range = engine.extractTemporalRange("What did I ask you on 3 November?", ref, "UTC");

    expect(range).not.toBeNull();
    expect(range?.startDateUtc).toBe("2026-11-03T00:00:00.000Z");
    expect(range?.endDateUtc).toBe("2026-11-03T23:59:59.999Z");
    expect(range?.label).toBe("2026-11-03");
  });

  it("resolves relative weekday 'on Monday' (Scenario A)", () => {
    const engine = new TemporalEngine("UTC");
    // Suppose reference date is Thursday Nov 12, 2026
    const ref = new Date("2026-11-12T14:00:00.000Z");
    const query = "On Monday we shortlisted 5 CRM tools for a 20-person sales team. Has any of them changed pricing?";
    const range = engine.extractTemporalRange(query, ref, "UTC");

    expect(range).not.toBeNull();
    // Monday was Nov 9, 2026
    expect(range?.startDateUtc).toBe("2026-11-09T00:00:00.000Z");
    expect(range?.endDateUtc).toBe("2026-11-09T23:59:59.999Z");
    expect(range?.label).toContain("2026-11-09");
  });

  it("resolves relative weekday 'last Tuesday' (Scenario C)", () => {
    const engine = new TemporalEngine("UTC");
    // Reference date: Thursday Nov 12, 2026
    const ref = new Date("2026-11-12T14:00:00.000Z");
    const query = "Last Tuesday I asked you about Postgres hosting. Has any pricing changed since then?";
    const range = engine.extractTemporalRange(query, ref, "UTC");

    expect(range).not.toBeNull();
    // The previous Tuesday was Nov 10, 2026 (2 days prior to Thursday)
    expect(range?.startDateUtc).toBe("2026-11-10T00:00:00.000Z");
    expect(range?.endDateUtc).toBe("2026-11-10T23:59:59.999Z");
    expect(range?.label).toContain("2026-11-10");
  });

  it("resolves 'yesterday' and 'today'", () => {
    const engine = new TemporalEngine("UTC");
    const ref = new Date("2026-11-12T12:00:00.000Z");

    const todayRange = engine.extractTemporalRange("What did we do today?", ref, "UTC");
    expect(todayRange?.startDateUtc).toBe("2026-11-12T00:00:00.000Z");

    const yesterdayRange = engine.extractTemporalRange("What was my question yesterday?", ref, "UTC");
    expect(yesterdayRange?.startDateUtc).toBe("2026-11-11T00:00:00.000Z");
  });

  it("detects temporal references with hasTemporalReference", () => {
    const engine = new TemporalEngine();
    expect(engine.hasTemporalReference("On Monday we shortlisted 5 CRM tools")).toBe(true);
    expect(engine.hasTemporalReference("What did I ask on 3 November?")).toBe(true);
    expect(engine.hasTemporalReference("Last Tuesday I asked about Postgres")).toBe(true);
    expect(engine.hasTemporalReference("What is the capital of France?")).toBe(false);
  });
});
