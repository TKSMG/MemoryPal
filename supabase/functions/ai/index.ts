// MemoryPal "ai" Edge Function: study notes and practice questions with
// Google Gemini, for signed-in people only, with a daily allowance each.
//
// The Gemini key stays here (secret GEMINI_API_KEY); the apps never see it.
// See README.md for deploying it and supabase/migrations/2026-10-18-ai-usage.sql
// for the ai_usage table it counts requests in.
//
// POST /functions/v1/ai   Authorization: Bearer <the person's access token>
//   { "action": "notes" | "questions", "text"?: string,
//     "file"?: { "data": base64, "mime_type": "application/pdf" | "image/png" | ... },
//     "count"?: number, "avoid"?: string[], "title"?: string }
// -> 200 { "ok": true, "action", "result": Notes | { "questions": Question[] }, "remaining": number }
// -> 4xx/5xx { "ok": false, "error": code, "message": text }

import { AiError, cleanNotes, cleanQuestions, ERRORS, geminiBody, modelJson, parseRequest, providerError } from "./logic.ts";

const env = (name: string, fallback = "") => Deno.env.get(name) ?? fallback;
const SUPABASE_URL = env("SUPABASE_URL").replace(/\/+$/, "");
const PUBLIC_KEY = env("SUPABASE_ANON_KEY") || env("SUPABASE_PUBLISHABLE_KEY");
const SERVICE_KEY = env("SUPABASE_SERVICE_ROLE_KEY") || env("SUPABASE_SECRET_KEY");
const GEMINI_KEY = env("GEMINI_API_KEY");
const GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash").trim() || "gemini-2.5-flash";
const DAILY_LIMIT = Math.max(1, Math.trunc(Number(env("AI_DAILY_LIMIT", "20"))) || 20);
const GEMINI_TIMEOUT_MS = 100_000;
// The base64 of an 8 MB file plus some text, with room to spare.
const MAX_BODY_BYTES = 12 * 1024 * 1024;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

function failure(error: AiError): Response {
  return reply(ERRORS[error.code] ?? 500, { ok: false, error: error.code, message: error.message });
}

/** The signed-in person behind the access token, checked by Supabase Auth. */
async function caller(request: Request): Promise<string> {
  const token = (request.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!token || token === PUBLIC_KEY) throw new AiError("not_signed_in", "Sign in to use AI notes.");
  const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, { headers: { apikey: PUBLIC_KEY || SERVICE_KEY, Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new AiError("not_signed_in", "Sign in to use AI notes.");
  const user = await response.json().catch(() => ({}));
  if (!user?.id) throw new AiError("not_signed_in", "Sign in to use AI notes.");
  // Same rule as the database: an account with an authenticator app needs the second step.
  const twoStep = (user.factors ?? []).some((factor: { status?: string }) => factor.status === "verified");
  if (twoStep && claims(token).aal !== "aal2") throw new AiError("second_step", "Finish two-step sign-in first.");
  return String(user.id);
}

function claims(token: string): Record<string, unknown> {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(part + "=".repeat((4 - (part.length % 4)) % 4)));
  } catch {
    return {};
  }
}

async function rpc(name: string, args: Record<string, unknown>): Promise<unknown> {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify(args),
  });
  if (!response.ok) throw new AiError("provider_error", "The daily allowance couldn't be checked.");
  return response.json().catch(() => null);
}

async function gemini(body: Record<string, unknown>): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), GEMINI_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(GEMINI_MODEL)}:generateContent`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch {
    throw new AiError("busy", "The AI took too long to answer. Try again.");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    console.error("gemini", response.status, (await response.text().catch(() => "")).slice(0, 500));
    throw providerError(response.status);
  }
  return response.json().catch(() => null);
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (request.method !== "POST") return failure(new AiError("bad_request", "Use POST."));
  let userId = "";
  let charged = false;
  try {
    if (!GEMINI_KEY || !SUPABASE_URL || !SERVICE_KEY) throw new AiError("not_configured", "AI notes aren't set up on this server yet.");
    userId = await caller(request);
    const size = Number(request.headers.get("Content-Length") ?? 0);
    if (size > MAX_BODY_BYTES) throw new AiError("file_too_large", "The file is larger than 8 MB.");
    const raw = await request.text();
    if (raw.length > MAX_BODY_BYTES) throw new AiError("file_too_large", "The file is larger than 8 MB.");
    let body: unknown;
    try {
      body = JSON.parse(raw);
    } catch {
      throw new AiError("bad_request", "Send a JSON object.");
    }
    const input = parseRequest(body);

    const used = await rpc("ai_usage_take", { p_user: userId, p_limit: DAILY_LIMIT });
    if (typeof used !== "number") throw new AiError("limit_reached", `You've used today's ${DAILY_LIMIT} AI requests. Try again tomorrow.`);
    charged = true;

    const answer = modelJson(await gemini(geminiBody(input)));
    const pdf = input.file?.mime_type === "application/pdf";
    const result = input.action === "notes" ? cleanNotes(answer) : { questions: cleanQuestions(answer, input.count, input.avoid, pdf) };
    return reply(200, { ok: true, action: input.action, result, remaining: Math.max(0, DAILY_LIMIT - used) });
  } catch (error) {
    const aiError = error instanceof AiError ? error : new AiError("provider_error", "Something went wrong. Try again later.");
    if (!(error instanceof AiError)) console.error("ai", error);
    // Not the person's fault: give the request back.
    if (charged && (aiError.code === "busy" || aiError.code === "provider_error")) {
      await rpc("ai_usage_refund", { p_user: userId }).catch(() => null);
    }
    return failure(aiError);
  }
});
