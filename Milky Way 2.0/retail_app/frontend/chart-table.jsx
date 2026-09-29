import React, { useEffect, useState } from "react";
import { fmt, title } from "./format.js";
import { PlaybookChart, StructuredQueryChart } from "./playbook-charts.jsx";

export function Chart(props) {
  return <PlaybookChart {...props} />;
}
export function QueryChart(props) {
  return <StructuredQueryChart {...props} />;
}
export function Table({ output }) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [output]);
  const rows = output?.rows || [],
    keys = rows.length ? Object.keys(rows[0]) : [];
  return (
    <>
      <div className="table-meta">
        <span>
          {fmt(output?.row_count)} rows{" "}
          {output?.truncated ? "· result truncated" : ""} · currency columns
          ending in cents are stored in US cents
        </span>
        <span>
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>
            Previous
          </button>{" "}
          {page + 1} / {Math.max(1, Math.ceil(rows.length / 25))}{" "}
          <button
            disabled={(page + 1) * 25 >= rows.length}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </span>
      </div>
      <div className="table-scroll">
        <table aria-label={output?.name ? title(output.name) : "Query results"}>
          <thead>
            <tr>
              {keys.map((k) => (
                <th key={k} scope="col">
                  {title(k)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(page * 25, (page + 1) * 25).map((r, i) => (
              <tr key={i}>
                {keys.map((k) => (
                  <td key={k}>
                    {r[k] == null
                      ? "—"
                      : typeof r[k] === "number"
                        ? fmt(r[k])
                        : String(r[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && <Empty>No rows returned.</Empty>}
    </>
  );
}
