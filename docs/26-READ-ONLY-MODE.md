# 26 — Read-only mode (`LINKEDIN_READ_ONLY`)

**Status: offline-proven, test-held. Not yet live-tested.**
Every *behavioural* claim about the gate (§§1–7) maps to a row of the evidence table in §9 and is
covered by an offline test (`mcp/tests/test_readonly.py`, run with a faked transport — no network,
no cookie file, no browser). Three things in this document are explicitly **not** test-held and say
so where they appear: the environment pin described in §8 (proven by running the suite, not by a
test case), the `fastmcp` version note in §9, and all of §10, which describes a live call that was
never made. There is no live session in this repo, so nothing here is marked ✅ *verified* in the
sense of `STATUS-MATRIX.md`: no real LinkedIn call was made to confirm it. What is proven is the
gate's behaviour at the MCP boundary.

---

## 1. What it is

`LINKEDIN_READ_ONLY` puts the MCP server (`mcp/server.py`) into **read-only mode**: every
**writing** tool is blocked outright, every **reading** tool keeps working. There is exactly one
declared exception, and it makes no network call: the preview branch of `delete_comment(dry_run=True)`
(§6). It is allowed by an explicit whitelist, not by the parameter name.

This is the right default for unattended operation — a cron job or an agent that only *watches*
LinkedIn (e.g. scanning the inbox for job offers) should not be able to post, message, react or
delete, not even through a prompt accident. The flag removes the capability instead of trusting
the prompt.

Read-only is **independent of, and additional to, the `confirm=True` gates** (`MCP-DESIGN.md` §5).
It does not replace them and does not change them: with the flag unset, every tool behaves exactly
as before (regression-tested, `mcp/tests/test_readonly.py:308`, `:336`).

## 2. The split: what is blocked, what is not

Blocking is per tool, declared in the tool layer (`mcp/server.py`) with the `@write_tool`
decorator (`mcp/server.py:59`). A registry test asserts the **complete** split, so a future tool
must be classified explicitly or the suite fails (`mcp/tests/test_readonly.py:352`).

| | Tools | Under `LINKEDIN_READ_ONLY` |
|---|---|---|
| **Reads (10)** | `get_me`, `get_my_posts`, `get_conversations`, `get_profile`, `get_notifications`, `get_connections_summary`, `get_post_comments`, `get_link_preview`, `session_status`, `refresh_session` | allowed, unchanged |
| **Writes (19)** | `create_comment`, `delete_comment`, `like`, `unlike`, `follow_company`, `connect`, `endorse_skill`, `remove_connection`, `save_post`, `repost`, `delete_repost`, `create_post`, `edit_post`, `create_poll`, `delete_post`, `send_dm`, `recall_message`, `react_to_message`, `react_to_comment` | **blocked — raises** |

`refresh_session` counts as a **read**: it starts nothing and launches nothing, it only re-probes
`/me` (`mcp/lib/client.py:61-70`).

**One write never sends its mutating call, even with the flag off (since 2026-07-31):**
`delete_repost` is **not operational** — its `queryId` has no `.<hash>` — and refuses up front
instead of sending a doomed request (`mcp/lib/client.py:776`, `BACKLOG.md`). It stays classified as
a write, stays `confirm`-gated and stays blocked under `LINKEDIN_READ_ONLY`; the split above is
unchanged.

**Mind the layer — "sends nothing" and "sends no write" are not the same claim here:**

- *Call layer.* `LinkedInClient.delete_repost()` sends **nothing at all**: zero `get`, zero `post`,
  zero `delete` against the faked transport (`mcp/tests/test_client.py:544`).
- *Tool layer.* `server.delete_repost()` still emits the session probe first — a **GET** on `/me`
  from `li.ensure_session()` (`mcp/server.py:298`) — and only then does the client method refuse.
  So at the boundary this document is about, the honest statement is *"no **mutating** call leaves
  the process"*, **not** *"nothing leaves the process"*.

Only the *proof* differs from the other eighteen writes: for this one tool the flag-off test
asserts `not _mutating(transport)` instead of requiring a mutating call to have arrived
(`NOT_OPERATIONAL`, `mcp/tests/test_readonly.py:332`; assert `:343`). The suite keeps those two
predicates apart on purpose — `_sent` (`:110`) versus `_mutating` (`:114-117`: *"A GET is NOT proof
of a write"*). When the hash is captured, that set has to be emptied in the same change.

Twelve of the nineteen writes are additionally `confirm`-gated; seven are not (`like`, `unlike`,
`follow_company`, `endorse_skill`, `save_post`, `create_poll`, `react_to_message`) and fire a real
write on the first call. For those seven, this flag is the only pre-emptive brake — which is why
the block is tested with `confirm=True` supplied everywhere a confirm gate exists
(`mcp/tests/test_readonly.py:42-67`): otherwise the test would only re-test the confirm gate.

## 3. Flag semantics — the flag only ever switches writes OFF

`read_only_enabled()` (`mcp/server.py:41`) is deliberately asymmetric:

| Value of `LINKEDIN_READ_ONLY` | Mode |
|---|---|
| unset, empty, whitespace-only | **off** (writes allowed) |
| `0`, `false` (any case) | **off** (writes allowed) |
| `1`, `true`, `yes`, `on` (any case) | **on** (writes blocked) |
| anything else — `2`, `ja`, `maybe`, `off`, `no`, `disabled`, `-1`, … | **on** (writes blocked) **+ warning** |

Only `0` and `false` hand write access back. Everything else — including values that *look* like
a switch-off, such as `off` or `no` — keeps the safe direction, so a typo can never grant write
access by accident (`mcp/tests/test_readonly.py:184`, `:191`, `:199`, `:205`).

An unrecognised value prints one warning per distinct value to **stderr** and stays ON
(`mcp/tests/test_readonly.py:217`, `:228`). It must never go to stdout: stdout *is* the stdio MCP
transport, and one stray line there corrupts the protocol.

The value is read from `os.environ` on **every call**, never cached at import time
(`mcp/tests/test_readonly.py:210`), so a long-running server picks up a change and a test can
switch the mode.

## 4. Failure behaviour: loud, never a silent success

A blocked call **raises** `fastmcp.exceptions.ToolError` (`mcp/server.py:85`). It deliberately
does not return a dict (`mcp/tests/test_readonly.py:151`):

- `{"ok": False, …}` is exactly what a *failed real call* looks like (`mcp/lib/client.py:344-350`)
  — a caller would read it as "try again".
- `{"ok": True, …}` would be worse than no gate at all: a gate that fakes success.

The message states three things, each asserted by a test
(`mcp/tests/test_readonly.py:120-123`): **what** is blocked (the tool name), **which** variable
releases it (`LINKEDIN_READ_ONLY`), and that the block is **intentional** and not a transient
failure, so an agent does not retry.

Both call paths are tested: the module-level function (what a direct importer sees) and
`mcp.call_tool` — the boundary an agent really goes through (`mcp/tests/test_readonly.py:128`,
`:137`). They are the same object only because `@mcp.tool` sits above `@write_tool`; flipping the
decorator order would register the *ungated* function, and the boundary test is what catches that.

Both of those two tests replace the transport (fake `vgreq` module **plus** `lib.client.requests`)
and assert **zero** outgoing calls for each of the nineteen writes — the constraint is enforced and
measured, not read off the source. The same transport fixture (`mcp/tests/test_readonly.py:85-105`)
is used by every test in the file, but not every test asserts an empty call log: the read-tool and
flag-unset tests deliberately expect calls to arrive, and use the recorder to check *which* verb
was sent.

## 5. Seeing the mode without attempting a write

`session_status()` carries `read_only: true|false` (`mcp/server.py:199`,
test `mcp/tests/test_readonly.py:176`). An agent should check that instead of probing the mode
with a write.

**There is no startup confirmation line.** "Read-only is active" is therefore not distinguishable
from "the variable never reached the process" by observing the server itself — only by calling
`session_status()`. Practical consequence: put the flag into the **`env` block of the MCP client
configuration** (where it belongs to the server process), not only into an interactive shell
profile, and confirm it once via `session_status()`.

## 6. `dry_run` under read-only

Read-only permits exactly one class of exception: paths that are **explicitly audited as
network-free**. This is an opt-in whitelist per tool (`network_free_param`, `mcp/server.py:59`),
never a check on a parameter *name* — a tool that merely happens to have a `dry_run` argument
stays blocked (`mcp/tests/test_readonly.py:272`), and a whitelist that names a non-existent
parameter blocks rather than opens (`mcp/tests/test_readonly.py:287`).

At the MCP boundary exactly one tool declares it today: `delete_comment(dry_run=True)`
(`mcp/server.py:163`). It returns the planned request without touching the network
(`mcp/lib/client.py:337-341` returns before the only outgoing call at `:342`).

Under read-only its result additionally carries **`read_only: true`**
(`mcp/tests/test_readonly.py:242`, `:250`), so the caller cannot conclude that a later
`dry_run=False` would go through. Without the flag the return value is unchanged — no
`read_only` key is added (`mcp/tests/test_readonly.py:300`).

The whitelist resolves the argument through the real signature, so it also holds for positional
calls and in combination with `force` (`mcp/tests/test_readonly.py:261`).

## 7. The honest limit — what this does NOT protect

**Read-only is an operating mode of the MCP server, not a library guarantee.**

The gate sits on the `@mcp.tool` functions in `mcp/server.py`. That is the layer the docs call the
guardrail layer (`mcp/server.py:1-12` vs. the pure call layer `mcp/lib/client.py:1-10`;
`MCP-DESIGN.md` §5), and it is the layer an MCP client can reach. It does **not** cover:

- **direct use of `LinkedInClient`** — `tools/*.py`, `mcp/tests/*`, or any script that imports
  `lib.client` and calls a write method. Those bypass `server.py` entirely and the flag has no
  effect on them.
- **anything outside this process** — the session daemon, capture tooling, a browser session.

So the claim is precisely: *with `LINKEDIN_READ_ONLY` set, no writing MCP tool of this server
performs a write.* It is not: *"with the flag set nothing in this repo can write to LinkedIn."*
A protection claim that reaches further than the protection would be the worst kind of defect in
this repo.

`mcp/lib/client.py` is unchanged by *this* feature — the `delete_repost` guard added on 2026-07-31
is a separate change and no read-only gate: it refuses whatever the flag says. A second assertion right before the outgoing
calls was considered and deliberately not built: it would live in the call layer, and its message
could not name the tool that was blocked. The zero-outgoing-call proof comes from the transport
monkeypatch in the tests instead.

## 8. Usage

```bash
# read-only server (recommended default for cron / unattended agents)
LINKEDIN_READ_ONLY=1 .venv/bin/python mcp/server.py

# writes allowed again — only these two values do that
LINKEDIN_READ_ONLY=0 .venv/bin/python mcp/server.py
unset LINKEDIN_READ_ONLY
```

In an MCP client configuration (stdio server), as part of the server's `env` block:

```json
{ "command": "python", "args": ["mcp/server.py"], "env": { "LINKEDIN_READ_ONLY": "1" } }
```

**Note for running the test suite:** exporting the variable is safe. `mcp/tests/conftest.py`
holds an autouse fixture that removes `LINKEDIN_READ_ONLY` from `os.environ` for every test in
`mcp/tests` and restores the previous value afterwards, so an exported value does not decide
whether the suite is green; tests that need the mode set it themselves per test via `monkeypatch`.
The same pin is repeated in the standalone runner `mcp/tests/test_server.py` `main()`, which
pytest's `conftest.py` does not reach.

## 9. Test evidence

Run: `./.venv/bin/python -m pytest mcp/tests tests -q`

| What is proven | Test |
|---|---|
| all 19 write tools blocked, zero outgoing calls (module level) | `mcp/tests/test_readonly.py:128` |
| all 19 write tools blocked at the `mcp.call_tool` boundary | `:137` |
| a blocked write never returns a dict (no fake failure, no fake success) | `:151` |
| all 10 read tools unaffected, and each really is a read (no mutating verb) | `:166` |
| `session_status()` exposes the mode | `:176` |
| flag semantics on / only-looks-like-off / off / unset | `:184`, `:191`, `:199`, `:205` |
| read per call, not cached at import | `:210` |
| unrecognised value warns on stderr only, once, and stays ON | `:217`, `:228` |
| `delete_comment(dry_run=True)` allowed, marked `read_only`, no network | `:242`, `:250`, `:261` |
| whitelist does not trust a parameter name; a typo fails safe | `:272`, `:287` |
| flag unset → confirm gates and dry_run behave exactly as before | `:300`, `:308` |
| flag unset → every write tool still reaches the transport with a mutating verb — except the not-operational `delete_repost`, which must send **no mutating** call and fail with `status: "not_configured"` | `:336` (`NOT_OPERATIONAL` branch `:342-347`) |
| the client method behind that one tool sends nothing at all (zero get/post/delete) | `mcp/tests/test_client.py:544` |
| the read/write split is complete: a new tool cannot stay unclassified | `:352` |
| tool registration + confirm guardrails (pre-existing, tightened to an exact set) | `mcp/tests/test_server.py:27` |

Environment pin (not a test case but part of the evidence): `mcp/tests/conftest.py:18-26` removes
`LINKEDIN_READ_ONLY` per test, so the suite result no longer depends on the ambient shell. Proven
by running the suite twice, with the variable exported and unset — both green. Running with
`--noconftest` and the variable exported turns it red, which shows the pin is load-bearing rather
than decorative.

The exact `fastmcp` version this was verified against is **3.4.5**
(`requirements.txt:4` only requires `>=2.0`; `from fastmcp.exceptions import ToolError` was
checked against the installed venv, not against every version in that range).

## 10. Decision sheet for Manuel — the one call that would prove it live

Not run, and not runnable here: there is no session (`/tmp/li_cookies.json` absent).

- **What would prove it:** with `LINKEDIN_READ_ONLY=1` and a live session, call `session_status()`
  (expect `read_only: true`, `logged_in: true`) and then one *reversible* write, e.g.
  `like(<own post urn>)` — expect the `ToolError`, and the post's reaction count unchanged.
  Then `LINKEDIN_READ_ONLY=0`, repeat `like`, expect 201, and `unlike` to revert.
- **What it costs:** one like + one unlike on the owner's own post.
- **What can go wrong:** the like stays visible for a moment on the owner's own content; nothing
  people-facing, nothing irreversible. If the flag were broken *off*, the second step's write
  would have happened in step one — visible in the reaction count, revertible with `unlike`.
