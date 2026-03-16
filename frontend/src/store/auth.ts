import { create } from "zustand";

type User = {
  id: number;
  email: string;
  name?: string | null;
  roles: string[];
  university_id?: number | null;
  university_name?: string | null;
  conference_id?: number | null;
  conference_name?: string | null;
  union_id?: number | null;
  union_name?: string | null;
  member_id?: string | null;
  member_number?: string | null;
  member_status?: string | null;
  member_university_id?: number | null;
  member_university_name?: string | null;
  donor_interest?: boolean;
  is_active?: boolean;
  is_system_admin?: boolean;
  subject_to_tenure?: boolean;
  force_password_reset?: boolean;
  tenure_months?: number | null;
  tenure_starts_on?: string | null;
  tenure_ends_on?: string | null;
  disabled_at?: string | null;
  deletion_due_at?: string | null;
};

type AuthState = {
  user: User | null;
  activeUniversityId: number | null;
  activeConferenceId: number | null;
  activeUnionId: number | null;
  setUser: (user: User | null) => void;
  setActiveUniversityId: (id: number | null) => void;
  setActiveConferenceId: (id: number | null) => void;
  setActiveUnionId: (id: number | null) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  activeUniversityId: null,
  activeConferenceId: null,
  activeUnionId: null,
  setUser: (user) => set((state) => {
    if (!user) {
      return {
        user: null,
        activeUniversityId: null,
        activeConferenceId: null,
        activeUnionId: null,
      };
    }
    if (user.university_id) {
      return {
        user,
        activeUniversityId: user.university_id,
        activeConferenceId: null,
        activeUnionId: null,
      };
    }
    if (user.conference_id) {
      return {
        user,
        activeUniversityId: null,
        activeConferenceId: user.conference_id,
        activeUnionId: null,
      };
    }
    if (user.union_id) {
      return {
        user,
        activeUniversityId: null,
        activeConferenceId: null,
        activeUnionId: user.union_id,
      };
    }
    return {
      user,
      activeUniversityId: state.activeUniversityId,
      activeConferenceId: state.activeConferenceId,
      activeUnionId: state.activeUnionId,
    };
  }),
  setActiveUniversityId: (id) => set((state) => ({
    activeUniversityId: state.user?.university_id ?? id,
    activeConferenceId: state.user?.university_id ? null : (state.user?.conference_id ?? state.activeConferenceId),
    activeUnionId: state.user?.university_id ? null : (state.user?.union_id ?? (id ? null : state.activeUnionId)),
  })),
  setActiveConferenceId: (id) => set((state) => ({
    activeUniversityId: state.user?.university_id ?? null,
    activeConferenceId: state.user?.university_id ? null : (state.user?.conference_id ?? id),
    activeUnionId: state.user?.university_id || state.user?.conference_id ? null : (state.user?.union_id ?? null),
  })),
  setActiveUnionId: (id) => set((state) => ({
    activeUniversityId: state.user?.university_id ?? null,
    activeConferenceId: state.user?.university_id || state.user?.conference_id ? null : null,
    activeUnionId: state.user?.university_id || state.user?.conference_id ? null : (state.user?.union_id ?? id),
  }))
}));
