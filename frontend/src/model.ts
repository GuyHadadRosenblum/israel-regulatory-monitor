export type Status = "matched" | "missing" | "review" | "submission";
export type Regulation = {
  id: string;
  title: string;
  ministry: string;
  date: string;
  status: Status;
  score: number;
  ria: "available" | "missing" | "exempt";
  summary: string;
  url: string;
  submissionDate: string;
};
export const labels: Record<Status, string> = {
  matched: "נמצאה התאמה",
  missing: "ללא פנייה רשמית",
  review: "לבדיקה",
  submission: "פנייה בלבד",
};
export const riaLabels = {
  available: "צורף דוח RIA",
  missing: "לא צורף RIA",
  exempt: "קיים פטור",
};
export function similarity(a: string, b: string): number {
  const words = (s: string) =>
    new Set(s.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || []);
  const x = words(a),
    y = words(b);
  if (!x.size || !y.size) return 0;
  return (
    (100 * [...x].filter((w) => y.has(w)).length) / new Set([...x, ...y]).size
  );
}
export function filterRows(
  rows: Regulation[],
  query: string,
  status: string,
  ministry: string,
) {
  return rows.filter(
    (r) =>
      (status === "all" || r.status === status) &&
      (ministry === "all" || r.ministry === ministry) &&
      `${r.title} ${r.ministry} ${r.summary}`.includes(query.trim()),
  );
}
export function csv(rows: Regulation[]) {
  const cell = (x: unknown) =>
    '"' +
    String(x)
      .replace(/^[=+@\-\t\r]/, "'$&")
      .replaceAll('"', '""') +
    '"';
  return (
    "\uFEFF" +
    [
      ["נושא", "משרד", "תאריך", "סטטוס", "ציון דמיון", "RIA"],
      ...rows.map((r) => [
        r.title,
        r.ministry,
        r.date,
        labels[r.status],
        r.score,
        riaLabels[r.ria],
      ]),
    ]
      .map((row) => row.map(cell).join(","))
      .join("\r\n")
  );
}
