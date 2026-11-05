# Diligence and evidence-based briefing

A fictional financing discussion contains three different things: a sponsor request, conditional lender interest, and a decision to undertake further diligence. An automated recap incorrectly treats the requested financing as approved.

## What the workflow preserves

The sponsor requests EUR 42 million over seven years. The lender could consider up to EUR 36 million over six years, conditional on a reconciled debt schedule. Only further diligence was authorized. The source also contains differently dated savings estimates and no agreed term-sheet deadline.

The executed demonstration records five claims with their source hashes and locations, leaving them pending. It creates request DD-010 for the reconciled debt schedule, exports a client-facing request, then archives and reconciles a synthetic response. That return becomes a proposal; the underlying tracker remains unchanged.

- [Generated claim ledger](outputs/financing-ledger.md)
- [Generated response proposal](outputs/financing-response.md)
- [Actual evaluated financing brief](outputs/financing-brief.md)
- [Original synthetic discussion](../../skills/evidence-brief/examples/financing/committee-record.md), [deck](../../skills/evidence-brief/examples/financing/concept-deck.md), and [incorrect recap](../../skills/evidence-brief/examples/financing/auto-summary.md)

The brief was generated separately from the supplied sources and reviewed against them. The ledger does not establish that its citations are true; recording a claim is separate from accepting it. This is an explicit handoff between deterministic records and source-based judgment.

## Reproduce

From the repository root, choose a new destination:

```sh
python examples/financing_evidence_demo.py /tmp/financing-evidence-example
```

The script calls the actual ledger and tracker CLIs. It sends no client message and accepts no returned response. The briefing prompt and sources are available in the evidence-brief package; model-generated wording can vary between runs.

The [document review coverage](../../skills/document-review-coverage/README.md) skill supplies a separate way to bind review records to document bytes and a fixed review scope. Coverage accounting is not proof that the underlying judgment is correct.

This case demonstrates decision-status discipline, stable identifiers, source traceability and controlled updates. No real financing, participant or client document is represented.
## Context reuse and stale evidence pilot

Run `python examples/context_evidence_demo.py /fresh/output-directory` from the
repository root. This synthetic composition runs the existing ledger handoff,
checks an authored fixture brief against its explicit sentence/quotation map,
then records the actual checker log through the artifact quality gate. Missing
checks remain INCOMPLETE; the completed fixture check is ATTESTED. Changing a
copied source invalidates that prior result. The incorrect automated recap fails
the fixture checker. The final copied source is intentionally changed.

This is reproducible fixture coverage and file-identity checking, not a general
semantic checker, model-performance benchmark, live transaction or acceptance
of the ledger's pending claims.
