export function newContent(kind) {
  if (kind === "knowledge")
    return { description: "", body: "", aliases: [], source_refs: [] };
  if (kind === "ontology")
    return {
      concept_type: "concept",
      description: "",
      aliases: [],
      date_basis: "sale_date",
      return_basis: "before_returns",
      source_refs: [],
    };
  if (kind === "skill")
    return {
      description: "",
      trigger_examples: [],
      method: "",
      required_concepts: [],
      approved_tools: [],
      handler: "method_only",
      output_profile_id: "business-review",
      allowed_filters: [],
      caveats: [],
    };
  if (kind === "output_profile")
    return {
      description: "",
      detail: "standard",
      required_sections: [
        "Headline",
        "Scope and metric",
        "Primary visual",
        "Supporting values",
        "Interpretation",
        "Limitations",
        "Next question",
      ],
      chart_preference: "auto",
      show_evidence: true,
      show_scope: true,
      show_limitations: true,
    };
  if (kind === "example")
    return {
      question: "",
      answer: "",
      quality: "good",
      notes: "",
      output_profile_id: "business-review",
    };
  return { description: "", cases: [] };
}
export function draftFrom(asset) {
  return {
    id: asset?.id || "",
    name: asset?.name || "",
    kind: asset?.kind || "knowledge",
    content: structuredClone(
      asset?.draft?.content ||
        asset?.content ||
        asset?.effective_content ||
        newContent(asset?.kind || "knowledge"),
    ),
  };
}
