const moneyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

export const fmt = (v, kind = "number") =>
  v == null
    ? "—"
    : kind === "money"
      ? moneyFormatter.format(v / 100)
      : kind === "pct"
        ? `${v.toFixed(1)}%`
        : numberFormatter.format(v);
export const title = (s) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
