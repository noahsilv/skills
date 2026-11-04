# Document review record reconciliation

Source/inventory binding: **CURRENT**. Coverage: **COMPLETE**.
Judgment conclusion: **NOT_ASSESSED**.

Counts measure valid submitted records, not review quality. Exact quotations establish text presence only. Factual support, judgment correctness, response adequacy, and implementation of proposed changes are NOT_ASSESSED.

Current source:

    draft.md

Current source SHA-256: `13ce0e3cf38b5f9c8cde568b3c2f3f98bcd6b002a193e93cbeee952b20201e09`
Source SHA-256 recorded in inventory: `13ce0e3cf38b5f9c8cde568b3c2f3f98bcd6b002a193e93cbeee952b20201e09`
Source SHA-256 recorded in ledger: `13ce0e3cf38b5f9c8cde568b3c2f3f98bcd6b002a193e93cbeee952b20201e09`

Current inventory file SHA-256: `643d63b63a44fea8ce9bd9e099122187beb4ff31ed9abea5d634b6f3b663a75b`
Inventory file SHA-256 recorded in ledger: `643d63b63a44fea8ce9bd9e099122187beb4ff31ed9abea5d634b6f3b663a75b`

Expected unit/check pairs: 8. Submitted records: 8. Valid unique pairs: 8.
Excluded blank physical lines: 3. No content block is exempted by the program.

## Inventory

| Unit | Physical lines | Unit SHA-256 |
| --- | --- | --- |
| U0001 | 1–1 | `d397ef467202ccd84cfcccca12c916e11d3c7cf587dc6852ab26596aad18ec6b` |
| U0002 | 3–3 | `3a95dbb966b1b2f4fbcd4a8194fb7e2e838e5bcbe9a4f78ea181bd1b5513c28c` |
| U0003 | 5–5 | `c57b7b3f8861a2747802707ec704f5d3d65ea9dda5ac61d1839fcaeef5a81f25` |
| U0004 | 7–7 | `e6e3516b8a630835f4de66440c50e47357ed1d93623b3a57835500657223ff9d` |

## Missing records

None among the declared unit/check pairs.

## Mechanical diagnostics

No mechanical exceptions found within the documented checks.

## Review work

Recorded reviewer statuses: {"closed": 6, "open": 1, "responded": 1}.
Records needing a person to assess a proposal, evidence gap, open response, or invalid/stale record: 6, 8.
Closed is a ledger status with a supplied resolution note. It does not prove a response was accepted or a change was implemented.

## Reviewer records (as supplied)

### Record 1 — counted

    {
      "unit_id": "U0001",
      "check": "clarity",
      "reviewer": "Synthetic reviewer",
      "verdict": "no-change",
      "quote": "# Synthetic component rollout note",
      "comment": "The heading names the subject of this short note.",
      "status": "closed",
      "resolution": "Assessment recorded; no source edit claimed."
    }

### Record 2 — counted

    {
      "unit_id": "U0001",
      "check": "source-support",
      "reviewer": "Synthetic reviewer",
      "verdict": "not-applicable",
      "quote": "# Synthetic component rollout note",
      "comment": "This heading labels the synthetic note and makes no rollout or cost claim.",
      "status": "closed",
      "resolution": "Assessment recorded; no source edit claimed."
    }

### Record 3 — counted

    {
      "unit_id": "U0002",
      "check": "clarity",
      "reviewer": "Synthetic reviewer",
      "verdict": "no-change",
      "quote": "The current test group includes 24 accounts.",
      "comment": "The sentence clearly distinguishes the current test group from the wider rollout.",
      "status": "closed",
      "resolution": "Assessment recorded; no source edit claimed."
    }

### Record 4 — counted

    {
      "unit_id": "U0002",
      "check": "source-support",
      "reviewer": "Synthetic reviewer",
      "verdict": "no-change",
      "quote": "The current test group includes 24 accounts.",
      "comment": "The supplied note states the same test-group count.",
      "status": "closed",
      "resolution": "Assessment recorded; no source edit claimed.",
      "support": [
        {
          "source_id": "NOTE",
          "quote": "The current test group includes 24 accounts.",
          "locator": "Synthetic planning decision"
        }
      ]
    }

### Record 5 — counted

    {
      "unit_id": "U0003",
      "check": "clarity",
      "reviewer": "Synthetic reviewer",
      "verdict": "no-change",
      "quote": "The 120-account rollout is approved for 18 June.",
      "comment": "The sentence is readily understandable. Its approval status is assessed in the separate source-support record.",
      "status": "closed",
      "resolution": "Assessment recorded; no source edit claimed."
    }

### Record 6 — counted

    {
      "unit_id": "U0003",
      "check": "source-support",
      "reviewer": "Synthetic reviewer",
      "verdict": "revise",
      "quote": "The 120-account rollout is approved for 18 June.",
      "comment": "The source describes a proposal and defers approval. The current wording overstates the decision.",
      "status": "open",
      "proposed_text": "The 120-account rollout is proposed for 18 June, subject to a capacity test.",
      "support": [
        {
          "source_id": "NOTE",
          "quote": "A wider rollout to 120 accounts is proposed for 18 June, subject to a capacity test. Approval of the wider rollout is deferred until the test result is reviewed.",
          "locator": "Synthetic planning decision"
        }
      ]
    }

### Record 7 — counted

    {
      "unit_id": "U0004",
      "check": "clarity",
      "reviewer": "Synthetic reviewer",
      "verdict": "no-change",
      "quote": "Monthly hosting is estimated at 4,000 credits, excluding support and tax.",
      "comment": "The cost sentence names the monthly period and both exclusions.",
      "status": "closed",
      "resolution": "Assessment recorded; no source edit claimed."
    }

### Record 8 — counted

    {
      "unit_id": "U0004",
      "check": "source-support",
      "reviewer": "Synthetic reviewer",
      "verdict": "no-change",
      "quote": "Monthly hosting is estimated at 4,000 credits, excluding support and tax.",
      "comment": "Please confirm that support is excluded.",
      "status": "responded",
      "response": "The supplied planning note excludes support and tax. This reply is recorded; reviewer acceptance is not established.",
      "support": [
        {
          "source_id": "NOTE",
          "quote": "The hosting estimate is 4,000 credits per month, excluding support and tax.",
          "locator": "Synthetic planning decision"
        }
      ]
    }

