# E2E Cases

Filesystem-driven cases for the POST-only `/message` e2e harness.

The checked-in sample case uses fictional `example` country data only. Do not
commit real certificates or real-person narratives as fixtures.

## Layout

```text
e2e_cases/
  <country>/
    real/
      <case_id>/
        narrative.txt
        certificate.png|certificate.jpg|certificate.jpeg|certificate.pdf
        expected.json
    fake/
      <case_id>/
        narrative.txt
        expected.json
```

`narrative.txt`, `certificate.*`, and `expected.json` are optional, but each
case should produce at least one `/message` POST. To test a certificate locally,
drop a file named `certificate.png`, `certificate.jpg`, `certificate.jpeg`, or
`certificate.pdf` into the case folder.

## Expected JSON

```json
{
  "expected_outcome": "accept",
  "http_status": 200,
  "min_response_chars": 1,
  "accept_indicators": ["forwarded to GiveLight", "Verification passed"],
  "reject_indicators": ["human review", "did not meet", "flagged"],
  "response_contains": ["optional required text"],
  "response_contains_any": ["one", "of these"],
  "response_not_contains": ["forbidden text"]
}
```

`expected_outcome` is either `accept` or `reject`. For older fixtures,
`should_pass: true` maps to `accept`, and `should_pass: false` maps to `reject`.

The preferred actual outcome source is the structured death-certificate tool
result returned by `/message` debug mode. Enable it locally with:

```bash
uv run python scripts/e2e_cases.py --debug-tools
```

For deployed services, the Cloud Run service must also have:

```text
ENABLE_E2E_DEBUG=true
```

`--debug-tools` sends `X-E2E-Debug: true`. The API returns debug data only when
both the header and environment gate are enabled.

When tool debug output is present, the latest `death_certificate_verification`
result drives metrics:

```text
accepted true  -> actual accept
accepted false -> actual reject
accepted null  -> unknown
```

Without tool debug output, the harness falls back to deriving the actual outcome
from the final response body. Per-case `accept_indicators` and
`reject_indicators` override the defaults. If neither side matches, or both
sides match, the outcome is `unknown` and the case fails for metric purposes.

Default accept indicators:

```text
forwarded to GiveLight
Verification passed
verified
approved
accepted
eligible
```

Default reject indicators:

```text
human review
did not meet
flagged
cannot verify
can't verify
no document
verification failed
not eligible
rejected
```

## Stats

Reports include overall and per-country stats:

```text
TP = expected accept + actual accept
TN = expected reject + actual reject
FP = expected reject + actual accept
FN = expected accept + actual reject
UNKNOWN = no clear actual outcome
```

Accuracy is `(TP + TN) / classified`, where classified excludes unknown cases.
Unknown count is still reported.

In remote `--base-url` mode, local certificate files are not uploaded. To send a
media turn to a remote service, include a pre-existing Meta media ID:

```json
{
  "expected_outcome": "accept",
  "media_id": "meta-media-id",
  "mime_type": "image/jpeg"
}
```

If a case has a local certificate file and no `media_id`, remote mode marks the
media turn skipped, fails the case, and classifies it as `UNKNOWN`. This avoids
accidentally measuring a narrative-only request as a certificate test.

## Commands

Run locally against a uvicorn server started by the harness:

```bash
uv run python scripts/e2e_cases.py
```

Run against an existing deployed service:

```bash
uv run python scripts/e2e_cases.py --base-url https://example.run.app
```

Useful filters:

```bash
uv run python scripts/e2e_cases.py --country example --kind real
```

Reports are written under `e2e_runs/`.
