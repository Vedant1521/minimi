import Database from "better-sqlite3";
import path from "path";
import fs from "fs";
import crypto from "crypto";

export interface ConversationRecord {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  metadata?: string | null;
}

export interface MessageRecord {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp: string; // ISO-8601 UTC string
  timezone: string;
  citations?: string | null; // JSON string
  search_queries?: string | null; // JSON string
  entities?: string | null; // JSON string
}

export interface SearchEvidenceRecord {
  id: string;
  message_id: string;
  query: string;
  url: string;
  title: string;
  snippet: string;
  fetched_at: string;
}

export interface SaveMessageInput {
  id?: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp?: string;
  timezone?: string;
  citations?: Array<{ index: number; title: string; url: string; snippet?: string }>;
  search_queries?: string[];
  entities?: string[];
}

export interface SaveEvidenceInput {
  id?: string;
  message_id: string;
  query: string;
  url: string;
  title: string;
  snippet: string;
  fetched_at?: string;
}

export class MemoryStore {
  private db: Database.Database;

  constructor(dbPath: string = ":memory:") {
    if (dbPath !== ":memory:") {
      const dir = path.dirname(dbPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }

    this.db = new Database(dbPath);
    this.configurePragmas();
    this.initSchema();
  }

  private configurePragmas(): void {
    this.db.pragma("journal_mode = WAL");
    this.db.pragma("foreign_keys = ON");
    this.db.pragma("synchronous = NORMAL");
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT
      );

      CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        timezone TEXT NOT NULL DEFAULT 'UTC',
        citations TEXT,
        search_queries TEXT,
        entities TEXT
      );

      CREATE TABLE IF NOT EXISTS search_evidence (
        id TEXT PRIMARY KEY,
        message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
        query TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        snippet TEXT NOT NULL,
        fetched_at TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
      CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
      CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
      CREATE INDEX IF NOT EXISTS idx_evidence_message ON search_evidence(message_id);

      CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        message_id UNINDEXED,
        content,
        entities,
        tokenize='porter unicode61'
      );

      CREATE TRIGGER IF NOT EXISTS trg_messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(message_id, content, entities)
        VALUES (new.id, new.content, COALESCE(new.entities, ''));
      END;

      CREATE TRIGGER IF NOT EXISTS trg_messages_ad AFTER DELETE ON messages BEGIN
        DELETE FROM messages_fts WHERE message_id = old.id;
      END;

      CREATE TRIGGER IF NOT EXISTS trg_messages_au AFTER UPDATE ON messages BEGIN
        DELETE FROM messages_fts WHERE message_id = old.id;
        INSERT INTO messages_fts(message_id, content, entities)
        VALUES (new.id, new.content, COALESCE(new.entities, ''));
      END;
    `);
  }

  public createConversation(id?: string, title?: string): ConversationRecord {
    const convId = id || crypto.randomUUID();
    const now = new Date().toISOString();
    const convTitle = title || `Conversation ${convId.slice(0, 8)}`;

    const stmt = this.db.prepare(`
      INSERT INTO conversations (id, title, created_at, updated_at)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
      RETURNING *
    `);

    return stmt.get(convId, convTitle, now, now) as ConversationRecord;
  }

  public getConversation(id: string): ConversationRecord | null {
    const stmt = this.db.prepare(`SELECT * FROM conversations WHERE id = ?`);
    const result = stmt.get(id);
    return (result as ConversationRecord) || null;
  }

  public listConversations(limit: number = 50): ConversationRecord[] {
    const stmt = this.db.prepare(`
      SELECT * FROM conversations
      ORDER BY updated_at DESC
      LIMIT ?
    `);
    return stmt.all(limit) as ConversationRecord[];
  }

  public saveMessage(input: SaveMessageInput): MessageRecord {
    // Ensure parent conversation exists
    if (!this.getConversation(input.conversation_id)) {
      this.createConversation(input.conversation_id);
    }

    const id = input.id || crypto.randomUUID();
    const timestamp = input.timestamp || new Date().toISOString();
    const timezone = input.timezone || "UTC";
    const citations = input.citations ? JSON.stringify(input.citations) : null;
    const searchQueries = input.search_queries ? JSON.stringify(input.search_queries) : null;
    const entities = input.entities ? JSON.stringify(input.entities) : null;

    const stmt = this.db.prepare(`
      INSERT INTO messages (
        id, conversation_id, role, content, timestamp, timezone, citations, search_queries, entities
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      RETURNING *
    `);

    // Update conversation updated_at
    this.db.prepare(`UPDATE conversations SET updated_at = ? WHERE id = ?`).run(timestamp, input.conversation_id);

    return stmt.get(
      id,
      input.conversation_id,
      input.role,
      input.content,
      timestamp,
      timezone,
      citations,
      searchQueries,
      entities
    ) as MessageRecord;
  }

  public getMessages(conversationId: string, limit: number = 100): MessageRecord[] {
    const stmt = this.db.prepare(`
      SELECT * FROM messages
      WHERE conversation_id = ?
      ORDER BY timestamp ASC
      LIMIT ?
    `);
    return stmt.all(conversationId, limit) as MessageRecord[];
  }

  public saveSearchEvidence(input: SaveEvidenceInput): SearchEvidenceRecord {
    const id = input.id || crypto.randomUUID();
    const fetchedAt = input.fetched_at || new Date().toISOString();

    const stmt = this.db.prepare(`
      INSERT INTO search_evidence (id, message_id, query, url, title, snippet, fetched_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      RETURNING *
    `);

    return stmt.get(id, input.message_id, input.query, input.url, input.title, input.snippet, fetchedAt) as SearchEvidenceRecord;
  }

  public getSearchEvidenceForMessage(messageId: string): SearchEvidenceRecord[] {
    const stmt = this.db.prepare(`
      SELECT * FROM search_evidence
      WHERE message_id = ?
      ORDER BY fetched_at ASC
    `);
    return stmt.all(messageId) as SearchEvidenceRecord[];
  }

  public findMessagesByDateRange(
    startDateUtc: string,
    endDateUtc: string,
    options?: { role?: string; limit?: number }
  ): MessageRecord[] {
    let sql = `
      SELECT * FROM messages
      WHERE timestamp >= ? AND timestamp <= ?
    `;
    const params: unknown[] = [startDateUtc, endDateUtc];

    if (options?.role) {
      sql += ` AND role = ?`;
      params.push(options.role);
    }

    sql += ` ORDER BY timestamp ASC`;

    if (options?.limit) {
      sql += ` LIMIT ?`;
      params.push(options.limit);
    }

    return this.db.prepare(sql).all(...params) as MessageRecord[];
  }

  public searchMessagesFTS(
    queryText: string,
    options?: { role?: string; limit?: number }
  ): Array<MessageRecord & { conversation_title: string }> {
    // Sanitize query for FTS5 (escape special characters)
    const sanitized = queryText
      .replace(/["*()^]/g, " ")
      .trim()
      .split(/\s+/)
      .filter((w) => w.length > 0)
      .map((w) => `"${w}"*`)
      .join(" OR ");

    if (!sanitized) {
      return [];
    }

    let sql = `
      SELECT m.*, c.title AS conversation_title
      FROM messages_fts fts
      JOIN messages m ON fts.message_id = m.id
      JOIN conversations c ON m.conversation_id = c.id
      WHERE messages_fts MATCH ?
    `;
    const params: unknown[] = [sanitized];

    if (options?.role) {
      sql += ` AND m.role = ?`;
      params.push(options.role);
    }

    sql += ` ORDER BY rank, m.timestamp DESC`;

    if (options?.limit) {
      sql += ` LIMIT ?`;
      params.push(options.limit);
    } else {
      sql += ` LIMIT 20`;
    }

    return this.db.prepare(sql).all(...params) as Array<MessageRecord & { conversation_title: string }>;
  }

  public getRecentUserQuestions(limit: number = 30): Array<MessageRecord & { conversation_title: string }> {
    const stmt = this.db.prepare(`
      SELECT m.*, c.title AS conversation_title
      FROM messages m
      JOIN conversations c ON m.conversation_id = c.id
      WHERE m.role = 'user'
      ORDER BY m.timestamp DESC
      LIMIT ?
    `);
    return stmt.all(limit) as Array<MessageRecord & { conversation_title: string }>;
  }

  public close(): void {
    if (this.db.open) {
      this.db.close();
    }
  }
}
