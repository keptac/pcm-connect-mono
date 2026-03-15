import { create } from "zustand";

type User = {
  id: number;
  email: string;
  name?: string | null;
  roles: string[];
  university_id?: number | null;
  member_id?: string | null;
  member_number?: string | null;
  member_status?: string | null;
  member_university_id?: number | null;
  member_university_name?: string | null;
  donor_interest?: boolean;
};

type AuthState = {
  user: User | null;
  activeUniversityId: number | null;
  setUser: (user: User | null) => void;
  setActiveUniversityId: (id: number | null) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  activeUniversityId: null,
  setUser: (user) => set((state) => ({
    user,
    activeUniversityId: user?.university_id ?? (user ? state.activeUniversityId : null)
  })),
  setActiveUniversityId: (id) => set((state) => ({ activeUniversityId: state.user?.university_id ?? id }))
}));
