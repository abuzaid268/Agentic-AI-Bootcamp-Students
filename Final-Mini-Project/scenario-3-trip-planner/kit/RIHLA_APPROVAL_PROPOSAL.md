# Approval blocker: proposal for Developer 1

From Developer 2 (auth & frontend), 2026-11-02. It builds on your own notes in `RIHLA_TEAM_HANDOFF.md` (P1, B3) on
`feature/global-data-frontend`. Nothing here changes your files: the decisions and the edits are yours.

## 1. Why real plans return `verification_required`

`/api/chat` offers a `save_trip` pending action only when the final report is `PASS` **and** its evidence basis
is `"fresh"` (`app/main.py:103-110` on `main`). `fresh` means every opening-hours and travel fact came from a live
lookup (`planning/verification.py:1013`, `_basis`). Two separate causes block it:

| Cause | Effect | Bug? |
|---|---|---|
| Replay mode (the kit default; the team's store on 8103; very likely the graders' setup) | every fact is `recorded`, so the basis is never `fresh` | No: the policy (your P1) |
| A listing without opening hours for a scheduled place | `opening_hours` is `UNKNOWN`, so the status is not `PASS` | No: a data gap |

Real runs on 2026-11-02 (integration branch, OpenRouter, patched Travel API), with 0 confirmed problems in every run:

| Run | Mode | Status | Basis | Not PASS |
|---|---|---|---|---|
| Amman 4 days, three users | replay | UNKNOWN | recorded | hours, travel, walking, budget, costs |
| Amman 4 days, three users | live | UNKNOWN | mixed | hours, budget, costs |
| Istanbul 3 days | live | UNKNOWN | mixed | hours only: 2 places (Bereket Döner, Eyüp Mosque) |

The activity pace has no effect on this: the run without a pace fails exactly like the relaxed and packed ones.

## 2. What the official contract expects

`common/CONTRACT.md` §2-3 and `evals/cases.sample.jsonl`:

* `pending_action` (one at a time, with a `summary` that says exactly what will be saved) whenever a plan is
  proposed for saving. **S3-01, 02, 04, 05, 08 and 09 expect `save_trip`**; S3-02/04/05/09 then expect
  `result.trip_id` and one trip in `GET /admin/trips`.
* `approved: false` writes nothing and `/admin/trips` stays empty (S3-03). No trip may appear without approval
  (S3-01, 06, 07, 08, 10 check `len: 0`).
* The write is your code over MCP with `Idempotency-Key = action_id`; a repeated approval writes once.
* `/api/approve` answers a ChatResponse (`reply`, `result`), already done on your branch.

So with today's gate, every approval case fails in replay mode, whatever the plan quality.

## 3. Recommendation: adopt your P1 table, with one strict line

1. **Keep `VerificationReport.verified` exactly as it is** (`PASS` + `fresh`). Never call recorded data verified.
2. **Approvable = `status == "PASS"` and coverage sufficient**, whatever the basis. The pending action carries
   `verification_basis: "live" | "recorded"`. The reply, the `summary` and the dashboard state the basis ("checked
   against recorded data from <date>, not live sources").
3. **`UNKNOWN` is never approvable and never shown as PASS.** A plan with a place whose hours are unknown gets no
   `pending_action`; the reply lists what could not be checked. (If the team ever wants to relax this, do it per
   finding code with the findings listed in the summary, never by mapping UNKNOWN to PASS.)
4. `/api/approve` keeps refusing anything that was not `PASS` when it was proposed (the hash check stays).

Field to send: keep `verification_status: "verified"` only for the live basis, and use
`"verified_on_records"` for the recorded one. The frontend change is two lines (section 6).

## 4. "Save Unverified Draft" can coexist, as long as it is not a Trip Store write

* It already exists and is honest: the dashboard's Save keeps a **local draft** (labelled "Draft · Not verified"),
  and its PDF is marked "Draft - Not Verified" on every page.
* It must **never** go through `save_trip` or `/api/trips`. The graders count `GET /admin/trips` (S3-01, 03, 06,
  07, 08 and 10 expect 0, even with a plan waiting for approval). A draft in the store would fail them and would
  look approved in My Trips.
* If drafts must follow the account across devices, that is a separate store collection (Developer 3), not trips.

## 5. Keep the verification warnings

* In the response: keep `verification` (status, state, counts, findings) next to the itinerary, as today.
* In the approval: the `summary` names the basis and the number of advice items. The saved itinerary keeps its
  `notes` (e.g. "Opening hours unknown: check before you go").
* The PDF already prints the verdict and up to 12 findings, and marks drafts.

## 6. Keep the pending approval when unrelated messages arrive (your B3)

On `main`, `app/main.py:75-79` saves the previous pending action, clears it, and restores it only for a revision
that changed nothing. Any other message without a new plan (a question, "what's the weather?", "remember I'm
vegetarian", a clarification) still destroys it, and a later Approve gets 404.

Fix: clear or replace `session["pending_action"]` **only** when this response carries a new itinerary: replace it
with the new action when the new plan is approvable, clear it otherwise. Every response without an itinerary keeps
the previous one. Test: chat → pending; chat "what's the weather?"; approve with the first `action_id` → saved.

## 7. Branch integration, in order

1. Merge `feature/global-data-frontend` into `main` (12 files conflict, mostly yours; for the frontend, see 8).
2. Review and merge `feature/auth-backend-integration` (`d8e52c3`: `install_auth`, per-user traveller for approve
   and My Trips). On a signed-in request the traveller must be `traveller_id_for_request()`, never the body's
   `user.traveller_id` (that stays for anonymous contract calls).
3. P1 and B3 as above.
4. `feature/activity-pace-integration` comes last, after your and Developer 3's review.

## 8. Frontend: what Developer 2 will do after your merge

Both lines have their own approval UI: `main` (`tripApi.approveTrip`, `myTrips.js`, `pdfExport.js`) and yours
(`approval.js`, `tripPdf.js`, `tripExport.js`). When merging, keep **one**: `approval.js` (it understands both
answer shapes and has Reject) together with main's `myTrips.js` and `pdfExport.js` (Trip Store listing, labelled
PDF). Then Developer 2 will:

| Item | Change | Where |
|---|---|---|
| Reject | Keep your Reject button and `sendApproval({approved: false})`; after it, show "Not saved" and drop the pending action | `TripDashboard.jsx` |
| Expired session | `await requireSession(response)` before the `!response.ok` check (helper ready on `feature/auth-frontend`, `auth/authApi.js`); pages catch `AuthRequiredError` → `useAuth().sessionExpired(retry)` | `approval.js` `sendApproval`, `tripApi.js` `getJson` and `reviseTrip`, `MyTrips.jsx` load, `TripDashboard.jsx` approve and revise |
| Pending approval | Show "Verified · Awaiting your approval" (live) or "Checked against recorded data, not live sources" (`verified_on_records`); after B3, stop hiding Approve after every message | `approval.js` `approvalOptions`, `tripResult.js` `getVerificationState`, `TripDashboard.jsx` |
| My Trips | Loading, empty, error and Try again exist; add the 401 → log-in-again path | `MyTrips.jsx` |
| Saved-trip PDF | Works from the store record alone (test `savedTripPdf.test.js`) | none |
