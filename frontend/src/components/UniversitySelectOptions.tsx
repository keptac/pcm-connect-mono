import type { ReactNode } from "react";

type UniversityOption = {
  id: number | string;
  name?: string | null;
  union_id?: number | null;
  union_name?: string | null;
};

type UniversityGroup = {
  key: string;
  label: string;
  items: UniversityOption[];
};

type UniversitySelectOptionsProps = {
  universities?: UniversityOption[] | null;
  emptyOptionLabel?: string;
  emptyOptionValue?: string;
  extraOptions?: ReactNode;
  excludeUniversityIds?: Array<number | string>;
  preserveGroupOrder?: boolean;
};

const OTHER_GROUP_LABEL = "Other universities / campuses";

function normalizeUnionLabel(university: UniversityOption) {
  const label = String(university.union_name || "").trim();
  return label || OTHER_GROUP_LABEL;
}

export function groupUniversitiesByUnion(
  universities?: UniversityOption[] | null,
  excludeUniversityIds: Array<number | string> = [],
  preserveGroupOrder = false,
): UniversityGroup[] {
  const excludedIds = new Set(excludeUniversityIds.map((value) => String(value)));
  const grouped = new Map<string, UniversityGroup>();

  for (const university of universities || []) {
    if (!university || excludedIds.has(String(university.id))) {
      continue;
    }

    const label = normalizeUnionLabel(university);
    const key = university.union_id ? `union:${university.union_id}` : `union:${label}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        key,
        label,
        items: [],
      });
    }
    grouped.get(key)?.items.push(university);
  }

  const groups = [...grouped.values()];
  if (preserveGroupOrder) {
    return groups;
  }

  return groups.sort((left, right) => {
    if (left.label === OTHER_GROUP_LABEL) return 1;
    if (right.label === OTHER_GROUP_LABEL) return -1;
    return left.label.localeCompare(right.label);
  });
}

export function UniversitySelectOptions({
  universities,
  emptyOptionLabel,
  emptyOptionValue = "",
  extraOptions,
  excludeUniversityIds = [],
  preserveGroupOrder = false,
}: UniversitySelectOptionsProps) {
  const universityGroups = groupUniversitiesByUnion(universities, excludeUniversityIds, preserveGroupOrder);

  return (
    <>
      {emptyOptionLabel ? <option value={emptyOptionValue}>{emptyOptionLabel}</option> : null}
      {extraOptions}
      {universityGroups.map((group) => (
        <optgroup key={group.key} label={group.label}>
          {group.items.map((university) => (
            <option key={university.id} value={university.id}>
              {university.name || `University #${university.id}`}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}
