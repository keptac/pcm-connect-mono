import { useAuthStore } from "../store/auth";

export function useUniversityScope() {
  const { activeUniversityId, user } = useAuthStore();
  const roles = user?.roles || [];
  const isSuperAdmin = roles.includes("super_admin");
  const isUniversityScoped = Boolean(user?.university_id);
  const canSelectUniversity = Boolean(user) && !user?.university_id;
  const scopedUniversityId = user?.university_id ?? activeUniversityId ?? null;

  return {
    user,
    roles,
    isSuperAdmin,
    isUniversityScoped,
    canSelectUniversity,
    scopedUniversityId,
    defaultUniversityId: scopedUniversityId
  };
}
