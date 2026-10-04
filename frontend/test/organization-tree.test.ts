import { describe, expect, it } from "vitest";
import type { DepartmentDto } from "@/lib/domain-api/organizations";
import {
  buildDepartmentTree,
  departmentDescendantIds,
  departmentFullPath,
} from "@/lib/organization-tree";

const rows: DepartmentDto[] = [
  { id: "radio", hospital_id: "h1", parent_id: null, name: "Radiologie", code: "RAD", is_active: true },
  { id: "ct", hospital_id: "h1", parent_id: "radio", name: "CT", code: "CT", is_active: true },
  { id: "heart", hospital_id: "h1", parent_id: "medical", name: "Herzkatheter", code: "HK", is_active: true },
  { id: "medical", hospital_id: "h1", parent_id: null, name: "Medizinische Klinik", code: "MED", is_active: true },
  { id: "other", hospital_id: "h2", parent_id: null, name: "Radiologie", code: "RAD", is_active: true },
];

describe("organization department tree", () => {
  it("builds nested units within one hospital and sorts siblings", () => {
    const tree = buildDepartmentTree(rows, "h1");
    expect(tree.map((item) => item.name)).toEqual(["Medizinische Klinik", "Radiologie"]);
    expect(tree[1].children.map((item) => item.name)).toEqual(["CT"]);
    expect(tree.flatMap((item) => item.children).some((item) => item.id === "other")).toBe(false);
  });

  it("shows the full path for duplicate unit names", () => {
    expect(departmentFullPath(rows[2], rows)).toBe("Medizinische Klinik › Herzkatheter");
  });

  it("returns descendants to prevent selecting a child as its ancestor", () => {
    expect(departmentDescendantIds("radio", rows)).toEqual(new Set(["ct"]));
  });

  it("keeps malformed cycles visible instead of recursing forever", () => {
    const cyclic = rows.slice(0, 2).map((item) => ({ ...item }));
    cyclic[0].parent_id = cyclic[1].id;
    const tree = buildDepartmentTree(cyclic, "h1");
    expect(tree.map((item) => item.id).sort()).toEqual(["ct", "radio"]);
  });
});
