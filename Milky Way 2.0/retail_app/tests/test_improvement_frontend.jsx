import React from "react";
import { renderToString } from "react-dom/server";
import assert from "node:assert/strict";
import { api } from "../frontend/api.js";
import { ChatApp, Answer } from "../frontend/chat.jsx";
import { AnswerReport } from "../frontend/answer-report.jsx";
import {
  ImproveWorkspace,
  AssetEditor,
  CaseEditor,
  EvaluationResults,
  FeedbackForm,
  ScopeEditor,
  Validation,
  WhyThisAnswer,
  newContent,
  draftFrom,
  parseExpectedValue,
  validateChatDates,
  filterValue,
  contextExcerpt,
  metricUnits,
} from "../frontend/improve-workspace.jsx";
const render = (component) => renderToString(component);
const noop = () => {};
const shell = render(<ChatApp />);
assert(shell.includes("Improve workspace"));
assert(shell.includes('aria-label="Answer style"'));
const admin = render(<ImproveWorkspace onBack={noop} />);
for (const label of [
  "Knowledge &amp; ontology",
  "Skills",
  "Answer design &amp; examples",
  "Evaluations",
  "Feedback &amp; releases",
  "Local admin workspace",
  "User &amp; admin guide",
  "Loading the versioned workspace",
])
  assert(admin.includes(label), label);
assert(admin.includes('href="/guide"'));
const builtin = {
  id: "skill-trend",
  kind: "skill",
  name: "Sales trend",
  built_in: true,
  content: {
    description: "Measure sales",
    method: "Use measured data",
    approved_tools: ["query_retail"],
    handler: "playbook:trend",
    output_profile_id: "business-review",
  },
};
const caps = {
  tools: ["query_retail"],
  profiles: ["business-review"],
  handlers: ["method_only", "playbook:trend"],
  measures: ["sales_cents"],
  dimensions: ["channel_name"],
};
const asset = render(
  <AssetEditor
    asset={builtin}
    capabilities={caps}
    onSaved={noop}
    onCancel={noop}
  />,
);
assert(asset.includes("Duplicate built-in"));
assert(asset.includes('disabled=""'));
assert(!asset.includes("Save draft"));
assert(asset.includes("This form cannot upload executable code"));
const draft = {
  id: "metric-custom",
  name: "Sales after returns",
  kind: "ontology",
  built_in: false,
  draft_revision: 7,
  draft: {
    revision: 7,
    content: {
      concept_type: "metric",
      description: "Track cohort sales",
      measure: "sales_cents",
      units: "cents",
      return_basis: "sales_cohort",
      date_basis: "sale_date",
      aliases: ["realized sales"],
    },
  },
};
const edit = render(
  <AssetEditor
    asset={draft}
    capabilities={caps}
    onSaved={noop}
    onCancel={noop}
  />,
);
for (const field of [
  "Which approved measure supports it?",
  "Set by the approved calculation",
  "Returns basis",
  "Save draft",
  "Validate saved version",
  "Preview saved draft",
])
  assert(edit.includes(field), field);
assert.deepEqual(draftFrom(draft).content, draft.draft.content);
const copy = draftFrom(draft);
copy.content.aliases.push("changed");
assert.equal(
  draft.draft.content.aliases.length,
  1,
  "editor must not mutate asset records",
);
const knowledge = newContent("knowledge");
assert.equal(knowledge.body, "");
assert(!("text" in knowledge));
const profile = newContent("output_profile");
assert.equal(profile.required_sections.length, 7);
assert(profile.show_evidence && profile.show_scope && profile.show_limitations);
assert.equal(parseExpectedValue("42"), 42);
assert.equal(parseExpectedValue("false"), false);
assert.equal(parseExpectedValue("sales_cents"), "sales_cents");

assert(
  validateChatDates({
    start: "2025-01-05",
    end: "2025-12-27",
    compare_start: "2024-01-07",
    compare_end: "2024-12-28",
  }),
);
assert.throws(
  () =>
    validateChatDates({
      start: "2025-01-06",
      end: "2025-12-27",
      compare_start: "2024-01-07",
      compare_end: "2024-12-28",
    }),
  /equal numbers/,
);
assert.throws(
  () =>
    validateChatDates({
      start: "2025-01-01",
      end: "2025-03-31",
      compare_start: "2024-01-01",
    }),
  /both comparison/,
);
assert.equal(filterValue("false", "bool"), false);
assert.throws(() => filterValue("yes", "bool"), /true or false/);
assert.throws(() => filterValue("1.5", "int"), /whole numbers/);
assert.equal(
  contextExcerpt(
    '{"description":"Meaning","body":"Trusted guidance","aliases":["term"]}',
  ),
  "Meaning\n\nTrusted guidance\n\nAlso called: term",
);
assert.equal(metricUnits("sales_cents"), "cents");
assert.equal(metricUnits("aov_cents"), "cents/order");
assert.equal(metricUnits("return_rate_pct"), "percent");
const checks = render(
  <Validation
    value={{
      valid: false,
      errors: [{ field: "measure", message: "Needs data support." }],
    }}
  />,
);
assert(checks.includes('role="status"'));
assert(checks.includes("Needs data support."));
const caseEditor = render(
  <CaseEditor
    cases={[
      {
        id: "case-1",
        name: "Definitions",
        question: "What is sales?",
        contract: { type: "retrieval", inputs: { query: "sales" } },
        expected: { min_length: { sources: 1 } },
        asset_ids: ["metric-sales"],
      },
    ]}
    onChange={noop}
  />,
);
for (const field of [
  "Check type",
  "Pass conditions",
  "Assets covered by this case",
  "Expected values stay outside model context.",
  "Advanced test inputs",
  "workspace profile",
  "workspace skill",
  "session_scope.metric",
])
  assert(caseEditor.includes(field), field);
const compare = render(
  <EvaluationResults
    run={{
      id: "run-1",
      status: "completed",
      mode: "deterministic",
      total_cases: 1,
      completed_cases: 1,
      coverage: {
        changed_assets: [{ id: "metric-custom", name: "Custom metric" }],
        uncovered_assets: ["metric-custom"],
        note: "Review applicability.",
      },
      results: [
        {
          case_id: "c1",
          name: "Scope drift",
          category: "scope",
          baseline: {
            status: "passed",
            checks: [
              {
                name: "Scope match",
                passed: true,
                detail: "Original sale dates",
              },
            ],
            output: { scope: "expected" },
          },
          candidate: {
            status: "failed",
            checks: [
              {
                name: "Scope match",
                passed: false,
                detail: "Wrong date basis",
              },
            ],
            failures: ["Wrong date basis"],
            output: { scope: "wrong" },
          },
          diff: { output_changed: true, regression: true },
          review_status: "pending",
        },
      ],
    }}
  />,
);
for (const value of [
  "Baseline",
  "Candidate",
  "Wrong date basis",
  "Fail",
  "Missing explicit case coverage",
  "metric-custom",
  "Output and measured evidence",
])
  assert(compare.includes(value), value);
const provenance = render(
  <WhyThisAnswer
    result={{
      id: "a1",
      session_scope: {
        dates: { start: "2025-01-01", end: "2025-03-31" },
        metric: "sales_cents",
        return_basis: "sales_cohort",
        filters: [{ field: "channel_name", op: "eq", values: ["Web"] }],
      },
      workspace: {
        release_id: "release-pinned",
        output_profile_id: "analyst-detail",
        skill_versions: { "skill-margin": "version-7" },
        asset_versions: { "metric-sales": "version-2" },
        context_sources: [],
      },
      context: [
        {
          source_id: "D1",
          title: "Retail definitions",
          text: "Revenue is before returns.",
          role: "metric_contract",
        },
      ],
      outputs: [{ evidence_id: "E1", name: "Sales", row_count: 3, rows: [] }],
    }}
  />,
);
for (const value of [
  "release-pinned",
  "analyst-detail",
  "skill-margin",
  "Revenue is before returns.",
  "E1",
  "Web",
  "sales cohort",
])
  assert(provenance.includes(value), value);
const feedback = render(<FeedbackForm onSubmit={noop} onCancel={noop} />);
assert(feedback.includes("citation"));
assert(feedback.includes("Save for review"));
assert(feedback.includes("Choose the issues"));
const scopeEditor = render(
  <ScopeEditor
    scope={{
      dates: { start: "2025-01-01", end: "2025-12-31" },
      metric: "sales_cents",
      filters: [{ field: "channel_name", op: "eq", values: ["Web"] }],
    }}
    capabilities={{
      measures: ["sales_cents"],
      filters: { channel_name: { type: "text", operators: ["eq", "in"] } },
      return_bases: { before_returns: "Before returns" },
    }}
    onSave={noop}
  />,
);
for (const value of [
  "Current start",
  "Comparison start",
  "Returns basis",
  "Remove filter 1",
  "Add filter",
  "Apply scope",
  "Web",
])
  assert(scopeEditor.includes(value), value);
const result = {
  id: "a1",
  mode: "playbook",
  outputs: [
    {
      evidence_id: "E1",
      name: "Measured rows",
      row_count: 8,
      rows: Array.from({ length: 8 }, (_, i) => ({
        category: `Product ${i + 1}`,
        sales_cents: (i + 1) * 100,
      })),
    },
  ],
  presentation: {
    headline: "Measured headline",
    scope: "2025",
    metric_basis: "USD cents",
    interpretation: "Measured interpretation",
    limitations: ["Material limitation"],
    next_questions: ["What next?"],
    supporting_evidence_ids: ["E1"],
    display: {
      detail_level: "concise",
      table_rows: 5,
      chart_preference: "table",
      show_sources: true,
    },
    sources: ["fixture"],
  },
};
const report = render(
  <AnswerReport result={result} renderText={(t) => <p>{t}</p>} />,
);
assert(report.includes("Product 5"));
assert(!report.includes("Product 6"));
assert(report.includes("Show all 8 returned values"));
assert(report.includes("Material limitation"));
assert(report.includes('data-output-structure="playbook-seven-sections"'));
assert(report.includes("prefers the measured supporting table"));
const answer = render(
  <Answer message={{ text: "Answer", analysis: result }} onFeedback={noop} />,
);
assert(answer.includes("Why this answer?"));
assert(answer.includes("Needs improvement"));
const originalFetch = globalThis.fetch;
try {
  let received;
  globalThis.fetch = async (url, opts) => {
    received = { url, opts };
    return new Response(JSON.stringify({ id: "asset-1" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  await api(
    "/workspace/assets/asset-1",
    { expected_revision: 4, content: { description: "Update" } },
    { method: "PUT" },
  );
  assert.equal(received.url, "/api/workspace/assets/asset-1");
  assert.equal(received.opts.method, "PUT");
  assert.equal(JSON.parse(received.opts.body).expected_revision, 4);
  assert.equal(received.opts.headers["X-Retail-App"], "local");
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        detail: {
          code: "stale_revision",
          message: "This draft changed. Reload before saving.",
          errors: [{ field: "revision", message: "Stale draft" }],
        },
      }),
      { status: 409, headers: { "content-type": "application/json" } },
    );
  await assert.rejects(
    () => api("/workspace/assets/asset-1", {}),
    (err) =>
      err.status === 409 &&
      err.code === "stale_revision" &&
      err.message.includes("Reload") &&
      err.errors[0].field === "revision",
  );
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: [{ msg: "Invalid scope" }] }), {
      status: 422,
      headers: { "content-type": "application/json" },
    });
  await assert.rejects(
    () => api("/conversations/c1/scope", {}, { method: "PATCH" }),
    /Invalid scope/,
  );
} finally {
  globalThis.fetch = originalFetch;
}
console.log(
  "Improve workspace authoring, comparisons, profile rendering, provenance, scope, feedback and API conflict tests passed.",
);
