# AI notes and questions (Supabase Edge Function `ai`)

This function turns a person's notes, a PDF or a photo of a page into study notes or practice
questions with Google Gemini. The apps call it at `<project URL>/functions/v1/ai` with the
person's sign-in token. The Gemini key is kept as a secret on the server and is never put in
the apps.

- Only signed-in people can use it. Accounts with two-step sign-in must have finished the
  second step, the same rule the database uses.
- Each person gets a daily allowance (default 10 requests a day, counted in UTC) and at most
  3 requests a minute. A request that fails because Gemini is busy or broken is not counted
  against the daily allowance.
- Everyone together gets at most 450 requests a day (reset at midnight Pacific time, like
  Gemini's own quota) and 14 a minute, just under the free tier's limits for the whole key.
  When that runs out, people see "paused until tomorrow" instead of Gemini errors.
- Accepted files: PDF, PNG, JPEG, WEBP and HEIC, up to 8 MB.
- Gemini answers in JSON that has to match a schema, and the function checks and trims the
  answer again before passing it on.

## 1. Run the migration

Open the Supabase dashboard, go to **SQL Editor**, paste
[`supabase/migrations/2026-10-18-ai-usage.sql`](../../migrations/2026-10-18-ai-usage.sql)
and run it. Then do the same with
[`supabase/migrations/2026-10-20-ai-rate-limits.sql`](../../migrations/2026-10-20-ai-rate-limits.sql).
You can run both again safely. They create:

- `ai_usage`, one row per person per day, and `ai_usage_total`, one row per day for everyone,
  with Row Level Security on and no policies, so the apps can't read or change them.
- `ai_usage_take_limited()` and `ai_usage_refund()`, which only the function (service role)
  can call. The older `ai_usage_take()` stays; the function falls back to it (daily allowance
  only) if the second migration hasn't been run.

New projects get the same SQL from `supabase/schema.sql`.

## 2. Get a Gemini API key (free)

1. Go to <https://aistudio.google.com>, sign in, and choose **Get API key**, then **Create API
   key**.
2. Copy the key. Treat it like a password and never commit it.

## 3. Deploy the function

**With the CLI** (from the repository root):

```sh
supabase login
supabase link --project-ref <your-project-ref>
supabase secrets set GEMINI_API_KEY=<your key>
# optional:
supabase secrets set GEMINI_MODEL=gemini-3.5-flash-lite AI_DAILY_LIMIT=10
supabase functions deploy ai
```

**With the dashboard:**

1. Go to **Edge Functions**, choose **Deploy a new function**, then **Via Editor**, and name it
   `ai`.
2. Paste the contents of `index.ts`. Add a second file named `logic.ts` and paste that file's
   contents into it. Then deploy.
3. Go to **Edge Functions → Secrets** (or **Project Settings → Edge Functions**) and add
   `GEMINI_API_KEY`. You can also add `GEMINI_MODEL` and `AI_DAILY_LIMIT` there.

Supabase provides `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` to the
function automatically. If the project uses only the newer API keys, add
`SUPABASE_PUBLISHABLE_KEY` and `SUPABASE_SECRET_KEY` as secrets.

The function checks the caller's token itself. If the gateway's own JWT check turns down
valid sign-ins (this can happen with the newer signing keys), redeploy with
`supabase functions deploy ai --no-verify-jwt`. The function still refuses anyone who isn't
signed in.

### Settings

| Secret | Default | What it does |
| --- | --- | --- |
| `GEMINI_API_KEY` | (required) | Key from aistudio.google.com |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | The Gemini model ID. Flash-Lite is the default because its free tier allows about 500 requests a day for the whole key (the Flash models allow about 20). Check current limits in AI Studio under Rate limits, and exact IDs on <https://ai.google.dev/gemini-api/docs/models> |
| `AI_DAILY_LIMIT` | `10` | Requests per person per day. The free tier's daily allowance is shared by everyone, so keep this well below it |
| `AI_PER_MINUTE` | `3` | Requests per person per minute. `0` turns it off |
| `AI_TOTAL_DAILY_LIMIT` | `450` | Requests for everyone together per day (Pacific time). Keep it a little under the model's daily limit in AI Studio; raise it when you move to the paid tier. `0` turns it off |
| `AI_TOTAL_PER_MINUTE` | `14` | Requests for everyone together per minute, under the free tier's 15. `0` turns it off |

To see today's use, run `select * from ai_usage_total order by day desc limit 7;` in the SQL
editor.

## 4. Check it works

Run the tests with `deno test supabase/functions/ai/logic_test.ts`. After deploying, sign in
to the app and make notes from a short paragraph. In the dashboard, open **Edge Functions → ai
→ Logs** to see the requests.

## What the apps receive

Every reply is JSON. A successful reply looks like
`{ "ok": true, "action": "notes" | "questions", "result": ..., "remaining": <requests left today> }`.

- `notes` returns `{ title, sections: [{ heading, bullets[] }], key_terms: [{ term, definition }] }`.
- `questions` returns `{ questions: [{ type: "short" | "choice" | "truefalse" | "cloze", question, answer, options[], page }] }`.
  `page` is the PDF page the question came from, or `null` when there isn't one.

A failed reply looks like `{ "ok": false, "error": <code>, "message": <text> }`. The codes are:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `not_signed_in` | 401 | No valid sign-in |
| `second_step` | 401 | Two-step sign-in not finished |
| `limit_reached` | 429 | The person has used today's allowance |
| `file_too_large` | 413 | The file is over 8 MB |
| `unsupported_file` | 415 | The file isn't a PDF, PNG, JPEG, WEBP or HEIC |
| `bad_request` | 400 | No text or file was sent, or the request is malformed |
| `blocked` | 422 | Gemini's safety filters refused the material |
| `busy` | 503 | Gemini returned HTTP 429 (free-tier quota) or took too long, or a per-minute limit was hit. Has a `Retry-After` header |
| `busy_today` | 503 | Everyone together has used today's `AI_TOTAL_DAILY_LIMIT` |
| `provider_error` | 502 | Gemini or the database returned an error |
| `not_configured` | 500 | `GEMINI_API_KEY` or the Supabase settings are missing |

## Privacy: read this before turning it on

On Gemini's **free tier**, Google may use the content people send (their notes, PDFs and
photos) and the answers to improve its products, and human reviewers may read it. Because of
that:

- The app's AI consent screen must say so plainly before someone uses the feature for the
  first time.
- `PRIVACY_POLICY.md` must name Google (Gemini API) as a processor of the content people send
  to AI features, and say that on the free tier Google may use it to improve its products.

Moving the Google Cloud project behind the API key to the **paid tier** (turning on billing)
stops Google from using the content this way, and needs no code change. If you switch, update
the consent screen and privacy policy to match.
