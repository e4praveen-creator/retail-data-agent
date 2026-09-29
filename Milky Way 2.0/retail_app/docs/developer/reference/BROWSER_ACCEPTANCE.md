# Improvement workspace browser acceptance

Date: 2026-09-26. Browser: Codex in-app browser, desktop 1280×720 and narrow 390×844. Local URL `http://127.0.0.1:8766`. State isolated in `retail_app/tmp/browser-acceptance-state`; the normal application's existing state was not used. Model credentials disabled. The operator labels below explicitly say automated browser acceptance and do not claim independent human review.

## Verified interactions

1. Created **Acceptance: lunar service policy** through the source-document form, including two aliases. Saved the draft, ran validation and retrieved it by its example question. Draft preview showed its frozen version and kept the active release at `release-baseline`.
2. Created **Acceptance release — lunar policy** from the selected draft. Ran the complete enterprise suite against baseline and candidate: **76 baseline passes, 76 candidate passes, zero hard failures, zero regressions**. The UI exposed the missing explicit case-to-asset coverage and the fact that live semantic quality was not tested.
3. Recorded an automated acceptance review with that limitation. A first publication was correctly refused because code changed after evaluation. Repeated the complete comparison with stable code; run `3b85947a-b3c2-4df7` (ID prefix) passed, was reviewed, and activated candidate `release-fbe9d5f2008544958c0c`. Used **Restore this release** to return the active pointer to `release-baseline`.
4. Duplicated the read-only **Analyst detail** profile, changed it to **Quick answer** and **Prefer a table**, saved it and ran the measured January–March 2025 preview. The preview displayed the concise profile, actual warehouse values, source units, scope and limitations. Its narrow preview retained the measured table.
5. On the 390-pixel viewport, added the Web channel filter and changed the return basis through the scope dialog. Native keyboard date controls responded to Tab/Right/Up/Down. A scope discrepancy found during this check was fixed: unequal comparison durations are now rejected before saving; the backend was also tightened separately. Corrected scope submitted successfully.
6. Ran a measured local trend playbook with the saved Web filter. Opened **Why this answer?**, showing the baseline release, Business review profile and selected trend skill. Submitted structured explanation feedback, opened its admin inbox item, marked it reviewed, and converted it into a live-answer regression draft with expected-result review still required. The original answer/evidence stayed linked.
7. Narrow admin navigation, search and asset cards remained readable. DOM measurement showed `scrollWidth=390` and viewport width `390` (no horizontal page overflow). The temporary viewport override was reset. Browser developer logs contained no JavaScript errors at the end of the flow.

## Screenshots

- [Published release](improve-release-published.png)
- [Measured profile preview](improve-profile-preview.png)
- [Mobile admin workspace](improve-mobile.png)
- [Feedback-to-regression editor](improve-feedback-regression.png)

## Fixes prompted by acceptance

- Reject incompatible comparison dates in the scope editor instead of allowing a successful scope save followed by chat rejection.
- Keep session scope after synchronous local responses by hydrating the full conversation when the response lacks session state.
- Read `session_scope` for complete answer provenance, including metric, return basis and filters.
- Show detailed publication gate failures from the structured API error envelope.
- Render custom business source excerpts as readable guidance while keeping exact structured provenance expandable.
- Choose canonical metric units automatically from approved measure names.

The final fixes were covered by the frontend regression suite and a new production bundle. Date rejection and corrected submission were also rechecked in the browser. Live model quality, multi-user authorization, external deployment and Docker acceptance were outside this browser run. Evaluation cancellation and interruption are covered by backend tests; this browser run did not claim cancellation timing coverage.
