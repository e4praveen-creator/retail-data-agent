# Milky Way reference — architecture preserved

Source: user-supplied “Introducing Milky Way Corporate Deck GTM.pdf”, December 2025, 45 pages. The source deck is reference material; it is not bundled into the Git codebase.

## User's final direction

Keep the original system architecture: one primary Retail Data Agent in LangGraph, supported by a context engine, tools, workflows/playbooks, and read-only DuckDB. The primary agent owns the conversation and flexibly decides what to inspect next. Hypothesis, EDA and RCA specialists are callable capabilities inside this same tool loop; there is no replacement mandatory stage-by-stage multi-agent pipeline. The deck informs analytical content and experience only. Use the documented dates and all-business defaults when scope is omitted, and disclose them rather than adding a blocking clarification stage.

## Relevant deck content

- Pages 5, 7–8: distinguish fact finding, standard playbooks and deep diagnosis. Hypotheses should map to required data; execution should be transparent and checked against evidence.
- Page 12: reusable hypothesis and business-term context; conversation continuity.
- Page 15: distributions, summary statistics, correlation, t-tests, ANOVA, confidence intervals and effect sizes, chosen for the data/design.
- Pages 24 and 28: iterative follow-up questions, inspectable hypotheses/SQL/results, and persistent context.
- Pages 32–34: analytical traces, explainability, feedback and statistical-method guidance.

The deck's accuracy, speed, cost and library-size claims describe that presentation's enterprise work. They are not measured claims about this new local app. The deck does not supply the complete 1K-question / 15K-hypothesis / production-code libraries. Its banking examples are outside this dataset and are not included in the retail bank.

## Dataset-specific adaptation

The app has 18 candidate hypotheses grounded in Summit Field's actual schema and MODEL.md: SKU/channel price-volume-mix, Q4 markdowns, App price-book offset, Apparel/Footwear digital returns, damaged-return cost recovery, cohort margin, anonymous customer coverage, loyalty attachment, repeat-window maturity, seasonal division mix, private-label flag, campaign eligibility, channel baskets, weekend weighting, fulfillment baskets, inventory velocity/buffers, inventory reconciliation and division contribution.

Each has named required tables, exact scope and metric basis, a runnable test, a falsifier and a limitation. They start as untested templates. Running SQL collects evidence and does not automatically mark a hypothesis true. Generator rules are identified as construction assumptions; statistical association is not promoted into causality.

## Recovered chat context

The accessible “Explain Memory Types” chat describes Milky Way RCA procedural knowledge as reusable investigation patterns from expert playbooks, validated outcomes, prior traces and corrections. This supports user-confirmed notes and a reusable hypothesis bank. The available app history tools exposed only the latest 50 chats and no full-history search; the year-plus archive was not exhaustively reviewed. The supplied PDF is the primary design reference used for this adaptation.
