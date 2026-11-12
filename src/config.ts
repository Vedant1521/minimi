import path from "path";

export interface MinimiConfig {
  openaiApiKey?: string;
  openaiBaseUrl?: string;
  tavilyApiKey?: string;
  model: string;
  dbPath: string;
  timezone: string;
  port: number;
}

export function loadConfig(): MinimiConfig {
  return {
    openaiApiKey: process.env.OPENAI_API_KEY,
    openaiBaseUrl: process.env.OPENAI_BASE_URL,
    tavilyApiKey: process.env.TVLY_API_KEY,
    model: process.env.MINIMI_MODEL || "gpt-4o-mini",
    dbPath: process.env.MINIMI_DB_PATH || path.resolve(process.cwd(), "data", "minimi.db"),
    timezone: process.env.MINIMI_TIMEZONE || "UTC",
    port: parseInt(process.env.PORT || "3000", 10),
  };
}

export const config = loadConfig();
