import { create } from "zustand";
import type { User } from "@/types/api";

interface AuthState {
  user: User | null;
  status: "unknown" | "authenticated" | "anonymous";
  setUser: (user: User | null) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "unknown",
  setUser: (user) => set({ user, status: user ? "authenticated" : "anonymous" }),
  clear: () => set({ user: null, status: "anonymous" }),
}));
