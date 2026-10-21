// deno test supabase/functions/ai/logic_test.ts
import { AiError, base64Bytes, cleanNotes, cleanQuestions, ERRORS, geminiBody, limitsFrom, MAX_FILE_BYTES, modelJson, parseRequest, promptFor, providerError, secondsToNextMinute, takeResult } from "./logic.ts";

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

Deno.test("requests are checked and clamped", () => {
  assertEquals(code(() => parseRequest(null)), "bad_request");
  assertEquals(code(() => parseRequest({ action: "hack", text: "x" })), "bad_request");
  assertEquals(code(() => parseRequest({ action: "notes" })), "bad_request");
  assertEquals(code(() => parseRequest({ action: "notes", file: { data: "AAAA", mime_type: "application/zip" } })), "unsupported_file");
  assertEquals(code(() => parseRequest({ action: "notes", file: { data: "not base64!", mime_type: "image/png" } })), "bad_request");
  const big = "A".repeat(Math.ceil((MAX_FILE_BYTES + 10) / 3) * 4);
  assertEquals(code(() => parseRequest({ action: "notes", file: { data: big, mime_type: "application/pdf" } })), "file_too_large");
  const ok = parseRequest({ action: "questions", text: " notes ", count: 500, avoid: ["a", 3, "", "b"], file: { data: "data:image/png;base64,AAAA", mime_type: "IMAGE/PNG" } });
  assertEquals([ok.text, ok.count, ok.avoid, ok.file], ["notes", 30, ["a", "b"], { data: "AAAA", mime_type: "image/png" }]);
  assertEquals(parseRequest({ action: "questions", text: "x", count: "nope" }).count, 10);
  assertEquals(base64Bytes("AAAA"), 3);
  assertEquals(base64Bytes("AA=="), 1);
});

Deno.test("the Gemini body uses JSON mode, a schema, safety settings and the file", () => {
  const body = geminiBody(parseRequest({ action: "questions", text: "Cells", count: 5, avoid: ["What is a cell?"], file: { data: "AAAA", mime_type: "application/pdf" } })) as {
    generationConfig: { responseMimeType: string; responseSchema: { required: string[] } };
    safetySettings: unknown[];
    contents: { parts: { text?: string }[] }[];
  };
  assertEquals(body.generationConfig.responseMimeType, "application/json");
  assertEquals(body.generationConfig.responseSchema.required, ["questions"]);
  assertEquals(body.safetySettings.length, 4);
  assertEquals(body.contents[0].parts[0], { inlineData: { mimeType: "application/pdf", data: "AAAA" } });
  const prompt = body.contents[0].parts[1].text ?? "";
  if (!prompt.includes("What is a cell?") || !prompt.includes('"page"')) throw new Error(prompt);
});

Deno.test("the learner's style is clipped and fenced into the prompt", () => {
  const request = parseRequest({ action: "notes", text: "Dates", style: "  one line per date:   year, then event " + "x".repeat(600) });
  assertEquals(request.style.length, 500);
  assertEquals(request.style.startsWith("one line per date: year, then event"), true);
  const prompt = promptFor(request);
  assertEquals(prompt.includes('The learner described how they want this'), true);
  assertEquals(prompt.indexOf("Material:") < prompt.indexOf("The learner described"), true);
  assertEquals(promptFor(parseRequest({ action: "questions", text: "x" })).includes("The learner described"), false);
  assertEquals(promptFor(parseRequest({ action: "questions", text: "x" })).includes('"context"'), true);
});

Deno.test("model answers are read, and blocks are reported", () => {
  const answer = { candidates: [{ finishReason: "STOP", content: { parts: [{ text: '{"title":"T",' }, { text: '"sections":[],"key_terms":[]}' }] } }] };
  assertEquals(modelJson(answer), { title: "T", sections: [], key_terms: [] });
  assertEquals(code(() => modelJson({ promptFeedback: { blockReason: "SAFETY" } })), "blocked");
  assertEquals(code(() => modelJson({ candidates: [{ finishReason: "SAFETY" }] })), "blocked");
  assertEquals(code(() => modelJson({ candidates: [{ content: { parts: [{ text: "not json" }] } }] })), "provider_error");
  assertEquals(code(() => modelJson({})), "provider_error");
  assertEquals(providerError(429).code, "busy");
  assertEquals(providerError(500).code, "provider_error");
});

Deno.test("notes are clamped and stripped", () => {
  const notes = cleanNotes({ title: "  Cells  ", sections: [{ heading: "Parts", bullets: ["Nucleus", "", 5, "x".repeat(400)] }, { heading: "", bullets: [] }, "junk"], key_terms: [{ term: "Cell", definition: "Unit of life" }, { term: "No definition" }], extra: "dropped" });
  assertEquals(notes.title, "Cells");
  assertEquals(notes.sections.length, 1);
  assertEquals(notes.sections[0].bullets.length, 2);
  assertEquals(notes.sections[0].bullets[1].length, 300);
  assertEquals(notes.key_terms, [{ term: "Cell", definition: "Unit of life" }]);
  assertEquals(cleanNotes("nonsense").title, "Study notes");
});

Deno.test("questions keep only well-formed ones", () => {
  const raw = {
    questions: [
      { type: "short", question: "What is a cell?", answer: "Unit of life" },
      { type: "short", question: "What is a nucleus?", answer: "Control centre", page: 3, context: "  The nucleus is the   control centre. " },
      { type: "choice", question: "Powerhouse?", answer: "Mitochondria", options: ["Mitochondria", "Nucleus", "Ribosome", "Golgi"] },
      { type: "choice", question: "Too few options?", answer: "A", options: ["A", "B"] },
      { type: "truefalse", question: "Cells have walls", answer: "false." },
      { type: "truefalse", question: "Maybe?", answer: "sometimes" },
      { type: "cloze", question: "The nucleus holds DNA", answer: "DNA" },
      { type: "cloze", question: "No blank here", answer: "missing" },
      { type: "essay", question: "Write an essay", answer: "No" },
      { type: "short", question: "What is a nucleus?", answer: "duplicate" },
    ],
  };
  const out = cleanQuestions(raw, 30, ["what is a CELL?"], true);
  assertEquals(out.map((q) => q.type), ["short", "choice", "truefalse", "cloze"]);
  assertEquals(out[0].page, 3);
  assertEquals(out[0].context, "The nucleus is the control centre.");
  assertEquals(out[1].context, "");
  assertEquals(out[1].options, ["Mitochondria", "Nucleus", "Ribosome", "Golgi"]);
  assertEquals(out[2].answer, "False");
  assertEquals(out[3].question, "The nucleus holds _____");
  assertEquals(cleanQuestions(raw, 2).length, 2);
  assertEquals(cleanQuestions(raw, 30, [], false)[1].page, null);
});

Deno.test("rate limits come from the secrets, with safe defaults", () => {
  const env = (values: Record<string, string>) => (name: string) => values[name];
  assertEquals(limitsFrom(env({})), { daily: 10, perMinute: 3, totalDaily: 450, totalPerMinute: 14 });
  assertEquals(limitsFrom(env({ AI_DAILY_LIMIT: "0", AI_PER_MINUTE: "0", AI_TOTAL_DAILY_LIMIT: "-5", AI_TOTAL_PER_MINUTE: "nope" })), { daily: 1, perMinute: 0, totalDaily: 0, totalPerMinute: 14 });
  assertEquals(limitsFrom(env({ AI_DAILY_LIMIT: " 25 ", AI_TOTAL_DAILY_LIMIT: "1400.7" })).daily, 25);
  assertEquals(limitsFrom(env({ AI_TOTAL_DAILY_LIMIT: "1400.7" })).totalDaily, 1400);
  assertEquals(secondsToNextMinute(new Date("2026-10-20T10:00:45Z")), 15);
});

Deno.test("each limit maps to an error the apps understand", () => {
  const limits = limitsFrom(() => undefined);
  assertEquals(takeResult({ used: 4 }, limits), 4);
  const refused = (answer: unknown) => code(() => takeResult(answer, limits));
  assertEquals(refused({ refused: "daily" }), "limit_reached");
  assertEquals(refused(null), "limit_reached");
  assertEquals(refused({ refused: "minute" }), "busy");
  assertEquals(refused({ refused: "total_minute" }), "busy");
  assertEquals(refused({ refused: "total_daily" }), "busy_today");
  assertEquals([ERRORS.busy, ERRORS.busy_today, ERRORS.limit_reached], [503, 503, 429]);
});
