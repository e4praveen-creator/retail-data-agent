export const ISSUE_TYPES = [
  "scope",
  "definition",
  "calculation",
  "citation",
  "chart",
  "explanation",
  "other",
];
export const KINDS = {
  knowledge: "Source document",
  ontology: "Business concept",
  skill: "Skill",
  output_profile: "Answer profile",
  example: "Answer example",
  evaluation_suite: "Evaluation suite",
};
export const list = (value) =>
  Array.isArray(value)
    ? value
    : value && typeof value === "object"
      ? Object.keys(value)
      : [];
export const lines = (text) =>
  text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
export const words = (value) => String(value ?? "").replaceAll("_", " ");
export const plain = (value) =>
  typeof value === "object" && value !== null
    ? JSON.stringify(value)
    : String(value ?? "");
export const label = (value) =>
  typeof value === "string" ? value : value.id || value.name || value.slug;
export function metricUnits(measure) {
  if (!measure) return "";
  return measure === "aov_cents"
    ? "cents/order"
    : measure === "avg_price_cents"
      ? "cents/unit"
      : measure.endsWith("_cents")
        ? "cents"
        : measure.endsWith("_pct")
          ? "percent"
          : measure === "orders"
            ? "orders"
            : measure === "identified_buyers"
              ? "customers"
              : "units";
}
export function contextExcerpt(value) {
  if (typeof value !== "string") return value ? plain(value) : "";
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
      return (
        [
          parsed.description,
          parsed.body || parsed.definition || parsed.method,
          parsed.aliases?.length
            ? "Also called: " + parsed.aliases.join(", ")
            : null,
        ]
          .filter(Boolean)
          .join("\n\n") || value
      );
  } catch {
    /* Built-in Markdown remains readable text. */
  }
  return value;
}
export function validateChatDates(dates) {
  const parse = (value) => {
    const date = new Date(value + "T00:00:00Z");
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(value || "") ||
      !Number.isFinite(date.getTime()) ||
      date.toISOString().slice(0, 10) !== value
    )
      throw Error("Choose current start and end dates.");
    return date;
  };
  const start = parse(dates.start),
    end = parse(dates.end);
  if (!!dates.compare_start !== !!dates.compare_end)
    throw Error(
      "Provide both comparison dates, or clear both for the previous retail year.",
    );
  const previousStart = dates.compare_start
    ? parse(dates.compare_start)
    : new Date(+start - 364 * 86400000);
  const previousEnd = dates.compare_end
    ? parse(dates.compare_end)
    : new Date(+end - 364 * 86400000);
  if (start > end || previousStart > previousEnd)
    throw Error("Period starts must be before their ends.");
  if (end - start !== previousEnd - previousStart)
    throw Error("Comparison periods must have equal numbers of days.");
  if (
    Math.min(+start, +previousStart) < Date.parse("2024-01-01") ||
    Math.max(+end, +previousEnd) > Date.parse("2025-12-31")
  )
    throw Error("Sales and comparison dates must be within 2024–2025.");
  if (previousEnd >= start)
    throw Error("Comparison must end before the current period begins.");
  return true;
}
export function filterValue(value, type) {
  if (type === "int") {
    const number = Number(value);
    if (!Number.isSafeInteger(number) || number < 0)
      throw Error("Numeric filter values must be nonnegative whole numbers.");
    return number;
  }
  if (type === "bool") {
    if (value === true || value === "true") return true;
    if (value === false || value === "false") return false;
    throw Error("Boolean filter values must be true or false.");
  }
  return value;
}
