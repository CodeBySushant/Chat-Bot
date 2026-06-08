// API response/request types mirroring the FastAPI backend schemas.

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  email_verified_at: string | null;
  created_at: string;
}

export interface MembershipSummary {
  company_id: string;
  company_name: string;
  company_slug: string;
  role_slug: string;
  status: string;
}

export interface MeResponse {
  user: User;
  memberships: MembershipSummary[];
}

export interface Company {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
}

export interface RoleContext {
  company_id: string;
  role_slug: string;
  permissions: string[];
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  full_name: string | null;
  role_slug: string;
  status: string;
}

export interface Chatbot {
  id: string;
  name: string;
  slug: string;
  status: string;
  public_key: string;
  created_at: string;
}

export type ProcessingStatus = "pending" | "processing" | "ready" | "failed";

export interface Document {
  id: string;
  chatbot_id: string;
  title: string | null;
  source_type: string;
  mime_type: string | null;
  file_size: number | null;
  status: ProcessingStatus;
  token_count: number;
  chunk_count: number;
  error: string | null;
  created_at: string;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  page_number: number | null;
  token_count: number;
  char_count: number;
}

export interface CrawlJob {
  id: string;
  chatbot_id: string;
  start_url: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  mode: string;
  pages_discovered: number;
  pages_processed: number;
  pages_failed: number;
  error: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  chatbot_id: string;
  channel: string;
  status: string;
  title: string | null;
  message_count: number;
  started_at: string;
}

export interface SourceRef {
  document_id: string | null;
  chunk_id: string | null;
  chunk_index: number | null;
  title: string | null;
  source_uri: string | null;
  page_number: number | null;
  score: number;
  snippet: string | null;
}

export interface AnswerResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  sources: SourceRef[];
}

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
  citations: SourceRef[];
  created_at: string;
}

export interface Lead {
  id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  status: string;
  score: number;
  source: string | null;
  captured_at: string;
}

export interface ApiError {
  error: { code: string; message: string; details?: unknown };
}
