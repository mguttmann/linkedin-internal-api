"""test_client.py — canonical offline tests for LinkedInClient write bodies.

Mocks vgreq (NO network) and asserts the exact request shapes for the verified write endpoints.
Run:  .venv/bin/python tests/test_client.py   (exit 0 = green)

Covers the network-body logic that test_server.py can't: like/unlike endpoint + payload +
honest error handling. Live behaviour is proven separately (like → 201, unlike → 500 browserless).
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_URN = "urn:li:activity:1111111111111111111"
_AID = "1111111111111111111"


class _Resp:
    def __init__(self, code):
        self.status_code, self.text = code, ""

    def json(self):
        return {}


def _client(post_code=201):
    """A LinkedInClient wired to a fake vgreq that records calls and returns post_code."""
    calls = {"post": [], "delete": [], "get": []}
    fake = types.ModuleType("vgreq")
    fake.post = lambda url, body=None, *a, **k: (calls["post"].append((url, body)) or _Resp(post_code))
    fake.delete = lambda url, *a, **k: (calls["delete"].append(url) or _Resp(post_code))
    fake.get = lambda url, *a, **k: (calls["get"].append(url) or _Resp(200))
    sys.modules["vgreq"] = fake
    import importlib
    import lib.client as cl
    importlib.reload(cl)
    return cl.LinkedInClient(), calls


def test_like_hits_voyager_reactions_with_like_body():
    li, calls = _client(201)
    res = li.like(_URN)
    url, body = calls["post"][-1]
    assert "voyagerSocialDashReactions" in url
    assert "urn%3Ali%3Aactivity" in url, "urn must be url-encoded"
    assert body == {"reactionType": "LIKE"}
    assert res["ok"] is True and res["status"] == 201


def test_unlike_posts_sdui_template_browserless(monkeypatch):
    # unlike replays the captured SDUI template (full body) with minimal headers via requests.post —
    # NOT vgreq. Assert: right SDUI url, activity id substituted into the template, minimal headers.
    import lib.client as cl
    sent = {}

    class _R:
        status_code = 200
        text = ""
        headers = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        sent["url"] = url
        sent["body"] = data.decode() if isinstance(data, (bytes, bytearray)) else data
        sent["headers"] = headers or {}
        return _R()

    monkeypatch.setattr(cl.requests, "post", fake_post)
    monkeypatch.setattr(cl.LinkedInClient, "_sdui_min_headers",
                        staticmethod(lambda: {"csrf-token": "ajax:x", "Cookie": "k=v",
                                              "Content-Type": "application/json"}))
    res = cl.LinkedInClient().unlike(_URN)
    assert "sduiid=com.linkedin.sdui.reactions.delete" in sent["url"]
    assert _AID in sent["body"], "activity id must be substituted into the template body"
    assert "{{ACTIVITY_ID}}" not in sent["body"], "placeholder must be filled"
    assert "csrf-token" in sent["headers"] and "accept" not in sent["headers"], \
        "must use minimal SDUI headers (no voyager accept header)"
    assert res["ok"] is True and res["via"] == "sdui-browserless" and "note" not in res


def test_unlike_is_honest_on_error(monkeypatch):
    import lib.client as cl

    class _R:
        status_code = 500
        text = ""
        headers = {}

    monkeypatch.setattr(cl.requests, "post", lambda *a, **k: _R())
    monkeypatch.setattr(cl.LinkedInClient, "_sdui_min_headers",
                        staticmethod(lambda: {"csrf-token": "ajax:x", "Cookie": "k=v"}))
    res = cl.LinkedInClient().unlike(_URN)
    assert res["ok"] is False and res["status"] == 500
    assert "template may have rotated" in res.get("note", ""), "must explain the fallback"


def test_react_to_comment_posts_sdui_template_browserless(monkeypatch):
    # react_to_comment replays the reactions.create template with BOTH ids filled (comment id +
    # post activity id) via requests.post with minimal headers — same browserless SDUI pattern.
    import lib.client as cl
    sent = {}

    class _R:
        status_code = 200
        text = ""
        headers = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        sent["url"] = url
        sent["body"] = data.decode() if isinstance(data, (bytes, bytearray)) else data
        return _R()

    monkeypatch.setattr(cl.requests, "post", fake_post)
    monkeypatch.setattr(cl.LinkedInClient, "_sdui_min_headers",
                        staticmethod(lambda: {"csrf-token": "ajax:x", "Cookie": "k=v",
                                              "Content-Type": "application/json"}))
    res = cl.LinkedInClient().react_to_comment("888", _URN)
    assert "sduiid=com.linkedin.sdui.reactions.create" in sent["url"]
    assert "888" in sent["body"] and _AID in sent["body"], "both ids must be substituted"
    assert "{{COMMENT_ID}}" not in sent["body"] and "{{ACTIVITY_ID}}" not in sent["body"]
    assert res["ok"] is True and res["via"] == "sdui-browserless" and res["comment_id"] == "888"


def test_get_my_posts_uses_exact_captured_url_shape():
    # regression guard: the queryId hash + ordered variables + includeWebMetadata must match the
    # live-captured shape (a guessed shape returned non-JSON / broke).
    calls = {"get": []}
    fake = types.ModuleType("vgreq")
    fake.get = lambda url, *a, **k: (calls["get"].append(url) or _Resp(200))
    fake.post = lambda *a, **k: _Resp(200)
    fake.delete = lambda *a, **k: _Resp(200)
    sys.modules["vgreq"] = fake
    import importlib
    import lib.client as cl
    importlib.reload(cl)
    cl.LinkedInClient().get_my_posts(7)
    url = calls["get"][-1]
    assert "queryId=voyagerFeedDashProfileUpdates.20c70fe0314184158516a7ec004c0408" in url
    assert "includeWebMetadata=true" in url
    assert "count:7" in url and "start:0" in url
    assert "profileUrn:urn%3Ali%3Afsd_profile" in url, "profileUrn must be url-encoded"


def _client_with_response(resp_json, code=200, text=""):
    """A client whose vgreq.post returns a canned json body + status (for create_post body checks).

    `text` is the RAW body: create_poll scrapes the poll URN out of it with a regex, so a fake
    response without `.text` would make that scrape silently unreachable (vacuous assertions).
    """
    calls = {"post": []}
    fake = types.ModuleType("vgreq")
    raw = text  # not `text = text` in the class body: that reads the class-local, not the arg
    class R:
        status_code = code
        text = raw
        def json(self_): return resp_json
    fake.post = lambda url, body=None, *a, **k: (calls["post"].append((url, body)) or R())
    fake.get = lambda *a, **k: R()
    fake.delete = lambda *a, **k: R()
    sys.modules["vgreq"] = fake
    import importlib
    import lib.client as cl
    importlib.reload(cl)
    return cl.LinkedInClient(), calls


def test_create_post_maps_visibility_enum():
    # PUBLIC → ANYONE, CONNECTIONS* → CONNECTIONS_ONLY (the real enum; "CONNECTIONS" is invalid)
    li, calls = _client_with_response({"data": {}})
    li.create_post("hi", visibility="PUBLIC")
    assert calls["post"][-1][1]["variables"]["post"]["visibilityDataUnion"]["visibilityType"] == "ANYONE"
    li, calls = _client_with_response({"data": {}})
    r = li.create_post("hi", visibility="CONNECTIONS")
    assert calls["post"][-1][1]["variables"]["post"]["visibilityDataUnion"]["visibilityType"] == "CONNECTIONS_ONLY"
    assert r["ok"] is True


def test_create_post_detects_body_validation_error_despite_200():
    # CRITICAL regression: a 200 with data.errors must be ok=False (not a false success).
    err = {"data": {"errors": [{"message": "Invalid input for enum … No value found for 'CONNECTIONS'"}]}}
    li, _ = _client_with_response(err, code=200)
    r = li.create_post("hi", visibility="PUBLIC")
    assert r["ok"] is False, "200 + body errors must be treated as failure"
    assert "Invalid input" in r.get("error", "")


def test_create_post_uses_shares_query_id():
    li, calls = _client_with_response({"data": {}})
    li.create_post("hi")
    url = calls["post"][-1][0]
    assert "queryId=voyagerContentcreationDashShares." in url
    assert "action=execute" in url


def test_follow_company_toggles_following_state():
    li, calls = _client(200)
    li.follow_company("1035", follow=True)
    url, body = calls["post"][-1]
    assert "feed/dash/followingStates/" in url
    assert "fsd_company%3A1035" in url, "company id (1035 = Microsoft, a public example) must be in the url-encoded followingState urn"
    assert body == {"patch": {"$set": {"following": True}}}
    li, calls = _client(200)
    li.follow_company("1035", follow=False)
    assert calls["post"][-1][1] == {"patch": {"$set": {"following": False}}}


def test_send_dm_uses_create_message_with_origin_token():
    li, calls = _client(201)
    conv = "urn:li:msg_conversation:(urn:li:fsd_profile:ME,123)"
    li.send_dm(conv, "hallo")
    url, body = calls["post"][-1]
    assert "action=createMessage" in url
    assert body["message"]["body"]["text"] == "hallo"
    assert body["message"]["conversationUrn"] == conv
    assert body["message"]["originToken"], "must send an idempotency originToken"
    assert body["mailboxUrn"].startswith("urn:li:fsd_profile:")


def test_get_post_comments_url_shape():
    calls = {"get": []}
    fake = types.ModuleType("vgreq")
    fake.get = lambda url, *a, **k: (calls["get"].append(url) or _Resp(200))
    fake.post = lambda *a, **k: _Resp(200)
    fake.delete = lambda *a, **k: _Resp(200)
    sys.modules["vgreq"] = fake
    import importlib
    import lib.client as cl
    importlib.reload(cl)
    cl.LinkedInClient().get_post_comments("urn:li:activity:999")
    url = calls["get"][-1]
    assert "feed/comments?q=comments" in url
    assert "updateId=urn%3Ali%3Aactivity%3A999" in url


def test_delete_comment_dry_run_builds_voyager_rest_delete():
    # The primary path is the classic Voyager REST DELETE (verified live 204), NOT the SDUI
    # comments.deleteComment POST (which 500s browserless — needs currentActor). dry_run must
    # build the exact URL + comment urn without sending anything.
    li, calls = _client(204)
    res = li.delete_comment("7481685874066300928",
                            "urn:li:activity:7469679647589412864", dry_run=True)
    # nothing was sent
    assert calls["delete"] == [] and calls["post"] == []
    assert res["dry_run"] is True and res["method"] == "DELETE"
    # canonical comment urn: activity FIRST, then comment id (the `urn` form, not fs_objectComment)
    assert res["comment_urn"] == \
        "urn:li:comment:(activity:7469679647589412864,7481685874066300928)"
    # url = feed/comments/<url-encoded urn>  (NOT the sdui rsc-action route)
    assert "voyager/api/feed/comments/" in res["url"]
    assert "rsc-action" not in res["url"] and "sduiid" not in res["url"]
    # the urn must be url-encoded into the path segment
    assert "urn%3Ali%3Acomment%3A%28activity%3A7469679647589412864%2C7481685874066300928%29" \
        in res["url"]
    assert res["endpoint"] == "voyager.feed.comments.delete"


def test_delete_comment_sends_delete_to_feed_comments():
    # live path (mocked): must issue an HTTP DELETE to the feed/comments route and report ok on 204.
    li, calls = _client(204)
    res = li.delete_comment("222", "urn:li:activity:111")
    assert len(calls["delete"]) == 1, "must use HTTP DELETE (not POST)"
    url = calls["delete"][-1]
    assert "voyager/api/feed/comments/" in url
    assert "urn%3Ali%3Acomment%3A%28activity%3A111%2C222%29" in url
    assert res["ok"] is True and res["status"] == 204 and res["via"] == "voyager-rest"


def test_delete_comment_accepts_bare_activity_id():
    # a bare numeric activity id (no urn:li:activity: prefix) must still build the right urn.
    li, calls = _client(204)
    res = li.delete_comment("222", "111", dry_run=True)
    assert res["comment_urn"] == "urn:li:comment:(activity:111,222)"


def _client_comments(comments, delete_code=204):
    """Client whose get_post_comments returns the given comment objects (for the delete guard).
    comments: list of {id, author} → shaped into the included[] form the guard reads."""
    calls = {"delete": [], "post": []}
    included = [{"$type": "com.linkedin.voyager.feed.Comment",
                 "urn": f"urn:li:comment:(activity:999,{c['id']})",
                 "commenterProfileId": c["author"]} for c in comments]

    class R:
        def __init__(self, code=200, payload=None):
            self.status_code, self._p = code, payload or {}
        def json(self):
            return self._p

    fake = types.ModuleType("vgreq")
    fake.get = lambda *a, **k: R(200, {"included": included})
    fake.delete = lambda url, *a, **k: (calls["delete"].append(url) or R(delete_code))
    fake.post = lambda *a, **k: R(delete_code)
    sys.modules["vgreq"] = fake
    import importlib
    import lib.client as cl
    importlib.reload(cl)
    return cl.LinkedInClient(), calls, cl


def test_delete_comment_guard_blocks_other_peoples_comments(monkeypatch):
    # SAFETY: deleting a comment authored by someone OTHER than the owner must be refused
    # (no HTTP DELETE issued) unless force=True. Regression guard for a real incident.
    monkeypatch.setenv("LI_OWNER_URN", "urn:li:fsd_profile:OWNER123")
    li, calls, _ = _client_comments([{"id": "555", "author": "STRANGER999"}])
    res = li.delete_comment("555", "urn:li:activity:999")
    assert res["ok"] is False and res["status"] == "blocked" and res["via"] == "guard"
    assert calls["delete"] == [], "guard must NOT issue a DELETE for a stranger's comment"
    assert "force=True" in res["note"]


def test_delete_comment_guard_allows_own_comment(monkeypatch):
    # the owner's own comment deletes normally (guard must not over-block).
    monkeypatch.setenv("LI_OWNER_URN", "urn:li:fsd_profile:OWNER123")
    li, calls, _ = _client_comments([{"id": "555", "author": "OWNER123"}])
    res = li.delete_comment("555", "urn:li:activity:999")
    assert res["ok"] is True and res["status"] == 204 and res["via"] == "voyager-rest"
    assert len(calls["delete"]) == 1


def test_delete_comment_force_bypasses_guard(monkeypatch):
    # force=True deletes a stranger's comment on purpose (opt-in).
    monkeypatch.setenv("LI_OWNER_URN", "urn:li:fsd_profile:OWNER123")
    li, calls, _ = _client_comments([{"id": "555", "author": "STRANGER999"}])
    res = li.delete_comment("555", "urn:li:activity:999", force=True)
    assert res["ok"] is True and res["via"] == "voyager-rest"
    assert len(calls["delete"]) == 1


def test_delete_comment_guard_proceeds_when_author_unknown(monkeypatch):
    # if the comment can't be read (already gone / empty), the delete proceeds (idempotent) —
    # the guard only blocks when it can positively identify a DIFFERENT author.
    monkeypatch.setenv("LI_OWNER_URN", "urn:li:fsd_profile:OWNER123")
    li, calls, _ = _client_comments([])  # no comments returned → author unknown
    res = li.delete_comment("555", "urn:li:activity:999")
    assert res["ok"] is True and res["via"] == "voyager-rest"
    assert len(calls["delete"]) == 1


def test_create_comment_browserless_dry_run_builds_sdui_body():
    # BROWSERLESS comment create via the VERIFIED SDUI createComment route. dry_run must
    # build the request WITHOUT sending, target the flagship-web SDUI endpoint, and carry
    # the TEXT AS A REAL LITERAL in the (raw JSON string) body — plus a freshly-minted token.
    li, calls = _client(200)
    res = li.create_comment_browserless("urn:li:activity:12345", "hallo welt", dry_run=True)
    # 1) nothing was sent
    assert calls["post"] == [], "dry_run must NOT hit the network"
    # 2) route = SDUI createComment
    assert res["via"] == "sdui-browserless"
    assert res["ok"] is None and res["status"] == "dry_run"
    assert "sduiid=com.linkedin.sdui.comments.createComment" in res["url"]
    # 3) body is a RAW JSON STRING with the text as a literal + the activity id filled in
    body = res["body_sent"]
    assert isinstance(body, str), "SDUI body is a raw JSON string (posted with is_json=False)"
    assert "hallo welt" in body, "the comment text must be present as a literal"
    assert "12345" in body, "the activity id must be substituted into the template"
    assert "{{TOKEN}}" not in body and "{{TEXT}}" not in body, "all placeholders must be filled"
    assert "commentBoxText-" in body, "the minted state-key token must be embedded"


def test_mint_comment_token_is_unique_and_decodable():
    # the state-key token is self-minted ({timestamp varint + 16 random bytes}); two mints
    # must differ (random trackingId) and be valid base64url.
    import base64
    import lib.client as cl
    t1 = cl.LinkedInClient._mint_comment_token()
    t2 = cl.LinkedInClient._mint_comment_token()
    assert t1 != t2, "each mint must be unique (random trackingId)"
    raw = base64.urlsafe_b64decode(t1 + "=" * (-len(t1) % 4))
    assert raw[0] == 0x0A, "field1 (timestamp message) tag expected"
    assert b"\x12\x10" in raw, "field2 = 16-byte trackingId length-delimited"


def test_create_comment_browserless_live_send_and_urn_extract():
    # dry_run=False actually posts the raw body to the SDUI route and surfaces via=sdui-browserless.
    li, calls = _client(200)
    res = li.create_comment_browserless("urn:li:activity:777", "text", dry_run=False)
    url, body = calls["post"][-1]
    assert "sduiid=com.linkedin.sdui.comments.createComment" in url
    assert isinstance(body, str) and "text" in body and "777" in body
    assert res["ok"] is True and res["via"] == "sdui-browserless" and res["status"] == 200


def test_create_comment_prefers_browserless_no_browser():
    # the wrapper must try the browserless SDUI route FIRST and, on success, never touch the browser.
    li, calls = _client(200)
    # guard: if it tried the browser, SessionBrowser().start() would blow up in this env
    res = li.create_comment("urn:li:activity:42", "hey")
    url, body = calls["post"][-1]
    assert "sduiid=com.linkedin.sdui.comments.createComment" in url
    assert isinstance(body, str) and "hey" in body
    assert res["ok"] is True and res["via"] == "sdui-browserless"
    assert res["activity_id"] == "42"


def test_save_post_toggles_is_saved_with_literal_id():
    li, calls = _client(200)
    li.save_post("999", save=True)
    url, body = calls["post"][-1]
    assert "sduiid=com.linkedin.sdui.update.saveState" in url
    p = body["serverRequest"]["requestedArguments"]["payload"]
    assert p["isSaved"] is True
    aid = p["saveObjectUrn"]["saveEntityUrnFeedUpdateUrn"]["feedUpdateUrn"] \
            ["updateUrnActivityUrn"]["activityUrn"]["activityId"]
    assert aid == "999"
    li, calls = _client(200)
    li.save_post("999", save=False)
    assert calls["post"][-1][1]["serverRequest"]["requestedArguments"]["payload"]["isSaved"] is False


def test_repost_is_honest_on_500():
    li, _ = _client(500)
    r = li.repost("999")
    assert r["ok"] is False and "re-capture" in r.get("note", "") and "No browser" in r.get("note", "")


def test_send_dm_body_has_tracking_and_dedupe():
    li, calls = _client(200)
    conv = "urn:li:msg_conversation:(urn:li:fsd_profile:ME,1)"
    li.send_dm(conv, "hi")
    url, body = calls["post"][-1]
    assert "action=createMessage" in url
    assert body["message"]["conversationUrn"] == conv
    assert body["message"]["originToken"], "idempotency token required"
    assert body["trackingId"], "trackingId required (else 400)"
    assert body["dedupeByClientGeneratedToken"] is False


def test_recall_message_uses_recall_action():
    li, calls = _client(204)
    m = "urn:li:msg_message:(urn:li:fsd_profile:ME,2)"
    r = li.recall_message(m)
    url, body = calls["post"][-1]
    assert "action=recall" in url and body == {"messageUrn": m}
    assert r["ok"] is True


def test_get_link_preview_url_shape():
    li, calls = _client(200)
    li.get_link_preview("https://example.com/x")
    url = calls["get"][-1]
    assert "UpdateUrlPreview" in url
    assert "variables=(url:https%3A%2F%2Fexample.com%2Fx)" in url


def test_connect_body_shape():
    li, calls = _client(200)
    li.connect("urn:li:fsd_profile:X", note="hi")
    url, body = calls["post"][-1]
    assert "verifyQuotaAndCreateV2" in url
    assert body["invitee"]["inviteeUnion"]["memberProfile"] == "urn:li:fsd_profile:X"
    assert body["customMessage"] == "hi"
    # no note → no customMessage key
    li, calls = _client(200)
    li.connect("urn:li:fsd_profile:Y")
    assert "customMessage" not in calls["post"][-1][1]


def test_endorse_and_remove_connection_shapes():
    li, calls = _client(200)
    li.endorse_skill("other-user", "OTHER_PROFILE_ID", 48)
    url, body = calls["post"][-1]
    assert "endorseSkill" in url
    p = body["serverRequest"]["requestedArguments"]["payload"]
    assert p == {"vanityName": "other-user", "profileId": "OTHER_PROFILE_ID", "skillId": "48"}
    li, calls = _client(200)
    li.remove_connection("other-user", "Other", "U")
    url, body = calls["post"][-1]
    assert "RemoveConnectionVanityName" in url
    assert body["serverRequest"]["requestedArguments"]["payload"]["disconnectVanityName"] == "other-user"


def test_edit_post_shape():
    li, calls = _client(200)
    li.edit_post("2222222222222222222", "3333333333333333333", "new text")
    url, body = calls["post"][-1]
    assert "voyagerContentcreationDashShares.f2afb8a7" in url
    v = body["variables"]
    assert v["entity"]["resourceKey"] == "urn:li:share:3333333333333333333"
    assert "urn:li:activity:2222222222222222222" in v["updateUrn"]
    assert v["entity"]["entity"]["commentary"]["text"] == "new text"


def test_create_poll_and_post_with_poll():
    li, calls = _client(200)
    li.create_poll("Q?", ["A", "B"], duration="ONE_DAY")
    url, body = calls["post"][-1]
    assert "PollsPollSummary" in url
    assert body["variables"]["poll"] == {"question": "Q?", "duration": "ONE_DAY", "options": ["A", "B"]}
    # posting a poll attaches it as URN_REFERENCE media
    li, calls = _client(200)
    li.create_post("vote", poll_urn="urn:li:fsd_pollSummary:99")
    body = calls["post"][-1][1]
    assert body["variables"]["post"]["media"] == {"mediaUrn": "urn:li:fsd_pollSummary:99",
                                                   "category": "URN_REFERENCE"}


# --- false-success guard: HTTP 200 + data.errors must never read as success ----------
# docs/04: a Voyager GraphQL write answers 200 and still carries a ValidationError in the body.
# create_post/edit_post always checked this; create_poll and delete_repost did not.
_GQL_ERR = {"data": {"errors": [{"message": "Invalid input for field 'options'"}]}}
# Placeholder ONLY — the real repost-delete deploy hash is unknown and must never be invented.
_FAKE_REPOST_QID = "voyagerFeedDashReposts.TESTHASH_NOT_A_REAL_HASH"


def test_create_poll_detects_body_validation_error_despite_200():
    # The raw body deliberately ALSO carries a pollSummary URN: the regex scrape would happily
    # pick it up, so `poll_urn not in r` only proves something with this text present.
    err_text = ('{"data":{"errors":[{"message":"Invalid input for field \'options\'"}]},'
                '"included":[{"entityUrn":"urn:li:fsd_pollSummary:7654321"}]}')
    li, _ = _client_with_response(_GQL_ERR, code=200, text=err_text)
    r = li.create_poll("Q?", ["A", "B"])
    assert r["ok"] is False, "200 + body errors must be treated as failure"
    assert "Invalid input" in r.get("error", "")
    assert "poll_urn" not in r, "a failed poll must not hand back a poll urn"


def test_create_poll_returns_the_poll_urn_on_a_clean_200():
    # Counterpart to the guard above: the early return must not make the success path unusable.
    li, _ = _client_with_response(
        {"data": {}}, code=200,
        text='{"included":[{"entityUrn":"urn:li:fsd_pollSummary:7654321"}]}')
    r = li.create_poll("Q?", ["A", "B"])
    assert r["ok"] is True and r["status"] == 200
    assert r["poll_urn"] == "urn:li:fsd_pollSummary:7654321"
    assert "error" not in r


def test_edit_post_detects_body_validation_error_despite_200():
    li, _ = _client_with_response(_GQL_ERR, code=200)
    r = li.edit_post("2222222222222222222", "3333333333333333333", "new text")
    assert r["ok"] is False and "Invalid input" in (r.get("error") or "")


def test_delete_repost_detects_body_validation_error_despite_200(monkeypatch):
    import lib.client as cl
    li, _ = _client_with_response(_GQL_ERR, code=200)
    monkeypatch.setattr(cl.LinkedInClient, "_REPOST_DEL_QID", _FAKE_REPOST_QID)
    r = li.delete_repost("urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:1,2)")
    assert r["ok"] is False, "200 + body errors must be treated as failure"
    assert "Invalid input" in r.get("error", "")


def test_delete_repost_sends_nothing_while_the_query_id_hash_is_missing():
    # The repost-delete deploy hash is in no capture; the tool must fail honestly instead of
    # firing a doomed request. Constraint enforced, not assumed: count the transport calls.
    li, calls = _client(200)
    r = li.delete_repost("urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:1,2)")
    assert calls["post"] == [] and calls["delete"] == [] and calls["get"] == [], \
        "not-configured delete_repost must send ZERO transport calls"
    assert r["ok"] is False and r["status"] == "not_configured"
    assert r["retryable"] is False, "a caller must not read this as 'try again'"
    assert "capture_write_action.py" in r["note"], "the note must name the re-capture tool"


def test_every_graphql_write_checks_data_errors():
    # CLASS guard, not an instance guard: create_poll/delete_repost were the two known misses.
    # Any FUTURE method that POSTs a graphql action=execute mutation and reports an "ok" flag
    # must route through _gql_errors — otherwise the false-success class comes straight back.
    import ast
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "lib" / "client.py"
    tree = ast.parse(src.read_text())
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "LinkedInClient")
    missing = []
    for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
        body = ast.get_source_segment(src.read_text(), fn) or ""
        posts_mutation = "action=execute" in body and ".post(" in body
        reports_ok = '"ok"' in body
        if posts_mutation and reports_ok and "_gql_errors" not in body:
            missing.append(f"{fn.name} (client.py:{fn.lineno})")
    assert not missing, (
        "GraphQL writes reporting ok without a data.errors check (HTTP 200 can carry a "
        f"ValidationError — docs/04): {missing}")


def test_graphql_write_bodies_are_unchanged_by_the_errors_check(monkeypatch):
    # The errors check must not alter WHAT is sent: freeze url + body of the two touched writes.
    import lib.client as cl
    li, calls = _client(200)
    li.create_poll("Q?", ["A", "B"], duration="ONE_DAY")
    url, body = calls["post"][-1]
    assert url == (f"{cl.BASE}/graphql?action=execute&queryId={cl.POLL_QID}")
    assert body == {"variables": {"poll": {"question": "Q?", "duration": "ONE_DAY",
                                           "options": ["A", "B"]}},
                    "queryId": cl.POLL_QID, "includeWebMetadata": True}
    li, calls = _client(200)
    monkeypatch.setattr(cl.LinkedInClient, "_REPOST_DEL_QID", _FAKE_REPOST_QID)
    urn = "urn:li:fsd_repost:urn:li:instantRepost:(urn:li:share:1,2)"
    li.delete_repost(urn)
    url, body = calls["post"][-1]
    assert url == f"{cl.BASE}/graphql?action=execute&queryId={_FAKE_REPOST_QID}"
    assert body == {"variables": {"resourceKey": urn},
                    "queryId": _FAKE_REPOST_QID, "includeWebMetadata": True}


# ── create_post_with_image: browserless single-part image upload ─────────
# Owner-verified live on 2026-07-18 (asset urn D4E22AQGKhtES62GYIw). What is proven HERE is
# offline only: the two request bodies, the false-success check, and that neither the response
# body nor the file path can reach the return value.
_IMG_META = {"data": {"value": {"urn": "urn:li:digitalmediaAsset:D4TESTASSET",
                                "singleUploadUrl": "https://media.example/upload/xyz",
                                "singleUploadHeaders": {"x-li-upload": "1"}}}}


def _image_client(responses, monkeypatch, put_code=201):
    """A client for the image flow: vgreq.post answers the QUEUED (code, json, text) tuples in
    order — the flow makes TWO posts (register, then the Shares mutation) — and requests.put is
    recorded instead of performed. No network, no cookie file.
    """
    calls = {"post": [], "put": []}
    queue = list(responses)

    class R:
        def __init__(self, code, payload, text=""):
            self.status_code, self._payload, self.text = code, payload, text
            self.headers = {}

        def json(self):
            return self._payload

    fake = types.ModuleType("vgreq")

    def _post(url, body=None, *a, **k):
        calls["post"].append((url, body))
        return R(*(queue.pop(0) if queue else (200, {}, "")))

    fake.post = _post
    fake.get = lambda *a, **k: R(200, {}, "")
    fake.delete = lambda *a, **k: R(200, {}, "")
    sys.modules["vgreq"] = fake
    import importlib
    import lib.client as cl
    importlib.reload(cl)

    def _put(url, data=None, headers=None, timeout=None):
        calls["put"].append((url, data, headers or {}))
        return R(put_code, {}, "")

    monkeypatch.setattr(cl.requests, "put", _put)
    return cl.LinkedInClient(), calls


def _image_file(tmp_path):
    """A local file to upload — synthetic bytes, NOT a real image (nothing here decodes it)."""
    path = tmp_path / "cat.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
    return path


def test_upload_image_registers_the_captured_metadata_body_then_puts_the_bytes(tmp_path,
                                                                              monkeypatch):
    path = _image_file(tmp_path)
    li, calls = _image_client([(200, _IMG_META, "")], monkeypatch)
    r = li.upload_image(str(path))
    url, body = calls["post"][-1]
    assert "voyagerVideoDashMediaUploadMetadata?action=upload" in url
    assert body == {"mediaUploadType": "IMAGE_SHARING", "fileSize": 48, "filename": "cat.png"}, \
        "the register body carries the file NAME and size — never the directory"
    put_url, put_data, put_headers = calls["put"][-1]
    assert put_url == "https://media.example/upload/xyz"
    assert put_data == path.read_bytes(), "the raw bytes go to the singleUploadUrl, one PUT"
    assert put_headers["x-li-upload"] == "1" and "Content-Type" in put_headers
    assert r == {"ok": True, "asset_urn": "urn:li:digitalmediaAsset:D4TESTASSET",
                 "kind": "png", "size": 48}


def test_upload_image_sends_nothing_when_the_file_cannot_be_read(tmp_path, monkeypatch):
    # Enforced, not assumed: an unreadable file must cost ZERO transport calls, raise nothing,
    # and the honest error must name the FILE, never the path (it lands in the transcript).
    missing = tmp_path / "no-such-dir" / "cat.png"
    li, calls = _image_client([(200, _IMG_META, "")], monkeypatch)
    r = li.upload_image(str(missing))
    assert calls["post"] == [] and calls["put"] == [], "no call may go out for a missing file"
    assert r["ok"] is False and r["status"] == "unreadable_file"
    assert "cat.png" in r["error"], "the caller must learn WHICH file failed"
    assert str(tmp_path) not in repr(r), "the error must not carry the directory"


def test_upload_image_refuses_bytes_it_has_not_classified(tmp_path, monkeypatch):
    """Pre-flight, not trust: "readable" is not "valid". An empty file and a file that is not an
    image by its own first bytes must both cost ZERO calls — an empty file would otherwise
    register with fileSize=0, PUT nothing and be reported as a success.
    """
    cases = {"empty_file": b"", "unsupported_type": b"[core]\n\trepositoryformatversion = 0\n"}
    for status, payload in cases.items():
        path = tmp_path / f"{status}.png"  # the extension lies on purpose
        path.write_bytes(payload)
        li, calls = _image_client([(200, _IMG_META, "")], monkeypatch)
        r = li.upload_image(str(path))
        assert calls["post"] == [] and calls["put"] == [], f"{status} must send nothing"
        assert r["ok"] is False and r["status"] == status
        assert f"{status}.png" in r["error"] and str(tmp_path) not in repr(r)


def test_upload_image_returns_a_dict_for_a_path_the_os_cannot_parse(tmp_path, monkeypatch):
    # open() raises ValueError (not OSError) on an embedded NUL byte — a raw traceback must never
    # cross the tool boundary (project rule 4).
    li, calls = _image_client([(200, _IMG_META, "")], monkeypatch)
    r = li.upload_image(str(tmp_path / "ca\0t.png"))
    assert r["ok"] is False and r["status"] == "unreadable_file"
    assert calls["post"] == [] and calls["put"] == []
    assert str(tmp_path) not in repr(r)


def test_inspect_image_classifies_by_content_and_never_returns_a_path(tmp_path, monkeypatch):
    """The classifier is content-based: the same bytes stay a PNG under any name, and a renamed
    non-image stays refused. It reads 12 bytes + a stat — no transport is involved at all.
    """
    li, calls = _image_client([], monkeypatch)
    samples = {"png": b"\x89PNG\r\n\x1a\n", "jpeg": b"\xff\xd8\xff\xe0", "gif": b"GIF89a",
               "webp": b"RIFF\x24\x00\x00\x00WEBP"}
    for kind, head in samples.items():
        path = tmp_path / f"shot.{kind}.bin"     # deliberately NOT an image extension
        path.write_bytes(head + b"\x00" * 32)
        probe = li.inspect_image(str(path))
        assert probe == {"ok": True, "name": f"shot.{kind}.bin", "kind": kind,
                         "size": len(head) + 32, "status": "ok"}
    # a trailing slash empties basename(): the answer is a PLACEHOLDER plus the honest status —
    # never the directory segment above it, which on "/Users/<name>/" is the user name itself.
    probe = li.inspect_image(str(tmp_path) + "/")
    assert probe["ok"] is False and probe["status"] == "unreadable_file"
    assert probe["name"] == "(no file name)" and probe["kind"] == "unknown"
    assert os.path.basename(str(tmp_path)) not in repr(probe)
    assert calls["post"] == [] and calls["put"] == [], "classification is local only"


def test_create_post_with_image_stops_at_the_upload_and_makes_no_share_call(tmp_path,
                                                                           monkeypatch):
    missing = tmp_path / "no-such-dir" / "cat.png"
    li, calls = _image_client([(200, _IMG_META, "")], monkeypatch)
    r = li.create_post_with_image("hi", str(missing))
    assert calls["post"] == [] and calls["put"] == []
    assert r["ok"] is False and r["phase"] == "upload"
    assert str(tmp_path) not in repr(r)


def test_create_post_with_image_uses_the_shares_mutation_with_the_image_recipe(tmp_path,
                                                                              monkeypatch):
    path = _image_file(tmp_path)
    li, calls = _image_client([(200, _IMG_META, ""),
                               (200, {"data": {}}, '{"urn":"urn:li:activity:7484249869516365824"}')],
                              monkeypatch)
    r = li.create_post_with_image("hi", str(path), visibility="CONNECTIONS")
    url, body = calls["post"][-1]
    assert "queryId=voyagerContentcreationDashShares." in url and "action=execute" in url
    post = body["variables"]["post"]
    assert post["media"] == {"category": "IMAGE",
                             "mediaUrn": "urn:li:digitalmediaAsset:D4TESTASSET",
                             "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"]}
    assert post["visibilityDataUnion"]["visibilityType"] == "CONNECTIONS_ONLY"
    assert post["commentary"] == {"text": "hi", "attributesV2": []}
    assert r["ok"] is True and r["phase"] == "post"
    assert r["urns"] == ["urn:li:activity:7484249869516365824"]
    assert str(tmp_path) not in repr(r), "the return must not carry the image path"


def test_create_post_with_image_detects_body_validation_error_despite_200(tmp_path, monkeypatch):
    # The false-success class (docs/04): the share answers 200 WITH data.errors.
    path = _image_file(tmp_path)
    li, _ = _image_client([(200, _IMG_META, ""), (200, _GQL_ERR, "")], monkeypatch)
    r = li.create_post_with_image("hi", str(path))
    assert r["ok"] is False, "200 + body errors must be treated as failure"
    assert "Invalid input" in r.get("error", "")
    assert "urns" not in r, "a failed post must not hand back an activity urn"


def test_image_flow_returns_no_response_body_and_no_header(tmp_path, monkeypatch):
    # Only status, endpoint name, length and the client's own classification may come back.
    path = _image_file(tmp_path)
    secret = "SECRET-BODY-CONTENT"
    li, _ = _image_client([(500, {}, secret)], monkeypatch)
    r = li.upload_image(str(path))
    assert r["ok"] is False and r["status"] == 500
    assert secret not in repr(r), "a response body must never reach the return value"
    assert r["endpoint"] == "voyagerVideoDashMediaUploadMetadata?action=upload"
    li, _ = _image_client([(200, {"data": {"value": {}}}, secret)], monkeypatch)
    r = li.upload_image(str(path))
    assert r["ok"] is False and r["body_len"] == len(secret), "length only, never the body"
    assert secret not in repr(r)


# ── jobs reads: get_job / get_job_recommendations ────────────────────────
# The parsing itself is proven in mcp/tests/test_jobs_parse.py against synthetic fixtures; what
# is asserted HERE is the client layer: the exact URL, that unusable input sends NOTHING, and
# that a body which cannot be identified/read never comes back as a success.
_JOB_ID = "1234567890"


def _reading_client(resp_json, code=200, text="", not_json=False):
    """A client whose vgreq.get returns a canned body + status; records every requested URL."""
    calls = {"get": [], "post": [], "delete": []}
    fake = types.ModuleType("vgreq")
    raw = text

    class R:
        status_code = code
        text = raw

        def json(self_):
            if not_json:
                raise ValueError("Expecting value: line 1 column 1 (char 0)")
            return resp_json

    fake.get = lambda url, *a, **k: (calls["get"].append(url) or R())
    fake.post = lambda url, body=None, *a, **k: (calls["post"].append((url, body)) or R())
    fake.delete = lambda url, *a, **k: (calls["delete"].append(url) or R())
    sys.modules["vgreq"] = fake
    import importlib
    import lib.client as cl
    importlib.reload(cl)
    return cl.LinkedInClient(), calls


def _job_fixture():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "job_posting.json"),
              "r", encoding="utf-8") as fh:
        return json.load(fh)


def _feed_fixture():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "jobs_feed.json"),
              "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_get_job_hits_the_legacy_rest_route_with_the_captured_decoration():
    # Manuel's live evidence names /jobs/jobPostings/<id> — NOT voyagerJobsDashJobPostings and
    # NOT /graphql. Both of those exist and are different routes; confusing them is the failure.
    li, calls = _reading_client(_job_fixture())
    li.get_job(_JOB_ID)
    url = calls["get"][-1]
    assert url.startswith("https://www.linkedin.com/voyager/api/jobs/jobPostings/" + _JOB_ID)
    assert ("decorationId=com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65"
            in url)
    assert "graphql" not in url and "JobsDashJobPostings" not in url


def test_get_job_accepts_a_urn_and_a_url_and_asks_for_the_numeric_id():
    for value in ("urn:li:fsd_jobPosting:1234567890",
                  "https://www.linkedin.com/jobs/view/platform-engineer-at-example-1234567890/"):
        li, calls = _reading_client(_job_fixture())
        res = li.get_job(value)
        assert f"/jobPostings/{_JOB_ID}?" in calls["get"][-1]
        assert res["ok"] is True and res["job_id"] == _JOB_ID


def test_get_job_projects_the_fixture_flat():
    li, _ = _reading_client(_job_fixture())
    res = li.get_job(_JOB_ID)
    assert res["ok"] is True and res["status"] == 200
    assert res["url"] == f"https://www.linkedin.com/jobs/view/{_JOB_ID}/"
    assert res["title"] == "Platform Engineer" and res["company"] == "Example Company"
    assert res["reposted"] is False and res["salary_present"] is True
    assert res["description_text"].startswith("We run a small platform team")


def test_get_job_refuses_unusable_input_without_any_call():
    for value in ("", "not a job", "urn:li:activity:1", 0, -3, None):
        li, calls = _reading_client(_job_fixture())
        res = li.get_job(value)
        assert calls["get"] == [] and calls["post"] == [] and calls["delete"] == [], \
            f"{value!r} must not reach the transport"
        assert res["ok"] is False and res["status"] == "invalid_input"
        assert res["error"] and "Traceback" not in res["error"]


def test_get_job_aborts_hard_on_an_id_mismatch_and_returns_no_url():
    # Manuel's explicit instruction: do not correct, do not warn. A url built from the body id
    # would point at a different job than the one that was read.
    li, _ = _reading_client(_job_fixture())
    res = li.get_job("9999999999")
    assert res["ok"] is False and res["identity"] == "mismatch"
    assert res["job_id"] == "9999999999", "the requested id stays the requested id"
    assert res["body_job_id"] == _JOB_ID
    assert "url" not in res, "no url may leave on a mismatch"
    assert "jobs/view" not in json.dumps(res), "the body id must not become a link"
    assert "title" not in res and "description_text" not in res, \
        "no payload of the foreign job may leak into the result"


def test_get_job_reports_a_missing_identifying_witness():
    li, _ = _reading_client({"data": {"title": "Platform Engineer", "applies": 3}})
    res = li.get_job(_JOB_ID)
    assert res["ok"] is False and res["identity"] == "absent"
    assert "url" not in res and "identifying" in res["error"]


def test_get_job_is_honest_on_a_non_200_and_on_a_200_error_envelope():
    li, _ = _reading_client({}, code=404)
    res = li.get_job(_JOB_ID)
    assert res["ok"] is False and res["status"] == 404 and "re-capture" in res["note"]
    li, _ = _reading_client({"status": 403, "message": "Forbidden",
                             "data": {"$type": "com.linkedin.voyager.ErrorResponse"}})
    res = li.get_job(_JOB_ID)
    assert res["ok"] is False and "403" in res["error"], "a 200 with an error body is not a read"


def test_get_job_is_honest_when_the_body_is_not_json():
    li, _ = _reading_client(None, not_json=True)
    res = li.get_job(_JOB_ID)
    assert res["ok"] is False and "not JSON" in res["error"]
    assert "session_status" in res["note"], "the note must name the way out"


def test_get_job_declares_a_clamped_description_budget():
    li, _ = _reading_client(_job_fixture())
    res = li.get_job(_JOB_ID, description_chars=0)
    assert res["ok"] is True and str(20000) in res["note"]


def test_get_job_recommendations_uses_the_captured_feed_query():
    li, calls = _reading_client(_feed_fixture())
    res = li.get_job_recommendations(3)
    url = calls["get"][-1]
    assert "/graphql?includeWebMetadata=true&variables=(count:3,start:0)" in url
    assert "queryId=voyagerJobsDashJobsFeed.8b4a94e0e9d8395f1e7482987dd2f815" in url
    assert res["ok"] is True and res["state"] == "hits" and res["count"] == 3
    assert res["pagination_token"] == "SYNTHETIC_PAGINATION_TOKEN"
    assert res["results"][0]["url"] == "https://www.linkedin.com/jobs/view/1111111111/"


def test_the_requested_count_caps_the_request_and_never_silently_cuts_the_read_cards():
    # HARDENING (tester), corrected to the measured chain: `count:<n>` caps the MODULES LinkedIn
    # returns, and one module carries several cards, so cutting the CARD list to `n` locally would
    # drop understood jobs that cursor paging can never bring back. The cap therefore lives in the
    # REQUEST (asserted above), not in the result list — and if anything ever does cut the list, it
    # is counted in `dropped` instead of vanishing.
    li, calls = _reading_client(_feed_fixture())
    res = li.get_job_recommendations(1)
    assert "variables=(count:1,start:0)" in calls["get"][-1], "the cap goes to the server"
    assert res["ok"] is True and res["state"] == "hits"
    assert res["count"] == len(res["results"]) == 3, "every read card is returned, none cut away"
    assert res["dropped"] == 0 and res["requested_count"] == 1
    assert res["paging_total"] == 3, "the server-side total stays visible next to the list"


def test_get_job_applies_the_requested_description_budget():
    # HARDENING (tester). That the resolved budget actually reaches the projection is unproven:
    # the clamp test only reads the note, and the fixture description is short enough to survive
    # the default. A client that dropped the argument would pass the whole suite.
    li, _ = _reading_client(_job_fixture())
    res = li.get_job(_JOB_ID, description_chars=20)
    assert res["ok"] is True
    assert len(res["description_text"]) == 20
    assert res["description_truncated"] is True


def test_get_job_recommendations_uses_the_captured_cursor_query_with_the_token():
    li, calls = _reading_client(_feed_fixture())
    li.get_job_recommendations(20, pagination_token="aq4V+nwzP/OiDU")
    url = calls["get"][-1]
    assert "variables=(paginationToken:aq4V%2BnwzP%2FOiDU)" in url, "the token must be encoded"
    assert "queryId=voyagerJobsDashJobsFeed.711cec89dd87dcf89df6a9d6e7ab5682" in url
    assert "count:" not in url


def test_get_job_recommendations_refuses_a_useless_count_without_any_call():
    for value in (0, -1, "many", None, True):
        li, calls = _reading_client(_feed_fixture())
        res = li.get_job_recommendations(value)
        assert calls["get"] == [], f"count={value!r} must not reach the transport"
        assert res["ok"] is False and res["status"] == "invalid_input"


def test_get_job_recommendations_tells_an_empty_page_from_an_unreadable_one():
    li, _ = _reading_client({"data": {"elements": [], "paging": {"count": 20, "total": 0}}})
    empty = li.get_job_recommendations(20)
    assert empty["ok"] is True and empty["state"] == "empty" and empty["count"] == 0
    li, _ = _reading_client({"data": {}})
    unknown = li.get_job_recommendations(20)
    assert unknown["ok"] is False and unknown["state"] == "unknown"
    assert "re-capture" in unknown["note"], "the caller must learn how to close the gap"


def test_get_job_recommendations_never_reports_a_silent_zero_for_a_full_page():
    # The reproduced false success: a real collection came back as ok=True, count=0.
    body = {"data": {"elements": [{"trackingUrn": "urn:li:fsd_jobPosting:1111111111"},
                                  {"trackingUrn": "urn:li:fsd_jobPosting:2222222222"},
                                  {"trackingUrn": "urn:li:fsd_jobPosting:3333333333"}],
                     "paging": {"count": 20, "start": 0, "total": 3}}}
    li, _ = _reading_client(body)
    res = li.get_job_recommendations(20)
    assert res["ok"] is True and res["count"] == 3 and res["paging_total"] == 3
    # and the inverse: paging says there are jobs, none could be read → error, not an empty list
    li, _ = _reading_client({"data": {"elements": [], "paging": {"total": 3}}})
    drift = li.get_job_recommendations(20)
    assert drift["ok"] is False and drift["state"] == "drift" and drift["results"] == []


def test_get_job_recommendations_reads_the_owner_measured_module_feed():
    # The three-hop chain at the CLIENT boundary (owner-run 2026-07-31): the feed's entries are
    # jobs-feed MODULES, and only three of the five carry a job card. That the module/skip/loss
    # counters actually reach the caller is a separate claim from the parser's.
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "jobs_feed_modules.json"),
              "r", encoding="utf-8") as fh:
        body = json.load(fh)
    li, _ = _reading_client(body)
    res = li.get_job_recommendations(20)
    assert res["ok"] is True and res["state"] == "hits" and res["count"] == 3
    assert res["read_entries"] == 5 and res["skipped"] == 4 and res["lost"] == 0
    assert res["paging_total"] == 5, "paging.total counts MODULES on this route, not jobs"
    assert res["results"][0]["job_id"] == "4441501850"
    assert res["results"][0]["company"] == "Universum Managementges. mbH"


def test_a_pure_promotion_feed_is_not_an_error_at_the_client_boundary():
    # THE WITHDRAWN INVARIANT: 'paging.total > 0 with count 0 is an error' is FALSE on the feed
    # route, because `total` counts modules. A promotion-only feed must reach the agent as an
    # honest empty page — no `error`, ok=True — or the scout learns to distrust the field.
    module = {"entityUrn": "urn:li:fsd_jobsFeedCardModule:(JOBS_HOME_JYMBII,aaa)",
              "hide": False, "moduleType": "SINGLE",
              "entitiesResolutionResults": [{"jobPostingCardWrapper": None,
                                             "*promotionalCard": "urn:li:fsd_promotionalCard:X"}]}
    body = {"data": {"data": {"jobsDashJobsFeedAll": {
        "*elements": [module["entityUrn"]], "paging": {"count": 5, "start": 0, "total": 5}}}},
        "included": [module]}
    li, _ = _reading_client(body)
    res = li.get_job_recommendations(5)
    assert res["ok"] is True and res["state"] == "empty" and res["count"] == 0
    assert res["paging_total"] == 5 and res["skipped"] == 1 and res["lost"] == 0
    assert "error" not in res, "an expectable promotion feed is not a read error"


def test_a_lost_job_card_reaches_the_caller_as_an_error_not_as_a_short_list():
    # The other side of the same coin: a wrapper WAS there and its card did not resolve. ok=False
    # plus the counts — never a quietly shorter `results`.
    module = {"entityUrn": "urn:li:fsd_jobsFeedCardModule:(JOBS_HOME_JYMBII,aaa)",
              "hide": False, "moduleType": "VERTICAL_LIST",
              "entitiesResolutionResults": [{"jobPostingCardWrapper": {
                  "*jobPostingCard": "urn:li:fsd_jobPostingCard:(4441501850,JOBS_HOME_JYMBII)"}}]}
    body = {"data": {"data": {"jobsDashJobsFeedAll": {
        "*elements": [module["entityUrn"]], "paging": {"count": 5, "start": 0, "total": 1}}}},
        "included": [module]}
    li, _ = _reading_client(body)
    res = li.get_job_recommendations(5)
    assert res["ok"] is False and res["state"] == "card_lost" and res["results"] == []
    assert res["lost"] == 1 and "re-capture" in res["error"]


def test_get_job_recommendations_is_honest_on_a_graphql_error_with_200():
    li, _ = _reading_client({"data": None, "errors": [{"message": "PERMISSION_DENIED"}]})
    res = li.get_job_recommendations(20)
    assert res["ok"] is False and "PERMISSION_DENIED" in res["error"]
    assert res["state"] == "unknown" and res["count"] == 0


def test_jobs_reads_send_no_mutating_verb():
    # A "read" that POSTs is not a read. Counted, not assumed.
    li, calls = _reading_client(_job_fixture())
    li.get_job(_JOB_ID)
    li.get_job_recommendations(5)
    assert calls["post"] == [] and calls["delete"] == []
    assert len(calls["get"]) == 2


def test_jobs_parse_module_is_pure():
    # No transport may sneak into the parser: it must stay testable without any fake vgreq.
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "lib" / "jobs_parse.py").read_text()
    for forbidden in ("import requests", "import vgreq", "patchright", "playwright",
                      "subprocess", "open("):
        assert forbidden not in src, f"jobs_parse.py must not contain {forbidden!r}"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
    print(f"=== {passed}/{len(tests)} passed ===")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
