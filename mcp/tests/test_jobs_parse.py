"""test_jobs_parse.py — offline tests for the pure Jobs parsers (mcp/lib/jobs_parse.py).

No network, no cookie file, no browser: every test runs against SYNTHETIC, PII-free fixtures
(mcp/tests/fixtures/job_posting.json, jobs_feed.json) or against small inline objects. The
fixtures prove the PARSER's logic — they are NOT evidence about LinkedIn's real response form.

Three defect CLASSES from the handed-back attempt are pinned here, each with the failure it
produced:
  * the witness read at another root than the reader (three real cards → ok=True, count=0),
  * a quantitative instead of an identifying witness for a single posting (a foreign job id in
    the body silently overwrote the requested one, url included),
  * "empty" claimed although nothing was read.

Run:  .venv/bin/python -m pytest mcp/tests/test_jobs_parse.py -q
"""
import itertools
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lib import jobs_parse as jp  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
_POSTING_ID = "1234567890"


def _fixture(name: str) -> dict:
    with open(os.path.join(_FIXTURES, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _card(job_id: str, **extra) -> dict:
    """A minimal collection element: identity at an identifying key, nothing else assumed."""
    return {"trackingUrn": f"urn:li:fsd_jobPosting:{job_id}", "title": "A Job", **extra}


# ── R5: job_id normalisation, honest failure without a call ──────────────
@pytest.mark.parametrize("value,expected", [
    (1234567890, "1234567890"),
    ("1234567890", "1234567890"),
    ("  1234567890 ", "1234567890"),
    ("urn:li:fsd_jobPosting:1234567890", "1234567890"),
    ("urn:li:jobPosting:1234567890", "1234567890"),
    ("urn:li:fs_normalized_jobPosting:1234567890", "1234567890"),
    ("https://www.linkedin.com/jobs/view/platform-engineer-at-example-1234567890/",
     "1234567890"),
    ("https://www.linkedin.com/jobs/view/1234567890/", "1234567890"),
    ("https://www.linkedin.com/jobs/collections/recommended/?currentJobId=1234567890",
     "1234567890"),
])
def test_normalize_job_id_accepts_every_documented_form(value, expected):
    assert jp.normalize_job_id(value) == expected


def test_a_url_naming_two_different_job_ids_is_refused_not_resolved_by_precedence():
    # R2 on the INPUT side: a query parameter winning over /jobs/view/<id> silently swaps the job,
    # and the body-id guard cannot catch it — the body then agrees with the wrongly chosen id.
    url = "https://www.linkedin.com/jobs/view/4123456789/?refId=x&currentJobId=9876543210"
    with pytest.raises(ValueError) as excinfo:
        jp.normalize_job_id(url)
    assert "4123456789" in str(excinfo.value) and "9876543210" in str(excinfo.value)
    # the same two ids AGREEING are not a conflict
    agree = "https://www.linkedin.com/jobs/view/4123456789/?currentJobId=4123456789"
    assert jp.normalize_job_id(agree) == "4123456789"


def test_normalize_job_id_ignores_query_noise_around_a_job_url():
    # A copied job link carries geoId/position/savedSearchId — a "last digit run wins" scan
    # returns one of THOSE as the job id: wrong, but plausible enough to go unnoticed.
    url = ("https://www.linkedin.com/jobs/view/platform-engineer-at-example-1234567890/"
           "?geoId=987654321&position=1&savedSearchId=555555555")
    assert jp.normalize_job_id(url) == "1234567890"


@pytest.mark.parametrize("value", [
    "", "   ", None, 0, -5, True, False, [], {},
    "urn:li:activity:1234567890",          # a URN, but not a job
    "urn:li:fsd_profile:ACoAAsomething",
    "https://www.linkedin.com/feed/",
    "not a job at all",
])
def test_normalize_job_id_refuses_unusable_input(value):
    with pytest.raises(ValueError):
        jp.normalize_job_id(value)


# ── R4: Attributed Text is never str()'d ────────────────────────────────
@pytest.mark.parametrize("value,expected", [
    ("plain string", "plain string"),
    ({"text": "attributed", "attributes": [{"start": 0}]}, "attributed"),
    ({"text": {"text": "nested"}}, "nested"),
    (None, ""),
    ({}, ""),
    ({"attributes": []}, ""),
    ([{"text": "in a list"}], ""),
    (12345, ""),
])
def test_attributed_text_extracts_or_returns_empty(value, expected):
    assert jp.attributed_text(value) == expected


def test_attributed_text_never_leaks_a_python_repr():
    value = {"attributes": [{"type": {"bold": {}}}], "$type": "com.linkedin.AttributedText"}
    out = jp.attributed_text(value)
    assert out == "", "an unreadable Attributed Text must be empty, never a repr"
    for leak in ("{", "attributes", "com.linkedin"):
        assert leak not in out


def test_attributed_text_stops_at_its_depth_limit():
    deep = {"text": None}
    node = deep
    for _ in range(20):
        node["text"] = {"text": None}
        node = node["text"]
    node["text"] = "too deep"
    assert jp.attributed_text(deep) == "", "the extractor must bail out, not recurse forever"


# ── R7: repostedJob arrives as the STRING "True"/"False" ────────────────
@pytest.mark.parametrize("value,expected", [
    ("True", True), ("true", True), ("False", False), ("false", False), (" False ", False),
    (True, True), (False, False),
    (None, None), ("", None), ("maybe", None), (1, None), (0, None), ({}, None),
])
def test_tri_bool_parses_string_booleans_and_keeps_unknown_unknown(value, expected):
    assert jp.tri_bool(value) is expected


def test_the_string_false_is_not_truthy_after_parsing():
    # The whole point: `if ent["repostedJob"]:` reads the STRING "False" as True.
    assert bool("False") is True
    assert jp.tri_bool("False") is False


# ── R2: the identifying witness ─────────────────────────────────────────
def test_posting_read_from_the_fixture_is_identified_and_projected():
    read = jp.read_job_posting(_fixture("job_posting.json"), _POSTING_ID)
    assert read["ok"] is True and read["identity"] == "match"
    f = read["fields"]
    assert f["job_id"] == _POSTING_ID
    assert f["url"] == f"https://www.linkedin.com/jobs/view/{_POSTING_ID}/"
    assert f["title"] == "Platform Engineer"
    assert f["company"] == "Example Company", "company comes from included[], not from data"
    assert f["location"] == "Sample City, Sample Region"
    assert f["employment_status"] == "Full-time"
    assert f["remote_allowed"] is True
    assert f["listed_at"] == 1750000000000
    assert f["applies"] == 12 and f["views"] == 340
    assert f["salary"] == "60,000 - 80,000 per year" and f["salary_present"] is True
    assert f["reposted"] is False, "'False' as a STRING must become the boolean False"
    assert f["description_text"].startswith("We run a small platform team")
    assert f["description_truncated"] is False
    assert set(f) == {"job_id", "url", "title", "company", "location", "employment_status",
                      "remote_allowed", "listed_at", "applies", "views", "salary",
                      "salary_present", "reposted", "description_text", "description_truncated"}


def test_a_foreign_job_id_in_the_body_is_a_hard_error_not_a_correction():
    # THE defect: the body id silently replaced the requested one, url included, so a caller
    # received a link to a different job than the one it evaluated.
    raw = _fixture("job_posting.json")
    read = jp.read_job_posting(raw, "9999999999")
    assert read["ok"] is False and read["identity"] == "mismatch"
    assert read["body_job_id"] == _POSTING_ID
    assert read["fields"] is None, "no payload may leave on a mismatch — it describes another job"
    assert _POSTING_ID in read["reason"] and "9999999999" in read["reason"]
    assert "jobs/view" not in json.dumps(read), "no url may be built from the body id"


def test_a_body_without_any_identifying_id_is_reported_not_celebrated():
    raw = {"data": {"title": "Platform Engineer", "applies": 12, "views": 340,
                    "formattedLocation": "Sample City"}}
    read = jp.read_job_posting(raw, _POSTING_ID)
    assert read["ok"] is False and read["identity"] == "absent"
    assert read["fields"] is None
    assert "identifying" in read["reason"]


def test_an_empty_body_is_never_a_successful_posting_read():
    for raw in ({}, {"data": {}}, None, [], "not json"):
        read = jp.read_job_posting(raw, _POSTING_ID)
        assert read["ok"] is False, f"{raw!r} must not read as a job posting"


@pytest.mark.parametrize("ent,expected", [
    ({"entityUrn": "urn:li:fsd_jobPosting:42"}, "42"),
    ({"objectUrn": "urn:li:jobPosting:42"}, "42"),
    ({"trackingUrn": "urn:li:fsd_jobPosting:42"}, "42"),
    ({"jobPostingUrn": "urn:li:fsd_jobPosting:42"}, "42"),
    ({"jobPostingId": 42}, "42"),
    ({"jobPostingId": "42"}, "42"),
    # NOT identifying: a reference to some other job inside the same body
    ({"similarJobs": "urn:li:fsd_jobPosting:777", "title": "A Job"}, None),
    ({"entityUrn": "urn:li:fsd_profile:ACoAAx"}, None),
    ({}, None),
    ("not a dict", None),
])
def test_identifying_job_id_reads_only_identifying_positions(ent, expected):
    assert jp.identifying_job_id(ent) == expected


def test_a_reference_to_another_job_does_not_fake_a_mismatch():
    # A greedy value scan would find the recommendation URN and abort a perfectly correct read.
    raw = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job",
                    "relatedJobUrn": "urn:li:fsd_jobPosting:8888888888"}}
    read = jp.read_job_posting(raw, _POSTING_ID)
    assert read["ok"] is True and read["identity"] == "match"


def test_two_conflicting_identifying_ids_are_a_mismatch_in_any_key_order():
    # HARDENING (tester). R2 is a HARD abort. If a body carries two identifying ids that disagree,
    # the verdict must not depend on which one LinkedIn happened to serialize first — otherwise
    # Manuel's abort is decided by JSON key order, and the scout gets a link to another job.
    ent_a = {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}",
             "jobPostingId": 9999999999, "title": "A Job"}
    ent_b = {"jobPostingId": 9999999999,
             "entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job"}
    for name, ent in (("entityUrn first", ent_a), ("jobPostingId first", ent_b)):
        read = jp.read_job_posting({"data": ent}, _POSTING_ID)
        assert read["ok"] is False, f"{name}: conflicting ids must never be a successful read"
        assert read["identity"] == "mismatch", f"{name}: identity must be mismatch"
        assert read["fields"] is None, f"{name}: no payload may leave on conflicting ids"


@pytest.mark.parametrize("ref_key", [
    "relatedJobPostingUrn", "similarJobPostingUrn", "relatedJobUrn", "similarJobs",
    "*jobPostingRecommendation",
])
def test_a_reference_key_is_never_an_identity_in_either_direction(ref_key):
    # BOTH failure directions of a too-wide identity predicate, in one test:
    # (a) the reference carries the REQUESTED id while the real entityUrn differs — the read must
    #     still abort, or foreign title/description leave under the requested url;
    # (b) the reference carries a FOREIGN id next to a correct entityUrn — the read must succeed.
    masking = {ref_key: f"urn:li:fsd_jobPosting:{_POSTING_ID}",
               "entityUrn": "urn:li:fs_normalized_jobPosting:9999999999",
               "title": "SOME OTHER JOB", "description": {"text": "desc of the OTHER job"}}
    read = jp.read_job_posting({"data": masking}, _POSTING_ID)
    assert read["ok"] is False and read["identity"] == "mismatch", (
        f"{ref_key} must not vouch for the requested id")
    assert read["fields"] is None
    assert "SOME OTHER JOB" not in json.dumps(read) and "jobs/view" not in json.dumps(read)

    correct = {ref_key: "urn:li:fsd_jobPosting:8888888888",
               "entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job"}
    ok_read = jp.read_job_posting({"data": correct}, _POSTING_ID)
    assert ok_read["ok"] is True and ok_read["identity"] == "match", (
        f"a {ref_key} pointing elsewhere must not abort a correct read")


def test_the_identity_verdict_does_not_depend_on_key_order_in_any_permutation():
    keys = {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}",
            "jobPostingId": 9999999999,
            "trackingUrn": "urn:li:fsd_jobPosting:7777777777",
            "title": "A Job"}
    verdicts = set()
    for order in itertools.permutations(keys):
        read = jp.read_job_posting({"data": {k: keys[k] for k in order}}, _POSTING_ID)
        verdicts.add((read["ok"], read["identity"]))
    assert verdicts == {(False, "mismatch")}, (
        "every serialisation order of three disagreeing ids must be the same hard abort")


def test_an_identified_body_without_a_single_readable_field_is_not_a_successful_read():
    # The posting-side of R3: identity proven, content absent. 'A job without details' and
    # 'I could not read the job' are different answers and must not share ok=True.
    read = jp.read_job_posting({"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}"}},
                               _POSTING_ID)
    assert read["ok"] is False and read["identity"] == "match"
    assert read["fields"] is None and read["read_fields"] == []
    assert "re-capture" in read["reason"]


def test_a_posting_entity_living_in_included_is_read_not_reported_as_contentless():
    # A normalized body may keep only a reference in `data`. Returning an all-null projection for
    # it would be a quantitative claim ('no details') the read does not support.
    raw = {"data": {"*jobPosting": f"urn:li:fsd_jobPosting:{_POSTING_ID}"},
           "included": [{"$type": "com.linkedin.voyager.dash.jobs.JobPosting",
                         "entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}",
                         "title": "Platform Engineer", "description": {"text": "real text"}}]}
    read = jp.read_job_posting(raw, _POSTING_ID)
    assert read["ok"] is True and read["identity"] == "match"
    assert read["fields"]["title"] == "Platform Engineer"
    assert read["fields"]["description_text"] == "real text"
    assert read["fields"]["url"] == f"https://www.linkedin.com/jobs/view/{_POSTING_ID}/"


def test_two_included_entities_claiming_the_requested_job_are_ambiguous_not_a_pick():
    raw = {"data": {"*jobPosting": f"urn:li:fsd_jobPosting:{_POSTING_ID}"},
           "included": [{"$type": "com.linkedin.voyager.dash.jobs.JobPosting",
                         "entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "One"},
                        {"$type": "com.linkedin.voyager.dash.jobs.JobPosting",
                         "entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "Two"}]}
    read = jp.read_job_posting(raw, _POSTING_ID)
    assert read["ok"] is False and read["identity"] == "ambiguous" and read["fields"] is None
    assert "One" not in json.dumps(read) and "Two" not in json.dumps(read)


def test_a_diverging_id_on_a_discarded_wrapper_still_aborts_hard():
    # FIX ROUND 2 (approver blocker). The witness used to be collected only AFTER the second
    # `data` unwrap, so an id on the OUTER node was never compared with the requested one: a body
    # naming job 9999999999 passed as identity="match" and handed out the requested job's url.
    # R2 is literal — any diverging body id is an error, at whichever level it sits.
    raw = {"data": {"entityUrn": "urn:li:fsd_jobPosting:9999999999",
                    "data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}",
                             "title": "A Job", "description": {"text": "d"}}}}
    read = jp.read_job_posting(raw, _POSTING_ID)
    assert read["ok"] is False and read["identity"] == "mismatch"
    assert read["fields"] is None and "9999999999" in read["body_job_ids"]


def test_a_wrapper_without_an_id_does_not_break_a_correct_nested_read():
    # The other direction of the same fix: collecting ids over both levels must not turn a body
    # whose wrapper is merely a container into a false abort.
    raw = {"data": {"paging": {"count": 1},
                    "data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}",
                             "title": "A Job", "description": {"text": "d"}}}}
    read = jp.read_job_posting(raw, _POSTING_ID)
    assert read["ok"] is True and read["identity"] == "match"
    assert read["fields"]["url"] == f"https://www.linkedin.com/jobs/view/{_POSTING_ID}/"


# ── the company name is a JOIN, never the first entry of the pool ────────
def test_the_company_is_joined_on_the_reference_the_body_itself_carries():
    # A pool holding two companies: the fixture-style 'take the one in included' would name the
    # staffing agency for a job that references the other company — right job, wrong employer.
    raw = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job",
                    "companyDetails": {"company": "urn:li:fs_normalized_company:99"}},
           "included": [{"$type": "com.linkedin.voyager.organization.Company",
                         "entityUrn": "urn:li:fs_normalized_company:77", "name": "Other Company"},
                        {"$type": "com.linkedin.voyager.organization.Company",
                         "entityUrn": "urn:li:fs_normalized_company:99",
                         "name": "Example Company"}]}
    assert jp.read_job_posting(raw, _POSTING_ID)["fields"]["company"] == "Example Company"


def test_an_unjoinable_posting_next_to_several_companies_reports_no_company():
    raw = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job"},
           "included": [{"$type": "com.linkedin.voyager.organization.Company",
                         "entityUrn": "urn:li:fs_normalized_company:77", "name": "Other Company"},
                        {"$type": "com.linkedin.voyager.organization.Company",
                         "entityUrn": "urn:li:fs_normalized_company:99",
                         "name": "Example Company"}]}
    assert jp.read_job_posting(raw, _POSTING_ID)["fields"]["company"] is None, (
        "with two candidate employers no name may be claimed"
    )


def test_two_conflicting_company_references_claim_no_employer():
    raw = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job",
                    "companyDetails": {"company": "urn:li:fs_normalized_company:77"},
                    "hiringCompany": "urn:li:fs_normalized_company:99"},
           "included": [{"$type": "com.linkedin.voyager.organization.Company",
                         "entityUrn": "urn:li:fs_normalized_company:77", "name": "Other Company"},
                        {"$type": "com.linkedin.voyager.organization.Company",
                         "entityUrn": "urn:li:fs_normalized_company:99",
                         "name": "Example Company"}]}
    assert jp.read_job_posting(raw, _POSTING_ID)["fields"]["company"] is None


# ── R6: unknown is not False, salary present is not salary read ─────────
def test_missing_flags_and_counters_stay_none():
    raw = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job"}}
    f = jp.read_job_posting(raw, _POSTING_ID)["fields"]
    for key in ("remote_allowed", "applies", "views", "salary", "listed_at", "reposted",
                "company", "location", "employment_status"):
        assert f[key] is None, f"{key} must be None when it was not read, never False/0"
    assert f["salary_present"] is False, "no salaryInsights at all means: no salary"


def test_salary_present_but_unprojectable_is_distinguishable_from_no_salary():
    urn_only = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job",
                         "salaryInsights": {"$type": "com.linkedin.voyager.jobs.SalaryInsights",
                                            "entityUrn": "urn:li:fs_salaryInsights:1"}}}
    f = jp.read_job_posting(urn_only, _POSTING_ID)["fields"]
    assert f["salary"] is None, "a URN/class name is plumbing, never a salary text"
    assert f["salary_present"] is True, "LinkedIn sent salaryInsights — say so"


def test_employment_status_object_is_never_stringified():
    raw = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job",
                    "employmentStatus": {"$type": "com.linkedin.voyager.jobs.EmploymentStatus",
                                         "entityUrn": "urn:li:fs_employmentStatus:1",
                                         "localizedName": "Part-time"}}}
    f = jp.read_job_posting(raw, _POSTING_ID)["fields"]
    assert f["employment_status"] == "Part-time"
    assert "urn:" not in str(f["employment_status"]) and "{" not in str(f["employment_status"])


# ── description budget: every clamp declares itself ─────────────────────
def test_description_is_truncated_and_flagged():
    raw = {"data": {"entityUrn": f"urn:li:fsd_jobPosting:{_POSTING_ID}", "title": "A Job",
                    "description": {"text": "x" * 500}}}
    f = jp.read_job_posting(raw, _POSTING_ID, description_chars=100)["fields"]
    assert len(f["description_text"]) == 100 and f["description_truncated"] is True


@pytest.mark.parametrize("requested", [0, -1, 10 ** 9, "many", None, True])
def test_every_description_clamp_returns_its_own_sentence(requested):
    chars, note = jp.effective_description_chars(requested)
    assert chars == jp.MAX_DESCRIPTION_CHARS
    assert note and str(jp.MAX_DESCRIPTION_CHARS) in note


def test_a_description_budget_within_the_ceiling_is_silent():
    assert jp.effective_description_chars(4000) == (4000, None)


# ── R1: the witness is bound to the container that was READ ─────────────
def test_a_canonical_restli_collection_with_three_cards_reads_three():
    # The reproduced false success: ok=True, count=0 plus the note "a genuinely empty page".
    raw = {"data": {"elements": [_card("1111111111"), _card("2222222222"), _card("3333333333")],
                    "paging": {"count": 3, "start": 0, "total": 3}}}
    read = jp.read_job_collection(raw)
    assert read["ok"] is True and read["state"] == "hits" and read["count"] == 3
    assert [c["job_id"] for c in read["results"]] == ["1111111111", "2222222222", "3333333333"]
    assert read["paging_total"] == 3


def test_an_aliased_graphql_container_is_found_by_shape_not_by_name():
    read = jp.read_job_collection(_fixture("jobs_feed.json"))
    assert read["ok"] is True and read["state"] == "hits" and read["count"] == 3
    assert read["paging_total"] == 3
    assert read["pagination_token"] == "SYNTHETIC_PAGINATION_TOKEN"
    first = read["results"][0]
    assert first["job_id"] == "1111111111"
    assert first["url"] == "https://www.linkedin.com/jobs/view/1111111111/"
    assert first["remote_allowed"] is True
    assert read["results"][1]["reposted"] is True and read["results"][0]["reposted"] is False
    assert read["results"][2]["reposted"] is None, "unread stays unknown"


def test_a_card_reports_no_company_it_cannot_join():
    # The pool in included[] holds one company; handing it to every card would invent a plausible
    # employer per card. Only a card that REFERENCES the company gets the name.
    read = jp.read_job_collection(_fixture("jobs_feed.json"))
    assert all(c["company"] is None for c in read["results"])
    # key name below is synthetic — the join runs on the VALUE (the company's entityUrn)
    joined = {"data": {"elements": [_card("1111111111",
                                          companyRef="urn:li:fs_normalized_company:99")]},
              "included": [{"$type": "com.linkedin.voyager.organization.Company",
                            "entityUrn": "urn:li:fs_normalized_company:99",
                            "name": "Example Company"}]}
    assert jp.read_job_collection(joined)["results"][0]["company"] == "Example Company"


def test_elements_inside_included_are_not_the_read_container():
    # included[] is the entity POOL. An `elements` list nested in one of its entities (an insight
    # list, a carousel) must never pose as the collection the caller asked for.
    raw = {"included": [{"$type": "com.linkedin.voyager.jobs.Insights",
                         "elements": [_card("1111111111"), _card("2222222222")]}]}
    read = jp.read_job_collection(raw)
    assert read["ok"] is False and read["state"] == "unknown"
    assert read["container_found"] is False and read["count"] == 0


def test_the_shallowest_container_wins_and_is_the_one_read_from():
    inner = {"elements": [_card("2222222222")], "paging": {"total": 1}}
    raw = {"data": {"elements": [_card("1111111111")], "paging": {"total": 7},
                    "nested": inner}}
    node = jp.find_collection(raw)
    assert node is raw["data"], "the shallowest elements container is the read root"
    read = jp.read_job_collection(raw)
    # hits AND paging come from the SAME node — never one from here and one from there
    assert [c["job_id"] for c in read["results"]] == ["1111111111"]
    assert read["paging_total"] == 7


# ── R3: 'empty' may only be claimed when it was READ ────────────────────
def test_an_empty_read_container_is_an_honest_empty_page():
    raw = {"data": {"elements": [], "paging": {"count": 20, "start": 0, "total": 0}}}
    read = jp.read_job_collection(raw)
    assert read["ok"] is True and read["state"] == "empty" and read["count"] == 0
    assert read["results"] == [] and read["paging_total"] == 0


def test_an_empty_container_without_paging_is_still_empty_because_it_was_read():
    read = jp.read_job_collection({"data": {"elements": []}})
    assert read["ok"] is True and read["state"] == "empty" and read["paging_total"] is None


@pytest.mark.parametrize("raw", [
    {},
    {"data": {}},
    {"data": {"paging": {"count": 20, "start": 0}}},   # count is what WE asked for, not evidence
    {"data": None},
    None,
    "a login page, not JSON",
])
def test_no_container_means_unknown_never_empty(raw):
    read = jp.read_job_collection(raw)
    assert read["ok"] is False, f"{raw!r} must not read as a successful page"
    assert read["state"] == "unknown", "a scout must tell 'no jobs' from 'I could not read'"
    assert read["state"] != "empty"
    assert "re-capture" in read["reason"]


def test_paging_total_above_zero_with_no_hits_is_an_error_not_an_empty_list():
    raw = {"data": {"elements": [], "paging": {"count": 20, "start": 0, "total": 42}}}
    read = jp.read_job_collection(raw)
    assert read["ok"] is False and read["state"] == "drift" and read["results"] == []
    assert "42" in read["reason"] and "re-capture" in read["reason"]


def test_elements_that_carry_no_job_id_are_drift_not_an_empty_page():
    raw = {"data": {"elements": [{"title": "A Job"}, {"title": "Another Job"}]}}
    read = jp.read_job_collection(raw)
    assert read["ok"] is False and read["state"] == "drift"
    assert "identifying job id" in read["reason"]


def test_unreadable_elements_are_never_reported_as_an_empty_page():
    # HARDENING (tester). The reproduced false-success class, one level deeper: the container is
    # NOT empty, its entries are merely unreadable (strings instead of objects). R3 allows 'empty'
    # only when the READ container was empty — three discarded entries are 'could not read'.
    raw = {"data": {"elements": ["urn:li:fsd_jobPosting:1111111111"] * 3}}
    read = jp.read_job_collection(raw)
    assert read["state"] != "empty", "a container holding three entries was never an empty page"
    assert read["ok"] is False and read["state"] == "drift"
    assert "re-capture" in read["reason"]
    # the same body WITH server-side evidence must stay an error too (already covered, kept as
    # the pair so the two paths cannot drift apart)
    paged = jp.read_job_collection({"data": {"elements": ["urn:li:fsd_jobPosting:1"] * 3,
                                             "paging": {"total": 3}}})
    assert paged["ok"] is False and paged["state"] == "drift"


def test_partly_unreadable_elements_are_not_silently_dropped():
    # HARDENING (tester). Two entries could not be read, one could. Reporting count=1 without a
    # word is a quantitative claim the read does not support: the caller cannot tell a one-card
    # page from a three-card page the parser mostly lost.
    raw = {"data": {"elements": ["junk", "junk", _card("1111111111")]}}
    read = jp.read_job_collection(raw)
    assert read["ok"] is True and read["state"] == "hits" and read["count"] == 1
    assert read["reason"], "the two discarded entries must be surfaced, not swallowed"
    assert "3" in read["reason"] or "2" in read["reason"]


def test_an_empty_sibling_container_cannot_make_a_filled_page_look_empty():
    # The rejected false success in its purest form: two candidate containers, ONE real card, and
    # the verdict decided by dict insertion order — 'no jobs' in one order, three hits in the other.
    filled = {"elements": [_card("1111111111")], "paging": {"total": 1}}
    for name, body in (("decoy first", {"promo": {"elements": []}, "feed": filled}),
                       ("feed first", {"feed": filled, "promo": {"elements": []}})):
        read = jp.read_job_collection({"data": body})
        assert (read["ok"], read["state"], read["count"]) == (True, "hits", 1), name
        assert read["paging_total"] == 1, f"{name}: paging comes from the container that was read"
        assert read["results"][0]["job_id"] == "1111111111", name


@pytest.mark.parametrize("order", [("elements", "paging", "jobsFeed"),
                                   ("jobsFeed", "elements", "paging")])
def test_an_empty_outer_container_cannot_hide_a_filled_one_nested_below_it(order):
    # FIX ROUND 2 (QA + approver blocker). The rejected false success in parent/child form: the
    # search appended a node holding an `elements` list and stopped descending — even when that
    # list was EMPTY. Three readable cards one level deeper produced ok=True, state="empty",
    # count=0, plus the body's two contradicting paging.total (0 outside, 3 inside) read as 0.
    inner = {"elements": [_card("1111111111"), _card("2222222222"), _card("3333333333")],
             "paging": {"total": 3}}
    keys = {"elements": [], "paging": {"total": 0}, "jobsFeed": inner}
    read = jp.read_job_collection({"data": {k: keys[k] for k in order}})
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", 3), order
    assert read["paging_total"] == 3, "paging comes from the container that was read"
    assert [c["job_id"] for c in read["results"]] == ["1111111111", "2222222222", "3333333333"]


def test_an_empty_outer_container_without_paging_still_finds_the_nested_cards():
    # Same shape without any server-side counter, and in the doubly nested `data.data` form the
    # graphql feed bodies use — nothing but the read may decide 'empty'.
    flat = jp.read_job_collection({"data": {"elements": [], "jobsFeed": {
        "elements": [_card("1111111111")]}}})
    assert (flat["ok"], flat["state"], flat["count"]) == (True, "hits", 1)
    nested = jp.read_job_collection({"data": {"elements": [], "data": {"jobsDashJobsFeed": {
        "elements": [_card("1111111111"), _card("2222222222")], "paging": {"total": 2}}}}})
    assert (nested["ok"], nested["state"], nested["count"]) == (True, "hits", 2)


def test_a_filled_elements_list_is_still_not_descended_into():
    # The boundary the fix must NOT move: a card's own nested `elements` list (an insight list) is
    # card content, so a FILLED container stays the read root and its cards are not candidates.
    raw = {"data": {"elements": [_card("1111111111", insights={"elements": [_card("9999999999")]})],
                    "paging": {"total": 1}}}
    read = jp.read_job_collection(raw)
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", 1)
    assert [c["job_id"] for c in read["results"]] == ["1111111111"]
    assert jp.find_collection(raw) is raw["data"]


def test_two_filled_candidate_containers_are_ambiguous_not_a_choice():
    body = {"data": {"feedA": {"elements": [_card("1111111111")]},
                     "feedB": {"elements": [_card("2222222222")]}}}
    read = jp.read_job_collection(body)
    assert read["ok"] is False and read["state"] == "ambiguous"
    assert read["state"] != "empty" and read["results"] == [] and read["count"] == 0
    assert "re-capture" in read["reason"]
    assert jp.find_collection(body) is None, "an undecidable container choice is not a container"


def test_a_pagination_token_hanging_off_a_card_is_not_the_page_cursor():
    read = jp.read_job_collection({"data": {"elements": [
        _card("1111111111", paginationToken="TOKEN_FROM_A_CARD")]}})
    assert read["ok"] is True and read["count"] == 1
    assert read["pagination_token"] is None, "a card's token would re-request the wrong thing"


def test_two_different_container_tokens_yield_no_cursor():
    node = {"elements": [], "metadata": {"paginationToken": "ONE"},
            "extra": {"paginationToken": "TWO"}}
    assert jp.find_pagination_token(node) is None
    same = {"elements": [], "metadata": {"paginationToken": "ONE"},
            "extra": {"paginationToken": "ONE"}}
    assert jp.find_pagination_token(same) == "ONE", "one distinct token is an answer"


def test_read_entries_and_discarded_balance_against_the_raw_container():
    raw = {"data": {"elements": [_card("1111111111"), "junk", None,
                                 _card("1111111111"), _card("2222222222")]}}
    read = jp.read_job_collection(raw)
    assert read["read_entries"] == 5, "the raw container length, not the projectable subset"
    assert read["discarded"] == 2 and read["count"] == 2
    assert read["reason"] and "5" in read["reason"]


def test_paging_total_is_read_from_the_container_only():
    # A `paging.total` sitting in a DIFFERENT object is not evidence about this container.
    node = {"elements": [], "meta": {"paging": {"total": 99}}}
    assert jp.paging_total(node) is None
    assert jp.paging_total({"elements": [], "paging": {"total": 5}}) == 5
    assert jp.paging_total({"elements": [], "paging": {"count": 5}}) is None


def test_duplicates_are_collapsed_and_the_limit_is_applied():
    raw = {"data": {"elements": [_card("1111111111"), _card("1111111111"),
                                 _card("2222222222"), _card("3333333333")]}}
    read = jp.read_job_collection(raw, limit=2)
    assert [c["job_id"] for c in read["results"]] == ["1111111111", "2222222222"]
    assert read["count"] == 2


# ── a 200 that carries an error is not a read ──────────────────────────
@pytest.mark.parametrize("raw,fragment", [
    ({"status": 403, "message": "Forbidden",
      "data": {"$type": "com.linkedin.voyager.ErrorResponse"}}, "403"),
    ({"errors": [{"message": "PERMISSION_DENIED"}]}, "PERMISSION_DENIED"),
    ({"errors": [{}]}, "GraphQL"),
    ({"$type": "com.linkedin.common.ErrorResponse", "message": "nope"}, "nope"),
])
def test_inband_error_catches_both_error_envelopes(raw, fragment):
    msg = jp.inband_error(raw)
    assert msg and fragment in msg


@pytest.mark.parametrize("raw", [
    {"data": {"elements": []}},
    {"data": {"title": "A Job"}, "errors": []},
    {},
    None,
    {"status": 200, "message": "ok"},
])
def test_inband_error_stays_quiet_on_a_clean_body(raw):
    assert jp.inband_error(raw) is None
