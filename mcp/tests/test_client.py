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


def _client_with_response(resp_json, code=200):
    """A client whose vgreq.post returns a canned json body + status (for create_post body checks)."""
    calls = {"post": []}
    fake = types.ModuleType("vgreq")
    class R:
        status_code = code
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
    assert r["ok"] is False and "currentActor" in r.get("note", "")


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
