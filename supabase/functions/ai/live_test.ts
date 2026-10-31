// deno test supabase/functions/ai/live_test.ts
import { AiError } from "./logic.ts";
import { LIVE_TOKEN_MINUTES, liveInstruction, liveSetup, liveTokenBody, MAX_LIVE_CARDS, parseLiveRequest, tokenFrom } from "./live.ts";

function assertEquals(actual: unknown, expected: unknown) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) throw new Error(`expected ${e}\n     got ${a}`);
}

function code(fn: () => unknown): string {
  try {
    fn();
  } catch (error) {
    if (error instanceof AiError) return error.code;
    throw error;
  }
  return "none";
}

Deno.test("live requests keep only well-formed cards, capped", () => {
  assertEquals(code(() => parseLiveRequest(null)), "bad_request");
  assertEquals(code(() => parseLiveRequest({ action: "live", cards: [] })), "bad_request");
  assertEquals(code(() => parseLiveRequest({ action: "live", cards: [{ key: "x1", front: "Q", back: "A" }] })), "bad_request");
  const request = parseLiveRequest({
    action: "live",
    deck: "  Biology ",
    voice: "Nope",
    cards: [
      { key: "c1", front: " What is a cell? ", back: "The basic unit of life" },
      { key: "c1", front: "Duplicate key", back: "x" },
      { key: "c2", front: "No answer", back: "" },
      { key: "c3", front: "Q3", back: "A3" },
    ],
  });
  assertEquals(request.cards.map((card) => card.key), ["c1", "c3"]);
  assertEquals([request.deck, request.voice, request.cards[0].front], ["Biology", "Kore", "What is a cell?"]);
  const many = Array.from({ length: MAX_LIVE_CARDS + 5 }, (_, i) => ({ key: `c${i}`, front: `Q${i}`, back: `A${i}` }));
  assertEquals(parseLiveRequest({ cards: many }).cards.length, MAX_LIVE_CARDS);
});

Deno.test("the tutor set-up holds the cards fenced, the tools and audio settings", () => {
  const request = parseLiveRequest({ cards: [{ key: "c1", front: "Capital of France?", back: "Paris" }], deck: "Geo", voice: "Puck" });
  const setup = liveSetup(request, "gemini-3.8-live") as {
    model: string;
    generationConfig: { responseModalities: string[]; speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: string } } } };
    tools: { functionDeclarations: { name: string }[] }[];
    inputAudioTranscription: unknown;
  };
  assertEquals(setup.model, "models/gemini-3.8-live");
  assertEquals(liveSetup(request, "models/x").model, "models/x");
  assertEquals(setup.generationConfig.responseModalities, ["AUDIO"]);
  assertEquals(setup.generationConfig.speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName, "Puck");
  assertEquals(setup.tools[0].functionDeclarations.map((tool) => tool.name), ["record_answer", "end_session"]);
  assertEquals(setup.inputAudioTranscription, {});
  const text = liveInstruction(request);
  if (!text.includes('"""\nc1: Q: Capital of France? | A: Paris\n"""')) throw new Error(text);
  if (!text.includes('The study set is "Geo".')) throw new Error(text);
});

Deno.test("the token is one use, short-lived and locked to the set-up", () => {
  const setup = liveSetup(parseLiveRequest({ cards: [{ key: "c1", front: "Q", back: "A" }] }), "gemini-3.8-live");
  const now = new Date("2026-10-30T10:00:00Z");
  const body = liveTokenBody(setup, now) as { uses: number; expireTime: string; newSessionExpireTime: string; liveConnectConstraints: { model: string; config: Record<string, unknown> } };
  assertEquals(body.uses, 1);
  assertEquals(body.newSessionExpireTime, "2026-10-30T10:01:00.000Z");
  assertEquals(Date.parse(body.expireTime) - now.getTime(), LIVE_TOKEN_MINUTES * 60_000);
  assertEquals(body.liveConnectConstraints.model, "models/gemini-3.8-live");
  assertEquals("model" in body.liveConnectConstraints.config, false);
  assertEquals(Object.keys((liveTokenBody(setup, now, false) as { liveConnectConstraints: object }).liveConnectConstraints), ["model"]);
  assertEquals(tokenFrom({ name: " auth_tokens/abc " }), "auth_tokens/abc");
  assertEquals(code(() => tokenFrom({})), "provider_error");
});
