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
as before (regression-tested, `mcp/tests/test_readonly.py::test_without_the_flag_confirm_gates_behave_exactly_as_before`
and `::test_without_the_flag_writes_reach_the_transport`).

**Two independent locks (since 2026-07-31).** Since the confirm gate was extended to the last seven
writes (§2), the two brakes cover different situations and neither replaces the other: the flag
protects **unattended** operation (cron, agent — the switch is on and no human is watching), the
`confirm` gate protects the **interactive** case (the switch is deliberately off, and a misfire must
still not go through on the first call). Their order is fixed and tested: **read-only answers
first** (§2, last paragraph).

## 2. The split: what is blocked, what is not

Blocking is per tool, declared in the tool layer (`mcp/server.py`) with the `@write_tool`
decorator (`mcp/server.py:59`). A registry test asserts the **complete** split, so a future tool
must be classified explicitly or the suite fails
(`mcp/tests/test_readonly.py::test_tool_registry_splits_into_reads_and_gated_writes`).

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
  zero `delete` against the faked transport
  (`mcp/tests/test_client.py::test_delete_repost_sends_nothing_while_the_query_id_hash_is_missing`).
- *Tool layer.* `server.delete_repost()` still emits the session probe first — a **GET** on `/me`
  from `li.ensure_session()` (`mcp/server.py:312`) — and only then does the client method refuse.
  So at the boundary this document is about, the honest statement is *"no **mutating** call leaves
  the process"*, **not** *"nothing leaves the process"*.

Only the *proof* differs from the other eighteen writes: for this one tool the flag-off test
asserts `not _mutating(transport)` instead of requiring a mutating call to have arrived (the
`NOT_OPERATIONAL` set and its branch in
`mcp/tests/test_readonly.py::test_without_the_flag_writes_reach_the_transport`). The suite keeps two
predicates apart on purpose — the helpers `_sent` versus `_mutating` (*"A GET is NOT proof of a
write"*) in the same file. When the hash is captured, that set has to be emptied in the same change.

### All nineteen writes are `confirm`-gated (changed 2026-07-31)

**Every** write tool now takes `confirm: bool = False` and, without it, returns
`{"needs_confirmation": True, …}` before touching the session or the transport. Until this change
twelve of the nineteen carried that gate and seven did not — `like`, `unlike`, `follow_company`,
`endorse_skill`, `save_post`, `create_poll`, `react_to_message` fired a real write on the *first*
call, so for them the flag was the only pre-emptive brake. That is no longer the case; the sentence
"for those seven this flag is the only brake" is obsolete.

What the tests hold (`mcp/tests/test_readonly.py`, offline, faked transport):

- Every tool the registry classifies as a write has a `confirm` parameter **defaulting to `False`** —
  a property over the registry, not a hand-kept list
  (`::test_every_write_tool_has_a_confirm_gate_defaulting_to_false`).
- For the seven newly gated tools, calling without `confirm` returns `needs_confirmation` and issues
  **zero** outgoing calls — counted on the recorded call log, so a gate placed *after*
  `li.ensure_session()` would fail the test — both directly and through `mcp.call_tool`
  (`::test_new_confirm_gates_block_and_send_nothing`,
  `::test_new_confirm_gates_hold_at_the_mcp_boundary`).
- The confirmation payload names **only** the identifying arguments and nothing else (whitelist, not
  a blacklist), and carries no cookie value, no file path, no server internals
  (same block plus `::test_new_confirm_gates_never_leak_cookies_or_paths`).
- For the toggles the payload names the **direction** — `follow=True|False`, `save=True|False`,
  `unlike` marked `action: "unlike"` — so confirming cannot fire the opposite of what was shown.
  `react_to_message` is the honest exception: it is a server-side toggle, and offline it is not
  knowable whether confirming *adds* or *removes* the reaction (`BACKLOG.md`).

**Order is the security statement, and it is tested per tool:** the `@write_tool` gate sits
*outside* and answers **first**. Under `LINKEDIN_READ_ONLY` a call **with** `confirm=True` still
raises `ToolError` and sends nothing — confirming does not buy a write
(`::test_read_only_wins_over_confirm`, asserted on the counted call log for every write, not on the
return value). The mirror case — read-only on, `confirm` **omitted** — must also raise instead of
returning a harmless-looking `needs_confirmation` dict
(`::test_read_only_wins_even_without_confirm`).

Because of that order the read-only proof itself needs `confirm=True` in its call table
(`WRITE_KWARGS`), or it would stop at the confirm gate and prove nothing about the flag. A test now
guards that table entry by entry, so the older proof cannot be weakened silently
(`::test_every_write_tool_is_called_with_confirm_true`).

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
access by accident (`mcp/tests/test_readonly.py::test_flag_values_that_mean_on`,
`::test_values_that_only_look_like_off_still_mean_on`, `::test_flag_values_that_mean_off`,
`::test_flag_unset_means_off`).

An unrecognised value prints one warning per distinct value to **stderr** and stays ON
(`::test_unrecognised_value_warns_on_stderr`,
`::test_warning_is_deduped_but_the_mode_stays_on`). It must never go to stdout: stdout *is* the stdio MCP
transport, and one stray line there corrupts the protocol.

The value is read from `os.environ` on **every call**, never cached at import time
(`mcp/tests/test_readonly.py::test_flag_is_read_per_call_not_cached_at_import`), so a long-running server picks up a change and a test can
switch the mode.

## 4. Failure behaviour: loud, never a silent success

A blocked call **raises** `fastmcp.exceptions.ToolError` (`mcp/server.py:85`). It deliberately
does not return a dict (`mcp/tests/test_readonly.py::test_blocked_write_never_returns_a_dict`):

- `{"ok": False, …}` is exactly what a *failed real call* looks like (`mcp/lib/client.py:344-350`)
  — a caller would read it as "try again".
- `{"ok": True, …}` would be worse than no gate at all: a gate that fakes success.

The message states three things, each asserted by the shared helper `_assert_block_message`
(`mcp/tests/test_readonly.py`): **what** is blocked (the tool name), **which** variable
releases it (`LINKEDIN_READ_ONLY`), and that the block is **intentional** and not a transient
failure, so an agent does not retry.

Both call paths are tested: the module-level function (what a direct importer sees) and
`mcp.call_tool` — the boundary an agent really goes through
(`mcp/tests/test_readonly.py::test_every_write_tool_is_blocked_and_sends_nothing`,
`::test_every_write_tool_is_blocked_at_the_mcp_boundary`). They are the same object only because
`@mcp.tool` sits above `@write_tool`; flipping the
decorator order would register the *ungated* function, and the boundary test is what catches that.

Both of those two tests replace the transport (fake `vgreq` module **plus** `lib.client.requests`)
and assert **zero** outgoing calls for each of the nineteen writes — the constraint is enforced and
measured, not read off the source. The same `transport` fixture (`mcp/tests/test_readonly.py`)
is used by every test in the file, but not every test asserts an empty call log: the read-tool and
flag-unset tests deliberately expect calls to arrive, and use the recorder to check *which* verb
was sent.

## 5. Seeing the mode without attempting a write

`session_status()` carries `read_only: true|false` (`mcp/server.py:199`,
test `mcp/tests/test_readonly.py::test_session_status_exposes_the_mode`). An agent should check that instead of probing the mode
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
stays blocked (`mcp/tests/test_readonly.py::test_gate_does_not_trust_a_dry_run_parameter_name`), and
a whitelist that names a non-existent parameter blocks rather than opens
(`::test_whitelist_naming_a_missing_parameter_fails_safe`).

At the MCP boundary exactly one tool declares it today: `delete_comment(dry_run=True)`
(`mcp/server.py:163`). It returns the planned request without touching the network
(`mcp/lib/client.py:337-341` returns before the only outgoing call at `:342`).

Under read-only its result additionally carries **`read_only: true`**
(`mcp/tests/test_readonly.py::test_dry_run_delete_comment_is_allowed_and_marked`,
`::test_dry_run_is_allowed_at_the_mcp_boundary`), so the caller cannot conclude that a later
`dry_run=False` would go through. Without the flag the return value is unchanged — no
`read_only` key is added (`::test_dry_run_delete_comment_unchanged_without_the_flag`).

The whitelist resolves the argument through the real signature, so it also holds for positional
calls and in combination with `force`
(`::test_dry_run_whitelist_also_holds_for_positional_and_force`).

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

Tests are named, not line-numbered: a line number in this table went stale the moment the test file
grew (see `BACKLOG.md`, citation rot). All rows below live in `mcp/tests/test_readonly.py` unless
stated otherwise.

| What is proven | Test |
|---|---|
| all 19 write tools blocked, zero outgoing calls (module level) | `::test_every_write_tool_is_blocked_and_sends_nothing` |
| all 19 write tools blocked at the `mcp.call_tool` boundary | `::test_every_write_tool_is_blocked_at_the_mcp_boundary` |
| a blocked write never returns a dict (no fake failure, no fake success) | `::test_blocked_write_never_returns_a_dict` |
| all 10 read tools unaffected, and each really is a read (no mutating verb) | `::test_read_tools_are_not_blocked_under_read_only` |
| `session_status()` exposes the mode | `::test_session_status_exposes_the_mode` |
| flag semantics on / only-looks-like-off / off / unset | `::test_flag_values_that_mean_on`, `::test_values_that_only_look_like_off_still_mean_on`, `::test_flag_values_that_mean_off`, `::test_flag_unset_means_off` |
| read per call, not cached at import | `::test_flag_is_read_per_call_not_cached_at_import` |
| unrecognised value warns on stderr only, once, and stays ON | `::test_unrecognised_value_warns_on_stderr`, `::test_warning_is_deduped_but_the_mode_stays_on` |
| `delete_comment(dry_run=True)` allowed, marked `read_only`, no network | `::test_dry_run_delete_comment_is_allowed_and_marked`, `::test_dry_run_is_allowed_at_the_mcp_boundary`, `::test_dry_run_whitelist_also_holds_for_positional_and_force` |
| whitelist does not trust a parameter name; a typo fails safe | `::test_gate_does_not_trust_a_dry_run_parameter_name`, `::test_whitelist_naming_a_missing_parameter_fails_safe` |
| flag unset → confirm gates and dry_run behave exactly as before | `::test_dry_run_delete_comment_unchanged_without_the_flag`, `::test_without_the_flag_confirm_gates_behave_exactly_as_before` |
| flag unset → every write tool still reaches the transport with a mutating verb — except the not-operational `delete_repost`, which must send **no mutating** call and fail with `status: "not_configured"` | `::test_without_the_flag_writes_reach_the_transport` (`NOT_OPERATIONAL` branch) |
| the client method behind that one tool sends nothing at all (zero get/post/delete) | `mcp/tests/test_client.py::test_delete_repost_sends_nothing_while_the_query_id_hash_is_missing` |
| the read/write split is complete: a new tool cannot stay unclassified | `::test_tool_registry_splits_into_reads_and_gated_writes` |
| **every** write tool has `confirm`, defaulting to `False` (property over the registry) | `::test_every_write_tool_has_a_confirm_gate_defaulting_to_false` |
| the seven newly gated tools return `needs_confirmation`, echo their identifying arguments **and only those**, and send zero calls — directly and at the boundary | `::test_new_confirm_gates_block_and_send_nothing`, `::test_new_confirm_gates_hold_at_the_mcp_boundary` |
| no confirmation payload contains a cookie value, a cookie path or a server internal | `::test_new_confirm_gates_never_leak_cookies_or_paths` |
| **order:** under read-only, `confirm=True` still raises and sends nothing (per write tool, counted) | `::test_read_only_wins_over_confirm` |
| **order:** under read-only, `confirm` omitted raises too — never a `needs_confirmation` dict | `::test_read_only_wins_even_without_confirm` |
| the read-only proof cannot be weakened silently: every `WRITE_KWARGS` entry must carry `confirm=True` | `::test_every_write_tool_is_called_with_confirm_true` |
| tool registration + confirm guardrails (pre-existing, tightened to an exact set) | `mcp/tests/test_server.py` |

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
  `like(<own post urn>, confirm=True)` — expect the `ToolError`, and the post's reaction count
  unchanged. `confirm=True` is what makes this the interesting call: it proves the order, not just
  the confirm prompt. Then `LINKEDIN_READ_ONLY=0`, repeat `like(…, confirm=True)`, expect 201, and
  `unlike(…, confirm=True)` to revert. Since 2026-07-31 both need `confirm=True`; without it the
  flag-off call only returns `needs_confirmation` and proves nothing about the live write.
- **What it costs:** one like + one unlike on the owner's own post.
- **What can go wrong:** the like stays visible for a moment on the owner's own content; nothing
  people-facing, nothing irreversible. If the flag were broken *off*, the second step's write
  would have happened in step one — visible in the reaction count, revertible with `unlike`.
