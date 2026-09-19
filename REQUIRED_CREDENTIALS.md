# Required Credentials

**No secret values appear in this file.** Status describes whether the credential
is reachable by the code that needs it, not whether it merely exists somewhere.
Audit date 2026-09-19.

| Credential | Provider | Required | Status | Action |
|---|---|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` (GitHub Actions) | Supabase → GitHub | YES | **MISSING** | Human must add it under exactly this name (GitHub → Settings → Secrets and variables → Actions → Secrets). The value already exists in Vercel under this exact name. Blocks all ingestion. |
| `SUPABASE_SERVER_ROLE_KEY` (GitHub Actions) | GitHub | NO (legacy alias) | CONFIGURED | Keep for now; workflows fall back to it. Delete after the canonical name is added. |
| `SUPABASE_URL` (GitHub Actions) | Supabase → GitHub | YES | CONFIGURED (2026-09-10T19:12:17Z) | None |
| `SUPABASE_PUBLISHABLE_KEY` (GitHub Actions) | Supabase → GitHub | YES | CONFIGURED (2026-09-10T19:11:43Z) | None |
| `SUPABASE_ANON_KEY` (GitHub Actions) | Supabase → GitHub | NO (public-boundary probe only) | MISSING | Optional; add to enable the RLS/public probe in CI |
| `SUPABASE_ACCESS_TOKEN` (GitHub Actions) | Supabase management | YES (schema inspection + migrations) | CONFIGURED (2026-09-07T15:55:21Z) | None |
| `SUPABASE_DB_URL` (GitHub Actions) | Supabase Postgres DSN | YES (backups via `pg_dump`) | CONFIGURED (2026-09-07T20:50:22Z) | None |
| `VERCEL_TOKEN` (GitHub Actions) | Vercel | YES (handoff/promote/verify) | CONFIGURED (2026-09-06T16:37:45Z) | None |
| Vercel CLI session (local) | Vercel | YES to deploy from this machine | **BLOCKED — LOGGED OUT** | Human must run `vercel login`, or set a local `VERCEL_TOKEN`. Without it no deployment can be made or inspected from here. |
| `NEXT_PUBLIC_SUPABASE_URL` (Vercel) | Supabase → Vercel | YES | CONFIGURED | None |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` (Vercel) | Supabase → Vercel | YES | CONFIGURED | None |
| `SUPABASE_URL` (Vercel, server) | Supabase → Vercel | YES | CONFIGURED | None |
| `SUPABASE_SERVICE_ROLE_KEY` (Vercel, server) | Supabase → Vercel | YES | CONFIGURED | None |
| `SUPABASE_SECRET_KEY` (Vercel, server) | Supabase → Vercel | NO | CONFIGURED but unused | Optional cleanup |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (Vercel) | Supabase → Vercel | NO | CONFIGURED but unused | Optional cleanup |
| `SUPABASE_JWT_SECRET` (Vercel) | Supabase → Vercel | NO (legacy) | CONFIGURED but unused | Optional cleanup |
| `WAITLIST_CONTACT_EMAIL` | Vercel `landing/vercel.json`, GitHub workflow env | YES (signup collection is disabled without it) | CONFIGURED | None. Public by design. |
| `ENABLE_PRODUCTION_INGESTION` (repository **variable**) | GitHub | YES to enable cron | **MISSING** | Human sets it to `true` **only after** a green bounded production smoke run |
| `KV_REST_API_URL`, `KV_REST_API_TOKEN`, `REDIS_URL` | Upstash/KV | NO on `main` | CONFIGURED but unused | Leave; roadmap items |
| `OPENAI_API_KEY` | OpenAI | NO — feature not on `main` | MISSING (not needed) | Only if unmerged PR #1 is adopted |
| `EXA_API_KEY`, `FIRECRAWL_API_KEY` | Exa / Firecrawl | NO | MISSING (not needed) | Research only |
| GitHub PAT in local `git remote` URL | GitHub | — | **PRESENT IN PLAINTEXT — ROTATE** | Human must rotate the token and move it to a credential helper. Never commit or paste the URL form. |

## BLOCKED — REQUIRES MANUAL CREDENTIAL PROVISIONING

1. **Vercel local authentication.** `vercel whoami` → "Logged out", and no
   `VERCEL_TOKEN` exists in this environment's variables. Deployment and
   live-project inspection from this machine are impossible without it. This
   audit did **not** invent or reuse a credential to work around it.
2. **GitHub secret write access.** The available token can read secret *names*
   and dispatch workflows, but cannot read values (by design) and the project's
   own docs record HTTP 403 on secret management for the agent token. The
   `SUPABASE_SERVICE_ROLE_KEY` value therefore cannot be copied by an agent from
   Vercel to GitHub; a human must do it.
3. **Supabase live database inspection.** No `SUPABASE_ACCESS_TOKEN`,
   `SUPABASE_DB_URL` or service-role value is available locally. The Supabase CLI
   is not installed. All database statements in this audit are sourced from the
   2026-09-10 workflow annotation, not from a fresh query.
4. **Production HTTP verification.** The production alias is unreachable from
   this sandbox at TCP level (see `PROJECT_STATE_AUDIT.md`). A human or a GitHub
   runner must re-run the smoke to confirm current status.

## What was deliberately NOT done

- No credentials were invented, generated, guessed or fabricated.
- No auth or payment system was bypassed.
- No secret was printed into a log, a document, a commit or a chat message.
- No secret was committed; `.env.example` files contain names and blanks only.