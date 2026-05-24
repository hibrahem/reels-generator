---
id: AgDR-0002
timestamp: 2026-05-24T18:25:00Z
agent: claude
model: claude-opus-4-7[1m]
trigger: user-prompt
status: executed
---

# Reattach to active jobs via the in-memory registry (defer disk persistence)

> In the context of making active pipeline jobs observable across page refresh and re-navigation (GH-9), facing a choice of how job progress should survive a client losing its in-memory `jobId`, I decided to **reattach to the server's existing in-memory job registry** (consume `GET /jobs?video_id=` + the SSE event-log replay) and **poll `GET /jobs` for a global indicator**, to achieve the feature with zero backend changes, accepting that in-flight job visibility does not survive a **server restart**.

## Context

- The web server already keeps a `JobManager` with every job in memory, keyed by `video_id`, with a `state` (`queued`/`running`/`done`/`failed`) and an event log.
- `GET /jobs?video_id=<id>` and `GET /jobs` already exist; the SSE endpoint `GET /jobs/{id}/events` replays the full event log on connect, then streams live and emits an `end` event.
- Today the only thing lost on refresh is the client-side `jobId` React state — the job itself keeps running server-side.
- Reels Studio is a local-first, single-operator tool; the server is a local process the user starts.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **In-memory reattach + poll** (chosen) | Zero backend change; survives browser refresh + re-navigation while the server runs; simplest; reuses existing SSE replay | Lost on server restart; a polling interval for the global indicator (trivial cost locally) |
| Persist job state to disk / manifest | Survives server restart | Larger change; new persistence format + lifecycle; write contention with per-video manifests; over-built for a single local user |
| WebSocket / server-push global feed | Real-time global updates without polling | New transport + infra; SSE + light polling is more than adequate for one local client |

## Decision

Chosen: **in-memory reattach + poll**, because it delivers the user-visible requirement (see progress after refresh / back-and-forward, and an at-a-glance "work is running" indicator) with no backend change and no new persistence surface, which is the right weight for a local-first single-user tool. Surviving a server restart is explicitly out of scope; revisit with disk persistence only if jobs become long-lived across restarts or the tool goes multi-user/hosted.

## Consequences

- Frontend only: a `listJobs(videoId?)` client, `VideoDetail` reattach-on-mount, a polled header indicator, and a Library "processing" badge.
- No API changes.
- In-flight job visibility is lost if the **server** restarts (documented limitation; acceptable for local-first).
- The global indicator polls `GET /jobs` on an interval while the app is open (~2s); negligible cost on localhost.

## Artifacts

- Ticket: `reels-generator#9`
- Builds on AgDR-0001 (shadcn/ui) for the indicator/badge styling.
- Implementation PR: hibrahem/reels-generator#10
