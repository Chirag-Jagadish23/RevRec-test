"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

type WorkspaceContextType = {
  companyName: string;
  isLoggedIn: boolean;
  isHydrated: boolean;
  login: (companyName: string) => void;
  logout: () => void;
  setCompanyName: (name: string) => void;
};

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(
  undefined
);

const STORAGE_KEYS = {
  companyName: "accruesmart.companyName",
  isLoggedIn: "accruesmart.isLoggedIn",
};

export function WorkspaceProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [companyName, setCompanyNameState] = useState<string>("DemoCo Finance");
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [isHydrated, setIsHydrated] = useState<boolean>(false);

  // Load from localStorage on first client render
  useEffect(() => {
    try {
      const savedCompany = window.localStorage.getItem(STORAGE_KEYS.companyName);
      const savedLoggedIn = window.localStorage.getItem(STORAGE_KEYS.isLoggedIn);

      if (savedCompany && savedCompany.trim()) {
        setCompanyNameState(savedCompany.trim());
      }

      if (savedLoggedIn === "true") {
        setIsLoggedIn(true);
      } else {
        setIsLoggedIn(false);
      }
    } catch {
      // ignore localStorage errors
    } finally {
      setIsHydrated(true);
    }
  }, []);

  const login = (name: string) => {
    const cleanName = (name || "").trim() || "My Company";

    setCompanyNameState(cleanName);
    setIsLoggedIn(true);

    try {
      window.localStorage.setItem(STORAGE_KEYS.companyName, cleanName);
      window.localStorage.setItem(STORAGE_KEYS.isLoggedIn, "true");
    } catch {
      // ignore localStorage errors
    }
  };

  const logout = () => {
    setIsLoggedIn(false);

    try {
      window.localStorage.removeItem(STORAGE_KEYS.isLoggedIn);
      // Keep companyName so user can log back in and still see it,
      // or uncomment next line to clear it too:
      // window.localStorage.removeItem(STORAGE_KEYS.companyName);
    } catch {
      // ignore localStorage errors
    }
  };

  const setCompanyName = (name: string) => {
    const cleanName = (name || "").trim();
    if (!cleanName) return;

    setCompanyNameState(cleanName);

    try {
      window.localStorage.setItem(STORAGE_KEYS.companyName, cleanName);
    } catch {
      // ignore localStorage errors
    }
  };

  const value = useMemo<WorkspaceContextType>(
    () => ({
      companyName,
      isLoggedIn,
      isHydrated,
      login,
      logout,
      setCompanyName,
    }),
    [companyName, isLoggedIn, isHydrated]
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextType {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used inside a WorkspaceProvider");
  }
  return ctx;
}
