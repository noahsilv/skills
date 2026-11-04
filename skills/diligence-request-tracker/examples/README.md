# Synthetic client roundtrip

`inputs/requests.json` has three diligence requests with deliberately nonsequential
IDs. Each has a synthetic private note. `inputs/returned.csv` contains two changed
responses and one unchanged request. Its formula-like second response is a
literal string used to exercise export safety.

Run `python examples/run_demo.py NEW_DIRECTORY` from the package root. The runner
calls the actual CLI to initialize, export, archive, reconcile, apply simulated
review decisions and export round 2. It asserts that private notes do not appear
in either client file and that the surviving IDs remain `REQ-040` and `REQ-090`.

`outputs/` contains a generated client export, round manifests, the unchanged
initial tracker, response proposals, a simulated review, the final tracker and
validation counts. `outputs/archive/` preserves the original return bytes under
their SHA-256. Only client CSVs belong in client delivery; all other artifacts
are internal review material.

The demonstration does not open referenced evidence or establish response
adequacy. Every name, date, request and decision is invented. In operational use,
decisions must reflect an authorized review, and closure requires an explicit
decision about that request.
