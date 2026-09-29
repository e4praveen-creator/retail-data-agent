/** Local API requests share one error contract across chat and the data workspace. */
export async function api(path, body, options = {}) {
  let response;
  try {
    response = await fetch("/api" + path, {
      method: options.method || (body !== undefined ? "POST" : "GET"),
      headers: {
        "X-Retail-App": "local",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      signal: options.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "The local app is unreachable. Check that it is running, then try again.",
    );
  }
  const contentType = response.headers.get("content-type") || "";
  let payload;
  let parsed = false;
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
      parsed = true;
    } catch {
      // An invalid or truncated JSON body is different from a valid JSON null.
    }
  }
  if (!response.ok) {
    const detail = payload?.detail;
    const validation = Array.isArray(detail)
      ? detail.map((item) => item.msg || "Invalid input").join("; ")
      : null;
    const error = new Error(
      (typeof detail === "string" && detail) ||
        detail?.message ||
        validation ||
        `The request could not be completed (${response.status}). Please try again.`,
    );
    if (Array.isArray(detail?.errors) && detail.errors.length) {
      error.message +=
        " " +
        detail.errors
          .map((item) =>
            typeof item === "string"
              ? item
              : item.message || item.code || "Invalid field",
          )
          .join("; ");
    }
    error.status = response.status;
    error.code = detail?.code;
    error.errors = detail?.errors;
    throw error;
  }
  if (response.status === 204) return null;
  if (!parsed)
    throw new Error(
      "The app returned an unreadable response. Please try again.",
    );
  return payload;
}

export function conversationMarkdown(conversation) {
  const lines = [
    `# ${conversation.title || "Retail analysis"}`,
    "",
    "Milky Way 2.0 · synthetic retail data. Check the supporting evidence before relying on an AI conclusion.",
    "",
  ];
  for (const message of conversation.messages || []) {
    lines.push(
      `## ${message.role === "user" ? "You" : "Retail Agent"}`,
      "",
      message.text || "",
      "",
    );
    const analysis = message.analysis;
    if (!analysis) continue;
    if (analysis.id) lines.push(`Analysis ID: ${analysis.id}`, "");
    for (const specialist of analysis.specialists || []) {
      lines.push(
        `### ${specialist.role} findings`,
        "",
        specialist.answer || "",
        "",
      );
    }
    for (const output of analysis.outputs || []) {
      lines.push(
        `### Evidence ${output.evidence_id || ""}: ${output.name || "Query"}`,
        "",
      );
      if (output.sql) lines.push("````sql", output.sql, "````", "");
      if (output.parameters)
        lines.push("Parameters: " + JSON.stringify(output.parameters), "");
      lines.push(
        `${output.row_count ?? output.rows?.length ?? 0} returned rows${output.truncated ? " (truncated)" : ""}. Full data is available from the analysis export.`,
        "",
      );
    }
    for (const warning of analysis.warnings || [])
      lines.push(`Note: ${warning}`, "");
  }
  return lines.join("\n");
}
