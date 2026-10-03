import type { DepartmentDto } from "@/lib/domain-api/organizations";

export interface DepartmentTreeNode extends DepartmentDto {
  children: DepartmentTreeNode[];
}

export function departmentFullPath(
  department: DepartmentDto,
  departments: DepartmentDto[],
): string {
  const byId = new Map(departments.map((item) => [item.id, item]));
  const parts: string[] = [];
  const visited = new Set<string>();
  let current: DepartmentDto | undefined = department;

  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    parts.push(current.name);
    current = current.parent_id ? byId.get(current.parent_id) : undefined;
  }

  return parts.reverse().join(" › ");
}

function hasParentCycle(id: string, nodes: Map<string, DepartmentTreeNode>): boolean {
  const visited = new Set<string>();
  let current = nodes.get(id);
  while (current?.parent_id) {
    if (visited.has(current.id) || current.parent_id === id) return true;
    visited.add(current.id);
    current = nodes.get(current.parent_id);
  }
  return false;
}

export function buildDepartmentTree(
  departments: DepartmentDto[],
  hospitalId: string,
): DepartmentTreeNode[] {
  const nodes = new Map<string, DepartmentTreeNode>();
  for (const department of departments) {
    if (department.hospital_id === hospitalId) {
      nodes.set(department.id, { ...department, children: [] });
    }
  }

  const roots: DepartmentTreeNode[] = [];
  for (const node of nodes.values()) {
    const parent = node.parent_id ? nodes.get(node.parent_id) : undefined;
    if (parent && !hasParentCycle(node.id, nodes)) parent.children.push(node);
    else roots.push(node);
  }

  const sort = (items: DepartmentTreeNode[]) => {
    items.sort((a, b) => a.name.localeCompare(b.name, "de"));
    for (const item of items) sort(item.children);
  };
  sort(roots);
  return roots;
}

export function departmentDescendantIds(
  departmentId: string,
  departments: DepartmentDto[],
): Set<string> {
  const descendants = new Set<string>();
  const queue = [departmentId];
  while (queue.length) {
    const parentId = queue.shift()!;
    for (const item of departments) {
      if (item.parent_id === parentId && !descendants.has(item.id)) {
        descendants.add(item.id);
        queue.push(item.id);
      }
    }
  }
  return descendants;
}
