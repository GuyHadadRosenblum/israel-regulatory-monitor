import { describe, it, expect } from "vitest";
import { similarity, filterRows, csv } from "./model";
import { demoRows } from "./demo";
describe("matching and exports", () => {
  it("uses Jaccard word sets, not percentage confidence", () => {
    expect(similarity("א ב", "ב ג")).toBeCloseTo(100 / 3);
    expect(similarity("", "טקסט")).toBe(0);
    expect(similarity("מילה מילה", "מילה")).toBe(100);
  });
  it("combines search and filters", () => {
    expect(filterRows(demoRows, "טעינה", "missing", "all")).toHaveLength(1);
    expect(filterRows(demoRows, "טעינה", "matched", "all")).toHaveLength(0);
  });
  it("escapes formulas and embedded quotes in exported cells", () => {
    const output = csv([{ ...demoRows[0], title: '=HYPERLINK("test")' }]);
    expect(output).toContain("'=");
    expect(output).toContain('""test""');
  });
});
