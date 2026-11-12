export interface TemporalRange {
  startDateUtc: string; // ISO-8601 UTC string
  endDateUtc: string;   // ISO-8601 UTC string
  label: string;
  originalText: string;
}

export class TemporalEngine {
  private defaultTimezone: string;

  constructor(defaultTimezone: string = "UTC") {
    this.defaultTimezone = defaultTimezone;
  }

  /**
   * Returns exact UTC day boundaries [00:00:00.000, 23:59:59.999] for a specific local date in a timezone.
   */
  public getDayBoundariesUtc(
    year: number,
    month: number, // 1-12
    day: number,   // 1-31
    timezone: string = this.defaultTimezone
  ): { startUtc: string; endUtc: string } {
    let t = Date.UTC(year, month - 1, day, 0, 0, 0);

    // Iteratively adjust offset to match local timezone
    for (let i = 0; i < 3; i++) {
      const parts = this.getTimezoneParts(new Date(t), timezone);
      const formattedUtc = Date.UTC(
        parts.year,
        parts.month - 1,
        parts.day,
        parts.hour,
        parts.minute,
        parts.second
      );
      const targetUtc = Date.UTC(year, month - 1, day, 0, 0, 0);
      const diff = targetUtc - formattedUtc;
      if (diff === 0) break;
      t += diff;
    }

    const start = new Date(t);
    const end = new Date(t + 86400000 - 1); // +23h 59m 59s 999ms

    return {
      startUtc: start.toISOString(),
      endUtc: end.toISOString(),
    };
  }

  private getTimezoneParts(date: Date, timezone: string) {
    const formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: timezone,
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      weekday: "long",
      hour12: false,
    });

    const parts = formatter.formatToParts(date);
    const getPart = (type: string) => {
      const p = parts.find((pt) => pt.type === type);
      return p ? p.value : "";
    };

    let hour = parseInt(getPart("hour"), 10);
    if (hour === 24) hour = 0; // Fix 24-hour midnight representation in some Intl versions

    return {
      year: parseInt(getPart("year"), 10),
      month: parseInt(getPart("month"), 10),
      day: parseInt(getPart("day"), 10),
      hour,
      minute: parseInt(getPart("minute"), 10),
      second: parseInt(getPart("second"), 10),
      weekday: getPart("weekday"),
    };
  }

  /**
   * Checks if a user prompt contains a temporal reference (e.g. "on Monday", "yesterday", "3 November").
   */
  public hasTemporalReference(query: string): boolean {
    const lower = query.toLowerCase();
    const patterns = [
      /\b(today|yesterday|tomorrow)\b/,
      /\b(last|this|past|on)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/,
      /\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/,
      /\b\d{1,2}(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b/,
      /\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(st|nd|rd|th)?\b/,
      /\b\d{4}-\d{2}-\d{2}\b/,
      /\b(last|past)\s+(week|month)\b/,
      /\b\d+\s+days?\s+ago\b/,
    ];
    return patterns.some((p) => p.test(lower));
  }

  /**
   * Deterministically parses temporal references in user queries into precise UTC ranges.
   */
  public extractTemporalRange(
    query: string,
    referenceDate: Date = new Date(),
    timezone: string = this.defaultTimezone
  ): TemporalRange | null {
    const lower = query.toLowerCase();
    const refParts = this.getTimezoneParts(referenceDate, timezone);

    // 1. Explicit calendar date: "3 November", "3rd November", "November 3", "Nov 3"
    const explicitMonthFirst = /\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(st|nd|rd|th)?\b/i.exec(lower);
    const explicitDayFirst = /\b(\d{1,2})(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b/i.exec(lower);

    if (explicitMonthFirst || explicitDayFirst) {
      let monthStr = "";
      let dayStr = "";
      let matchedText = "";

      if (explicitMonthFirst) {
        monthStr = explicitMonthFirst[1];
        dayStr = explicitMonthFirst[2];
        matchedText = explicitMonthFirst[0];
      } else if (explicitDayFirst) {
        dayStr = explicitDayFirst[1];
        monthStr = explicitDayFirst[3];
        matchedText = explicitDayFirst[0];
      }

      const monthMap: Record<string, number> = {
        january: 1, jan: 1, february: 2, feb: 2, march: 3, mar: 3, april: 4, apr: 4,
        may: 5, june: 6, jun: 6, july: 7, jul: 7, august: 8, aug: 8, september: 9, sep: 9,
        october: 10, oct: 10, november: 11, nov: 11, december: 12, dec: 12,
      };

      const month = monthMap[monthStr.toLowerCase()];
      const day = parseInt(dayStr, 10);
      const year = refParts.year;

      if (month && day >= 1 && day <= 31) {
        const bounds = this.getDayBoundariesUtc(year, month, day, timezone);
        return {
          startDateUtc: bounds.startUtc,
          endDateUtc: bounds.endUtc,
          label: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
          originalText: matchedText,
        };
      }
    }

    // 2. ISO Date: "2026-11-03"
    const isoMatch = /\b(\d{4})-(\d{2})-(\d{2})\b/.exec(lower);
    if (isoMatch) {
      const year = parseInt(isoMatch[1], 10);
      const month = parseInt(isoMatch[2], 10);
      const day = parseInt(isoMatch[3], 10);
      const bounds = this.getDayBoundariesUtc(year, month, day, timezone);
      return {
        startDateUtc: bounds.startUtc,
        endDateUtc: bounds.endUtc,
        label: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
        originalText: isoMatch[0],
      };
    }

    // 3. "Today"
    if (/\btoday\b/.test(lower)) {
      const bounds = this.getDayBoundariesUtc(refParts.year, refParts.month, refParts.day, timezone);
      return {
        startDateUtc: bounds.startUtc,
        endDateUtc: bounds.endUtc,
        label: "Today",
        originalText: "today",
      };
    }

    // 4. "Yesterday"
    if (/\byesterday\b/.test(lower)) {
      // Calculate previous day
      const yesterdayDate = new Date(referenceDate.getTime() - 86400000);
      const yParts = this.getTimezoneParts(yesterdayDate, timezone);
      const bounds = this.getDayBoundariesUtc(yParts.year, yParts.month, yParts.day, timezone);
      return {
        startDateUtc: bounds.startUtc,
        endDateUtc: bounds.endUtc,
        label: "Yesterday",
        originalText: "yesterday",
      };
    }

    // 5. Weekdays (e.g., "on Monday", "last Tuesday", "this Wednesday")
    const weekdayMatch = /\b(?:(on|last|this|past)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i.exec(lower);
    if (weekdayMatch) {
      const modifier = (weekdayMatch[1] || "").toLowerCase();
      const targetDay = weekdayMatch[2].toLowerCase();

      const weekdays = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
      const targetIndex = weekdays.indexOf(targetDay);

      // Current weekday index in target timezone
      const currentWeekdayIndex = weekdays.indexOf(refParts.weekday.toLowerCase());

      let daysBack = (currentWeekdayIndex - targetIndex + 7) % 7;
      if (daysBack === 0) {
        // Same weekday
        if (modifier === "last" || modifier === "past") {
          daysBack = 7;
        }
      } else if (modifier === "last") {
        // "last Tuesday" when today is Thursday -> 2 days ago (or if user means the week before, but usually most recent Tuesday)
        // If current day is after Tuesday, last Tuesday is 2 days ago. If current day is before Tuesday, last Tuesday is (current - target + 7).
        // If explicitly "last <day>", if daysBack < 7 we keep it, or if user explicitly meant previous calendar week:
        // We will target the most recent occurrence of that weekday prior to today.
      }

      // If daysBack is 0 (i.e. today is Monday and user says "on Monday" asking about past shortlist), look back 7 days
      if (daysBack === 0) {
        daysBack = 7;
      }

      const pastTargetDate = new Date(referenceDate.getTime() - daysBack * 86400000);
      const targetParts = this.getTimezoneParts(pastTargetDate, timezone);
      const bounds = this.getDayBoundariesUtc(targetParts.year, targetParts.month, targetParts.day, timezone);

      return {
        startDateUtc: bounds.startUtc,
        endDateUtc: bounds.endUtc,
        label: `${targetDay.charAt(0).toUpperCase() + targetDay.slice(1)} (${targetParts.year}-${String(targetParts.month).padStart(2, "0")}-${String(targetParts.day).padStart(2, "0")})`,
        originalText: weekdayMatch[0],
      };
    }

    return null;
  }
}
