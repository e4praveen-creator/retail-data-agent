import React from "react";
import { renderToString } from "react-dom/server";
import { ChatApp, Answer, Rich } from "../frontend/chat.jsx";
import { Chart, Evidence } from "../frontend/app.jsx";
import { QueryChart } from "../frontend/app.jsx";
import { api, conversationMarkdown } from "../frontend/api.js";
import fs from "node:fs";
import assert from "node:assert/strict";
const reports = JSON.parse(
  fs.readFileSync(
    new URL("../tmp/frontend-fixtures.json", import.meta.url),
    "utf8",
  ),
);
const shell = renderToString(<ChatApp />);
assert(shell.includes("What would you like to understand?"));
assert(shell.includes("Message Retail Agent"));
assert(shell.includes("Hypothesis bank"));
for (const r of reports) {
  const html = renderToString(
    <Evidence
      result={{
        id: "test",
        question: r.title,
        mode: "playbook",
        answer: r.summary,
        report: r,
        period: r.period,
        outputs: r.outputs,
        warnings: r.warnings,
      }}
      onOpenDoc={() => {}}
    />,
  );
  assert(html.includes(r.title.replaceAll("&", "&amp;")), r.slug);
  renderToString(<Chart slug={r.slug} outputs={r.outputs} period={r.period} />);
}
const safe = renderToString(
  <Rich text={"<script>alert(1)</script>\n\n[link](javascript:alert(1))"} />,
);
assert(!safe.includes("<script>"));
assert(!safe.includes('href="javascript:'));
const externalImage = renderToString(
  <Rich text="![Source illustration](https://example.com/image.png)" />,
);
assert(!externalImage.includes("<img"));
assert(externalImage.includes("Source illustration"));
const markdownTable = renderToString(
  <Rich text={"| Category | Sales |\n| --- | ---: |\n| Apparel | $120 |"} />,
);
assert(markdownTable.includes("<table>"));
assert(markdownTable.includes("Apparel"));
const references = renderToString(
  <Rich
    text="Measured [E1], reference [D1], unknown [E2]."
    references={{ E1: {}, D1: {} }}
    onReference={() => {}}
  />,
);
assert.equal((references.match(/inline-reference/g) || []).length, 2);
assert(references.includes("unknown [E2]"));
const moneyChart = renderToString(
  <QueryChart
    spec={{ kind: "bar", x: "category", y: "sales_cents" }}
    output={{
      evidence_id: "E1",
      rows: [{ category: "Apparel", sales_cents: 12345 }],
    }}
  />,
);
assert(moneyChart.includes("Sales (USD) by Category"));
assert(moneyChart.includes('role="figure"'));
const answer = renderToString(
  <Answer
    message={{
      text: "Measured answer",
      analysis: {
        id: "test",
        mode: "agent",
        outputs: [],
        specialists: [
          {
            role: "hypothesis",
            answer: "An untested hypothesis",
            evidence_ids: [],
          },
        ],
      },
    }}
    onPlaybook={() => {}}
    onDocument={() => {}}
    onFollowUp={() => {}}
  />,
);
assert(answer.includes("Hypotheses"));
assert(answer.includes("Evidence &amp; SQL"));
assert(answer.includes('aria-label="Copy answer"'));
const exported = conversationMarkdown({
  title: "Margin review",
  messages: [
    { role: "user", text: "Why?" },
    {
      role: "assistant",
      text: "Measured result [E1].",
      analysis: {
        id: "a1",
        specialists: [{ role: "rca", answer: "The alternatives remain open." }],
        outputs: [
          {
            evidence_id: "E1",
            name: "sales",
            sql: "SELECT 1",
            rows: [{ result: 1 }],
            row_count: 1,
          },
        ],
        warnings: ["Synthetic data"],
      },
    },
  ],
});
assert(exported.includes("# Margin review"));
assert(exported.includes("## You"));
assert(exported.includes("The alternatives remain open."));
assert(exported.includes("SELECT 1"));
assert(exported.includes("Note: Synthetic data"));

const originalFetch = globalThis.fetch;
try {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/conversations/c1");
    assert.equal(options.method, "DELETE");
    assert.equal(options.headers["X-Retail-App"], "local");
    return new Response(JSON.stringify({ deleted: true }), {
      headers: { "content-type": "application/json" },
    });
  };
  assert.deepEqual(
    await api("/conversations/c1", undefined, { method: "DELETE" }),
    { deleted: true },
  );
  globalThis.fetch = async () =>
    new Response("<html>private error detail</html>", {
      status: 503,
      headers: { "content-type": "text/html" },
    });
  await assert.rejects(api("/status"), /could not be completed \(503\)/);
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ detail: [{ msg: "Date must be in range" }] }),
      { status: 422, headers: { "content-type": "application/json" } },
    );
  await assert.rejects(api("/chat", {}), /Date must be in range/);
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(api("/status"), /local app is unreachable/);
  globalThis.fetch = async () =>
    new Response("bad", { headers: { "content-type": "application/json" } });
  await assert.rejects(api("/status"), /unreadable response/);
  globalThis.fetch = async (url) => {
    assert.equal(url, "/api/conversations/c1/investigation");
    return new Response("null", {
      headers: { "content-type": "application/json" },
    });
  };
  assert.equal(await api("/conversations/c1/investigation"), null);
} finally {
  globalThis.fetch = originalFetch;
}
console.log(
  "Frontend passed: chat shell, all 19 report/evidence paths, specialist controls, safe GFM Markdown, verified citations, USD chart labels, full-chat Markdown export, and API network/non-JSON/validation error handling. No browser layout/interaction claim.",
);
