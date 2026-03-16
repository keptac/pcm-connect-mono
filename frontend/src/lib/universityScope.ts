import type { ScopeParams } from "../api/endpoints";
import { useAuthStore } from "../store/auth";

export function useUniversityScope() {
  const { activeUniversityId, activeConferenceId, activeUnionId, user } = useAuthStore();
  const roles = user?.roles || [];
  const isSuperAdmin = roles.includes("super_admin");
  const assignedUniversityId = user?.university_id ?? null;
  const assignedConferenceId = assignedUniversityId ? null : (user?.conference_id ?? null);
  const assignedUnionId = assignedUniversityId || assignedConferenceId ? null : (user?.union_id ?? null);
  const isUniversityScoped = Boolean(assignedUniversityId);
  const isConferenceScoped = Boolean(!assignedUniversityId && assignedConferenceId);
  const isUnionScoped = Boolean(!assignedUniversityId && !assignedConferenceId && assignedUnionId);
  const canSelectNetwork = Boolean(user) && !assignedUniversityId && !assignedConferenceId && !assignedUnionId;
  const canSelectUniversity = Boolean(user) && !assignedUniversityId;
  const scopedUniversityId = assignedUniversityId ?? activeUniversityId ?? null;
  const scopedConferenceId = scopedUniversityId ? null : (assignedConferenceId ?? activeConferenceId ?? null);
  const scopedUnionId = scopedUniversityId || scopedConferenceId ? null : (assignedUnionId ?? activeUnionId ?? null);
  const scopeType = scopedUniversityId ? "university" : scopedConferenceId ? "conference" : scopedUnionId ? "union" : "network";
  const scopeParams: ScopeParams = {
    universityId: scopedUniversityId,
    conferenceId: scopedConferenceId,
    unionId: scopedUnionId,
  };
  const scopeKey = scopedUniversityId
    ? `university:${scopedUniversityId}`
    : scopedConferenceId
      ? `conference:${scopedConferenceId}`
      : scopedUnionId
        ? `union:${scopedUnionId}`
        : "network";

  return {
    user,
    roles,
    isSuperAdmin,
    assignedUniversityId,
    assignedConferenceId,
    assignedUnionId,
    isUniversityScoped,
    isConferenceScoped,
    isUnionScoped,
    canSelectNetwork,
    canSelectUniversity,
    scopedUniversityId,
    scopedConferenceId,
    scopedUnionId,
    scopeType,
    scopeKey,
    scopeParams,
    defaultUniversityId: scopedUniversityId
  };
}
