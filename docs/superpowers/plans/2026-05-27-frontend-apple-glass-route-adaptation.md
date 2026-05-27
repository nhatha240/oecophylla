# Frontend Apple Glass Route Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the real SvelteKit routes onto the Apple Glass visual system while preserving the working auth, feed, profile, post, composer, and admin flows.

**Architecture:** Keep the existing SvelteKit route/load/action structure and replace the presentation layer with Apple Glass shells and page sections. Reuse the existing Apple Glass CSS/components where practical, but do not route real pages through the mock `AppleGlassApp.svelte` state machine.

**Tech Stack:** SvelteKit, Svelte 5, Tailwind, existing Apple Glass Svelte components and CSS modules, Vitest, svelte-check

---

### Task 1: Wire global Apple Glass styling into the real app

**Files:**
- Modify: `frontend/src/app.css`
- Modify: `frontend/src/routes/+layout.svelte`

- [ ] Import the Apple Glass CSS token/style files globally and keep the current auth store wiring intact.
- [ ] Replace the bare layout slot with a real Apple Glass shell entry point that can render authenticated and unauthenticated states.
- [ ] Run `pnpm check` and confirm the layout compiles cleanly.

### Task 2: Replace login/register presentation with Apple Glass auth pages

**Files:**
- Modify: `frontend/src/lib/components/AuthForm.svelte`
- Modify: `frontend/src/routes/login/+page.svelte`
- Modify: `frontend/src/routes/register/+page.svelte`
- Verify: `frontend/src/routes/login/+page.server.ts`
- Verify: `frontend/src/routes/register/+page.server.ts`

- [ ] Rebuild the auth form UI to match the Apple Glass auth screen while keeping plain HTML form submission to the existing server actions.
- [ ] Support both login and register field sets, inline error rendering, and route-to-route switching.
- [ ] Run auth-focused checks and confirm login/register pages still submit to the existing actions.

### Task 3: Convert route pages to Apple Glass sections

**Files:**
- Modify: `frontend/src/routes/+page.svelte`
- Modify: `frontend/src/routes/post/[id]/+page.svelte`
- Modify: `frontend/src/routes/profile/[id]/+page.svelte`
- Modify: `frontend/src/routes/post/new/+page.svelte`
- Modify: `frontend/src/routes/admin/+page.svelte`
- Reuse/verify: `frontend/src/lib/components/*.svelte`

- [ ] Replace the old centered glass cards with Apple Glass page scaffolding and typography.
- [ ] Keep existing data sources and interactions, only adapting component composition and layout.
- [ ] Use mock/admin sections only where the backend does not yet provide real data, without regressing working route behavior.

### Task 4: Verify working flows after visual migration

**Files:**
- Test: `frontend/src/lib/server/cookies.test.ts`
- Test: `frontend/src/lib/api.test.ts`

- [ ] Run `pnpm test`.
- [ ] Run `pnpm check`.
- [ ] Manually review the auth flow assumptions in code and confirm the cookie-forwarding logic still lines up with the new UI submission path.
