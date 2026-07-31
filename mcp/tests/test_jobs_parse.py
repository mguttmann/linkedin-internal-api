"""test_jobs_parse.py — offline tests for the pure Jobs parsers (mcp/lib/jobs_parse.py).

No network, no cookie file, no browser: every test runs against PII-free fixtures
(mcp/tests/fixtures/job_posting.json, jobs_feed.json, jobs_feed_modules.json) or against small
inline objects. job_posting.json and jobs_feed.json are SYNTHETIC and prove the PARSER's logic
only — they are no evidence about LinkedIn's real response form. jobs_feed_modules.json reproduces
the FORM the owner measured live (owner-run 2026-07-31), field by field, and says in its
`_provenance` which values are his and which were added synthetically. That the parser reads that
form is proven OFFLINE here; the read itself is not live-tested (🔍, never ✅).

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
    # THE SURVIVING HALF of the invariant that was withdrawn for the feed: it holds for an EMPTY
    # ENTRY LIST (no entry at all next to a server-side total), on either route. It does NOT hold
    # for zero JOB CARDS behind a non-empty list of modules — see
    # test_a_pure_promotion_feed_with_a_paging_total_is_empty_and_not_an_error.
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


# ── module rule 5: the feed is THREE hops and `*elements` points at MODULES ──
# Every shape below reproduces the owner's live measurement (owner-run 2026-07-31, count:5,
# queryId voyagerJobsDashJobsFeed.8b4a94e0e9d8395f1e7482987dd2f815): the chain
# `*elements` -> JobsFeedCardModule.entitiesResolutionResults[] -> <one filled union branch> ->
# `*jobPostingCard` -> JobPostingCard. The class names in `$type` are synthetic (the owner measured
# that the key exists, not its value), which is why a module is also recognised by its URN alone.
_COLL = "com.linkedin.restli.common.CollectionResponse"
_CARD_URN = "urn:li:fsd_jobPostingCard:({0},JOBS_HOME_JYMBII)"
_RESULTS = "entitiesResolutionResults"
# All 18 union branch keys, verbatim from the owner's measurement — used to prove that the filled
# branch is found at ANY position, not just where a sample of three happens to put it.
_UNION_BRANCHES = ("endOfResultsCard", "jobPostingCardWrapper", "jobSearchHistoryCard",
                   "jobSearchSuggestion", "premiumUpsellSlot", "seekerNextBestActionComponent",
                   "carouselEntityHighlightCard", "feedbackCard", "newCollectionHeaderCard",
                   "carouselCollectionCard", "careerEnrichmentCard", "tabbedCollection",
                   "noResultsCard", "seeAllCard", "*promotionalCard", "refreshStateCard",
                   "jobPostingCard", "jumpBackInCard")


def _feed_card(job_id, **extra):
    """A JobPostingCard as measured: identity in the tuple entityUrn, the text ON the card."""
    card = {"$type": "com.linkedin.voyager.dash.jobs.JobPostingCard",
            "entityUrn": f"urn:li:fsd_jobPostingCard:({job_id},JOBS_HOME_JYMBII)",
            "title": {"text": f"A Job {job_id}"},
            "primaryDescription": {"text": "An Employer GmbH · A City, A Country (Vor Ort)"}}
    card.update(extra)
    return card


def _wrap(job_id, key="jobPostingCardWrapper"):
    """One union item whose ONLY filled branch is a job branch referencing a card."""
    return {key: {"*jobPostingCard": f"urn:li:fsd_jobPostingCard:({job_id},JOBS_HOME_JYMBII)"},
            "endOfResultsCard": None, "tabbedCollection": None, "*promotionalCard": None}


def _module(tail, items, **extra):
    module = {"$type": "com.linkedin.voyager.dash.jobs.JobsFeedCardModule",
              "entityUrn": f"urn:li:fsd_jobsFeedCardModule:(JOBS_HOME_JYMBII,{tail})",
              "hide": False, "moduleType": "VERTICAL_LIST", "header": None,
              "entitiesResolutionResults": items}
    module.update(extra)
    return module


def _feed_body(modules, cards, total=None):
    """The measured envelope: data.data.<alias> with a STARRED entry list of module URNs."""
    node = {"$type": _COLL, "*elements": [m["entityUrn"] for m in modules],
            "paging": {"count": len(modules), "start": 0,
                       "total": len(modules) if total is None else total}}
    return {"data": {"data": {"jobsDashJobsFeedAll": node}}, "included": [*modules, *cards]}


def test_the_measured_five_module_feed_reads_exactly_its_three_job_cards():
    # The owner's whole run, as a fixture: 3 job cards, one empty module, one upsell, one promotion
    # and four TABBED collections. The advertising siblings are silently skipped — they are neither
    # a value nor an error — and the three cards come out with title and employer.
    read = jp.read_job_collection(_fixture("jobs_feed_modules.json"))
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", 3)
    # four of the five modules carry no job at all: the empty one, the upsell, the promotion, TABBED
    assert read["read_entries"] == 5 and read["skipped"] == 4 and read["lost"] == 0
    assert read["discarded"] == 0, "an upsell or a TABBED module is not an unreadable entry"
    assert read["paging_total"] == 5, "paging.total counts MODULES on the feed, not job cards"
    assert read["pagination_token"] == "SYNTHETIC_PAGINATION_TOKEN"
    first = read["results"][0]
    assert first["job_id"] == "4441501850"
    assert first["url"] == "https://www.linkedin.com/jobs/view/4441501850/"
    assert first["title"] == "Leitung IT/Systemadministration (w/m/d)"
    assert first["company"] == "Universum Managementges. mbH"
    assert first["location"] == "Bremen, Deutschland (Vor Ort)"
    assert first["module_type"] == "VERTICAL_LIST" and first["module_title"] == "Top-Jobs für Sie"
    assert first["job_seeker_job_state_urn"] == "urn:li:fsd_jobSeekerJobState:4441501850"
    assert first["reposted"] is None and first["salary"] is None, "unknown is not False"
    assert first["remote_allowed"] is None, "'(Vor Ort)' in prose is not a measured flag"
    assert [c["job_id"] for c in read["results"]] == ["4441501850", "4441501851", "4441501852"]
    assert read["results"][2]["title"] == "Synthetic Site Reliability Engineer", "bare string title"


def test_a_pure_promotion_feed_with_a_paging_total_is_empty_and_not_an_error():
    # THE WITHDRAWN INVARIANT, and this test is what holds it back: 'paging.total > 0 with no items
    # is an error' is FALSE for the feed, because `total` counts MODULES. Two promotional modules
    # next to total=2 are a legitimately job-free feed, not a lost read.
    modules = [_module("aaa", [{"jobPostingCardWrapper": None, "jobPostingCard": None,
                               "*premiumUpsellSlot": "urn:li:fsd_premiumUpsellSlot:X"}],
                       moduleType="SINGLE"),
               _module("bbb", [{"jobPostingCardWrapper": None, "jobPostingCard": None,
                               "*promotionalCard": "urn:li:fsd_promotionalCard:Y"}],
                       moduleType="SINGLE")]
    read = jp.read_job_collection(_feed_body(modules, []))
    assert (read["ok"], read["state"], read["count"]) == (True, "empty", 0)
    assert read["paging_total"] == 2 and read["read_entries"] == 2
    assert read["skipped"] == 2 and read["lost"] == 0 and read["discarded"] == 0
    assert read["reason"] is None, "an expectable promotion feed is no finding"


def test_a_job_branch_whose_card_is_missing_is_a_read_error_not_an_absent_card():
    # The one reliable error edge of the feed: the wrapper IS there, so a card exists — and it does
    # not resolve in included[]. Fail-closed, and nothing is invented to fill the gap.
    read = jp.read_job_collection(_feed_body([_module("aaa", [_wrap("4441501850")])], []))
    assert read["ok"] is False and read["state"] == "card_lost"
    assert read["results"] == [] and read["count"] == 0 and read["lost"] == 1
    assert read["state"] != "empty" and "re-capture" in read["reason"]
    assert "unresolved" in read["reason"] and "jobPostingCardWrapper" in read["reason"]


def test_a_partial_card_loss_names_itself_instead_of_reporting_the_survivors():
    # Three wrappers, one card missing. Returning two cards without a word is the quantitative
    # claim the read does not support — the loss has to have a NAME.
    module = _module("aaa", [_wrap("4441501850"), _wrap("4441501851"), _wrap("4441501852")])
    read = jp.read_job_collection(_feed_body([module], [_feed_card("4441501850"),
                                                        _feed_card("4441501852")]))
    assert read["ok"] is False and read["state"] == "card_lost"
    assert read["lost"] == 1 and read["count"] == 2
    assert "1 of 3" in read["reason"] and "INCOMPLETE" in read["reason"]
    assert [c["job_id"] for c in read["results"]] == ["4441501850", "4441501852"]


def test_the_bare_job_posting_card_branch_is_read_like_the_wrapper():
    # `jobPostingCard` is a union branch of its OWN, next to `jobPostingCardWrapper`. It was null
    # throughout the measured run; the parser knows it anyway — as a reference and embedded.
    referencing = _module("aaa", [_wrap("4441501850", key="jobPostingCard")])
    read = jp.read_job_collection(_feed_body([referencing], [_feed_card("4441501850")]))
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", 1)
    assert read["results"][0]["job_id"] == "4441501850"
    embedded = _module("aaa", [{"jobPostingCard": _feed_card("4441501851"),
                                "jobPostingCardWrapper": None}])
    inline = jp.read_job_collection(_feed_body([embedded], []))
    assert (inline["ok"], inline["state"], inline["count"]) == (True, "hits", 1)
    assert inline["results"][0]["job_id"] == "4441501851"


def test_two_included_entries_with_the_same_entity_urn_are_fail_closed():
    # A pool contradicting itself about one URN cannot resolve it, and 'the first one' is exactly
    # the reduction rule 3 forbids: the card is LOST, not one of two.
    module = _module("aaa", [_wrap("4441501850")])
    body = _feed_body([module], [_feed_card("4441501850"),
                                 _feed_card("4441501850", title={"text": "A Different Wording"})])
    read = jp.read_job_collection(body)
    assert read["ok"] is False and read["state"] == "card_lost" and read["results"] == []
    assert "ambiguous" in read["reason"]


def test_the_feed_verdict_does_not_depend_on_key_order_in_any_permutation():
    # LinkedIn's serialisation order is not a fact we control. The same body, re-serialised in
    # every key order of module, card and union item, must read identically.
    # The UNION ITEM is permuted too, and it carries FILLED foreign branches next to the job
    # branch: 'the FIRST filled branch is the type' passes a body whose item lists the job branch
    # first and silently skips the very same body serialised the other way round. That mutation
    # survived every other test, so this is the one place the class is held instead of an instance.
    item = {"feedbackCard": {"text": "How relevant was this?"},
            "jobPostingCardWrapper": {"*jobPostingCard": _CARD_URN.format("4441501850")},
            "tabbedCollection": {"tabs": []}}
    module = _module("aaa", [item], header={"title": {"text": "Top-Jobs für Sie"}})
    card = _feed_card("4441501850")
    baseline = jp.read_job_collection(_feed_body([module], [card]))
    assert baseline["count"] == 1, "a filled foreign branch next to the job branch is still a hit"
    for item_keys in itertools.permutations(item.keys()):
        shuffled_item = {k: item[k] for k in item_keys}
        for keys in itertools.permutations(module.keys()):
            shuffled_module = {k: module[k] for k in keys}
            shuffled_module[_RESULTS] = [shuffled_item]
            for card_keys in itertools.permutations(card.keys()):
                shuffled_card = {k: card[k] for k in card_keys}
                got = jp.read_job_collection(_feed_body([shuffled_module], [shuffled_card]))
                assert got == baseline, (item_keys, keys, card_keys)


def test_the_job_branch_is_found_at_every_position_of_the_full_eighteen_branch_union():
    # The union as measured: 18 keys, exactly one filled. The filled NAME is the type, so its
    # POSITION must not matter — not at the front, not at the back, not anywhere between. This is
    # the same class as the permutation above, at the measured width instead of a sample of three.
    for pos in range(len(_UNION_BRANCHES)):
        rotated = _UNION_BRANCHES[pos:] + _UNION_BRANCHES[:pos]
        item = {name: None for name in rotated}
        item["jobPostingCardWrapper"] = {"*jobPostingCard": _CARD_URN.format("4441501850")}
        read = jp.read_job_collection(
            _feed_body([_module("aaa", [item])], [_feed_card("4441501850")]))
        assert (read["ok"], read["state"], read["count"]) == (True, "hits", 1), rotated[0]
        assert read["results"][0]["job_id"] == "4441501850"
        assert read["lost"] == 0 and read["skipped"] == 0 and read["reason"] is None


def test_a_module_wider_than_the_width_cap_does_not_lose_cards_silently():
    # The requirement 'a partial loss NAMES itself' one level deeper than the resolution failure:
    # `_feed_module_cards` walks `entitiesResolutionResults[:_MAX_WIDTH]`, so a module wider than the
    # cap drops the rest of its RESOLVABLE wrappers without a word — ok=True, lost=0, reason=None.
    # Whether the cap stays (then named) or does not apply to this measured, bounded list is a code
    # decision; a silent count is not one of the options.
    wide = jp._MAX_WIDTH + 10
    ids = [str(4441501850 + i) for i in range(wide)]
    module = _module("aaa", [_wrap(i) for i in ids])
    read = jp.read_job_collection(_feed_body([module], [_feed_card(i) for i in ids]))
    if read["count"] == wide:
        assert read["ok"] is True and read["lost"] == 0 and read["reason"] is None
    else:
        assert read["count"] < wide
        assert read["ok"] is False or read["reason"], (
            f"{wide - read['count']} of {wide} cards were dropped at the width cap without a name: "
            f"ok={read['ok']}, lost={read['lost']}, reason={read['reason']}")
        assert str(wide) in str(read["reason"]), "the named loss has to state what it read against"


def test_a_primary_description_without_the_separator_is_all_employer():
    # Employer and location sit in ONE string. Without ' · ' the whole text is the employer and the
    # location is None — the missing half is never invented, in neither direction.
    assert jp.split_primary_description({"text": "Employer Only GmbH"}) == ("Employer Only GmbH",
                                                                            None)
    assert jp.split_primary_description(None) == (None, None)
    assert jp.split_primary_description({"text": "E GmbH · Bremen · Deutschland"}) == (
        "E GmbH", "Bremen · Deutschland"), "a further separator stays part of the location"
    module = _module("aaa", [_wrap("4441501850")])
    card = _feed_card("4441501850", primaryDescription={"text": "Employer Only GmbH"})
    read = jp.read_job_collection(_feed_body([module], [card]))
    assert read["results"][0]["company"] == "Employer Only GmbH"
    assert read["results"][0]["location"] is None


def test_an_empty_module_and_a_hidden_module_are_silently_skipped():
    # Measured siblings, not failures: module 1 of the owner's run carried zero entries. `hide` is
    # the module's own flag — a hidden module's cards are not on the page the caller sees.
    modules = [_module("aaa", []),
               _module("bbb", [_wrap("4441501851")], hide=True),
               _module("ccc", [_wrap("4441501850")])]
    read = jp.read_job_collection(_feed_body(modules, [_feed_card("4441501850"),
                                                       _feed_card("4441501851")]))
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", 1)
    assert read["skipped"] == 2 and read["lost"] == 0 and read["discarded"] == 0
    assert [c["job_id"] for c in read["results"]] == ["4441501850"]
    alone = jp.read_job_collection(_feed_body([_module("aaa", [])], []))
    assert (alone["ok"], alone["state"], alone["skipped"]) == (True, "empty", 1)


def test_a_card_without_a_job_seeker_state_is_no_error():
    # `*jobSeekerJobState` is the card's ONLY starred key and it is optional. Absent means None.
    module = _module("aaa", [_wrap("4441501850")])
    read = jp.read_job_collection(_feed_body([module], [_feed_card("4441501850")]))
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", 1)
    assert read["results"][0]["job_seeker_job_state_urn"] is None
    assert read["reason"] is None


def test_a_module_is_recognised_without_a_type_by_its_own_urn():
    # The `$type` VALUE is not owner-measured — only that the key exists. A module must therefore
    # stay readable by its measured URN prefix alone, or the whole chain hangs on an invented name.
    module = _module("aaa", [_wrap("4441501850")])
    del module["$type"]
    read = jp.read_job_collection(_feed_body([module], [_feed_card("4441501850")]))
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", 1)


def test_a_card_contradicting_itself_about_its_job_id_is_lost_not_guessed():
    # `entityUrn` is the id; `preDashNormalizedJobPostingUrn` is read ONLY to contradict it. A url
    # pointing at another job than the one that was read is the worst outcome this module knows.
    module = _module("aaa", [_wrap("4441501850")])
    card = _feed_card("4441501850",
                      preDashNormalizedJobPostingUrn="urn:li:fs_normalized_jobPosting:9999999999")
    read = jp.read_job_collection(_feed_body([module], [card]))
    assert read["ok"] is False and read["state"] == "card_lost" and read["results"] == []
    assert "contradiction" in read["reason"]


def test_a_starred_entry_list_without_a_collection_witness_is_not_a_container():
    # The container half's guard: a STARRED list holds URNs and is by shape indistinguishable from
    # any other reference list, so it is admitted only where the node itself proves it is a
    # collection (`paging` or the CollectionResponse $type) — both owner-measured on the feed.
    modules = [_module("aaa", [_wrap("4441501850")])]
    rail = {"data": {"similarJobsRail": {"*elements": [modules[0]["entityUrn"]]}},
            "included": [*modules, _feed_card("4441501850")]}
    read = jp.read_job_collection(rail)
    assert read["ok"] is False and read["state"] == "unknown"
    assert read["count"] == 0, "a reference list without a collection witness is not the feed"
    assert jp.container_entry_keys({"*elements": [], "paging": {"total": 0}}) == ["*elements"]
    assert jp.container_entry_keys({"*elements": [], "$type": _COLL}) == ["*elements"]
    assert jp.container_entry_keys({"*elements": []}) == []


def test_a_node_holding_both_entry_keys_with_content_is_ambiguous():
    # The same undecidability as two candidate containers, one level down: merging would invent a
    # page LinkedIn never sent, preferring one is 'the first key wins' again.
    both = {"data": {"$type": _COLL, "elements": [_card("1111111111")],
                     "*elements": ["urn:li:fsd_jobsFeedCardModule:(JOBS_HOME_JYMBII,aaa)"],
                     "paging": {"total": 2}}}
    read = jp.read_job_collection(both)
    assert read["ok"] is False and read["state"] == "ambiguous" and read["results"] == []


# ── fix round 1: a shorter list, a foreign id and an ununderstood form all have to say so ──
def test_a_module_wider_than_fifty_returns_every_resolvable_card():
    # The width cap `_MAX_WIDTH` bounds recursive DISCOVERY over an unknown body; applied to the
    # module's own embedded, already-parsed list it dropped resolvable cards without a word.
    wide = jp._MAX_WIDTH + 10
    ids = [str(4441501850 + i) for i in range(wide)]
    read = jp.read_job_collection(_feed_body([_module("aaa", [_wrap(i) for i in ids])],
                                             [_feed_card(i) for i in ids]))
    assert (read["ok"], read["state"], read["count"]) == (True, "hits", wide)
    assert read["lost"] == 0 and read["dropped"] == 0 and read["reason"] is None


def test_the_limit_never_cuts_cards_read_out_of_modules_and_names_what_it_does_cut():
    # `limit` is the caller's ENTRY count. On the FEED an entry is a MODULE carrying several cards,
    # so cutting cards to it threw away understood jobs that cursor paging cannot bring back.
    modules = [_module(t, [_wrap(i) for i in ids]) for t, ids in
               (("aaa", ["4441501850", "4441501851"]), ("bbb", ["4441501852", "4441501853"]))]
    cards = [_feed_card(str(4441501850 + i)) for i in range(4)]
    read = jp.read_job_collection(_feed_body(modules, cards), limit=2)
    assert (read["ok"], read["count"], read["dropped"]) == (True, 4, 0)
    # On the SEARCH route an entry IS a card, so the limit still applies — but it says so.
    search = jp.read_job_collection({"data": {"elements": [_card("1111111111"),
                                                           _card("2222222222"),
                                                           _card("3333333333")]}}, limit=2)
    assert search["count"] == 2 and search["dropped"] == 1
    assert search["reason"] and "limit=2" in search["reason"]


def test_a_feed_entity_never_gets_its_id_from_a_foreign_tracking_urn():
    # An entity carrying the measured container is a MODULE even when `$type` and urn drift; before
    # this, it fell through to the SEARCH projection, which reads the id from `trackingUrn` and
    # answered with a job that is not the one in the body.
    drifted = {"$type": "com.linkedin.voyager.dash.jobs.SomethingElse",
               "entityUrn": "urn:li:fsd_somethingElse:(JOBS_HOME_JYMBII,aaa)",
               "trackingUrn": "urn:li:jobPosting:7777777",
               "entitiesResolutionResults": [_wrap("4441501850")]}
    body = {"data": {"data": {"jobsDashJobsFeedAll": {
        "$type": _COLL, "*elements": [drifted["entityUrn"]], "paging": {"total": 1}}}},
        "included": [drifted, _feed_card("4441501850")]}
    read = jp.read_job_collection(body)
    assert [c["job_id"] for c in read["results"]] == ["4441501850"], "the card IN the body"
    assert "7777777" not in str(read["results"])


def test_a_feed_entity_whose_container_key_drifted_is_not_projected_by_the_search_route():
    # Last line of defence: all module witnesses gone, but a job branch is still one level down.
    # Reading `trackingUrn` here would answer with a foreign job id — so the form is named unread.
    drifted = {"$type": "com.linkedin.voyager.dash.jobs.SomethingElse",
               "entityUrn": "urn:li:fsd_somethingElse:(JOBS_HOME_JYMBII,aaa)",
               "trackingUrn": "urn:li:jobPosting:7777777",
               "entityResolutionResultsV2": [_wrap("4441501850")]}
    body = {"data": {"data": {"jobsDashJobsFeedAll": {
        "$type": _COLL, "*elements": [drifted["entityUrn"]], "paging": {"total": 1}}}},
        "included": [drifted, _feed_card("4441501850")]}
    read = jp.read_job_collection(body)
    assert read["ok"] is False and read["state"] == "drift" and read["results"] == []
    assert read["unread"] == 1 and "7777777" not in str(read["reason"])


def test_a_card_urn_nested_inside_a_foreign_urn_is_not_an_identity():
    # `_CARD_URN_RE` is anchored: the identity is the WHOLE entityUrn or there is none.
    nested = "urn:li:fsd_jobPostingCardUnion:(urn:li:fsd_jobPostingCard:(9999999,X),FOO)"
    card, why = jp.project_feed_job_card(_feed_card("4441501850", entityUrn=nested))
    assert card is None and "entityUrn" in why
    embedded = _module("aaa", [{"jobPostingCard": _feed_card("4441501850", entityUrn=nested)}])
    read = jp.read_job_collection(_feed_body([embedded], []))
    assert read["ok"] is False and read["state"] == "card_lost"
    assert "9999999" not in str(read["results"])


@pytest.mark.parametrize("module,witness", [
    (_module("aaa", None, entitiesResolutionResults=None), "not_a_list"),
    ({"$type": "com.linkedin.voyager.dash.jobs.JobsFeedCardModule",
      "entityUrn": "urn:li:fsd_jobsFeedCardModule:(JOBS_HOME_JYMBII,aaa)",
      "entityResolutionResultsV2": []}, "missing"),
    (_module("aaa", [{name: None for name in _UNION_BRANCHES}]), "no_filled_branch"),
    (_module("aaa", ["not-an-object"]), "not_an_object"),
])
def test_a_module_form_that_was_not_understood_is_drift_and_never_a_promotion_feed(module, witness):
    # The rejected false success one level deeper: a renamed container key or a union item with no
    # filled branch was counted as `skipped` — sold to the agent as 'understood, legitimately no
    # job'. Only the MEASURED empty list and a hidden module stay silent.
    read = jp.read_job_collection(_feed_body([module], []))
    assert (read["ok"], read["state"]) == (False, "drift"), witness
    assert read["unread"] == 1 and read["skipped"] == 0 and read["reason"]


def test_an_unread_form_next_to_a_readable_card_still_names_both():
    modules = [_module("aaa", [_wrap("4441501850")]),
               _module("bbb", [{name: None for name in _UNION_BRANCHES}])]
    read = jp.read_job_collection(_feed_body(modules, [_feed_card("4441501850")]))
    assert read["ok"] is False and read["state"] == "drift"
    assert read["count"] == 1 and read["unread"] == 1, "what WAS read stays visible"


# ── fix round 2: the chokepoint, not another witness ──
@pytest.mark.parametrize("drifted,shape", [
    ({"$type": "com.linkedin.voyager.dash.jobs.FeedModuleV2",
      "entityUrn": "urn:li:fsd_x:(A,1)",
      "trackingUrn": "urn:li:jobPosting:7777777",
      "title": {"text": "FOREIGN TITLE"},
      "sections": {"inner": [_wrap("4441501850")]}}, "job_branch_two_levels_down"),
    ({"$type": "com.linkedin.voyager.dash.jobs.FeedModuleV2",
      "entityUrn": "urn:li:fsd_x:(A,1)",
      "trackingUrn": "urn:li:jobPosting:7777777",
      "title": {"text": "FOREIGN TITLE"}}, "no_job_branch_at_all"),
])
def test_a_referenced_entity_that_is_no_module_never_reaches_the_search_projection(drifted, shape):
    # The class, not the instance: witnesses can always be out-driftet one level deeper. What is
    # decidable WITHOUT looking inside is where the entry came from — a URN in the starred
    # `*elements` list is the FEED shape, and what it names is a module. Is it not readable as one,
    # it is unread; it never gets an id from `trackingUrn`.
    body = {"data": {"data": {"jobsDashJobsFeedAll": {
        "$type": _COLL, "*elements": [drifted["entityUrn"]], "paging": {"total": 1}}}},
        "included": [drifted, _feed_card("4441501850")]}
    read = jp.read_job_collection(body)
    assert (read["ok"], read["state"], read["count"]) == (False, "drift", 0), shape
    assert read["results"] == [] and read["unread"] == 1
    assert "7777777" not in str(read) and "FOREIGN TITLE" not in str(read)


def test_the_chokepoint_leaves_the_search_route_untouched():
    # The search route never arrives through a URN string: its `elements` hold the cards inlined.
    search = jp.read_job_collection({"data": {"elements": [_card("1111111111")]}})
    assert (search["ok"], search["state"], search["count"]) == (True, "hits", 1)
    assert search["unread"] == 0


def test_an_inlined_object_inside_the_starred_list_never_becomes_a_card():
    """The route decision hangs on the container KEY, not on an entry's runtime type.

    `*elements` is the feed's shape and its entries are URNs naming modules. An entry sitting there
    inlined as an object is a form we cannot read — whatever it contains. While the decision hung on
    `isinstance(ent, str)` such an entry skipped the chokepoint and reached the search projection,
    which takes its id from `trackingUrn`: a foreign job_id and url standing next to a correctly
    read card at ok=True, with nothing marking the difference. Measured 2026-08-01.
    """
    module_urn = "urn:li:fsd_jobsFeedCardModule:(JOBS_HOME_JYMBII,m0)"
    raw = {
        "data": {"data": {"jobsDashJobsFeedAll": {
            "*elements": [module_urn, {
                "$type": "com.linkedin.voyager.dash.jobs.SomethingDrifted",
                "trackingUrn": "urn:li:jobPosting:7777777",
                "title": "FOREIGN TITLE",
                "primaryDescription": {"text": "Evil Corp · Nowhere"}}],
            "paging": {"total": 2, "count": 2, "start": 0},
            "$type": "com.linkedin.restli.common.CollectionResponse"}}},
        "included": [
            {"$type": "com.linkedin.voyager.dash.jobs.JobsFeedCardModule",
             "entityUrn": module_urn, "moduleType": "VERTICAL_LIST",
             "entitiesResolutionResults": [{"jobPostingCardWrapper": {
                 "*jobPostingCard": "urn:li:fsd_jobPostingCard:(1,JOBS_HOME_JYMBII)"}}]},
            {"$type": "com.linkedin.voyager.dash.jobs.JobPostingCard",
             "entityUrn": "urn:li:fsd_jobPostingCard:(1,JOBS_HOME_JYMBII)",
             "title": "REAL JOB", "primaryDescription": {"text": "Real GmbH · Bremen"}}],
    }
    read = jp.read_job_collection(raw)
    blob = json.dumps(read)
    assert "7777777" not in blob, "a foreign identity reached the result"
    assert "FOREIGN TITLE" not in blob, "a foreign title reached the result"
    assert read["ok"] is False, "an entry we could not read must not read as success"
    assert read["state"] == "drift"
    assert [c["job_id"] for c in read["results"]] == ["1"], "the real card is still read"
