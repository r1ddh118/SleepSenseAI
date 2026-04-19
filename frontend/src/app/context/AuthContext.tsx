import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface User {
  email: string;
  name: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => boolean;
  signup: (email: string, password: string, name: string, role: string) => boolean;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Demo credentials
const DEMO_CREDENTIALS = {
  email: "demo@sleepsense.ai",
  password: "demo123",
  name: "Dr. Demo User",
  role: "doctor",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // Check if user is already logged in
    const savedUser = localStorage.getItem("sleepsense_user");
    if (savedUser) {
      setUser(JSON.parse(savedUser));
    }
  }, []);

  const login = (email: string, password: string): boolean => {
    // Check demo credentials first
    if (email === DEMO_CREDENTIALS.email && password === DEMO_CREDENTIALS.password) {
      const demoUser = {
        email: DEMO_CREDENTIALS.email,
        name: DEMO_CREDENTIALS.name,
        role: DEMO_CREDENTIALS.role,
      };
      setUser(demoUser);
      localStorage.setItem("sleepsense_user", JSON.stringify(demoUser));
      return true;
    }

    // Check localStorage for registered users
    const users = JSON.parse(localStorage.getItem("sleepsense_users") || "[]");
    const foundUser = users.find(
      (u: any) => u.email === email && u.password === password
    );

    if (foundUser) {
      const userData = {
        email: foundUser.email,
        name: foundUser.name,
        role: foundUser.role || "user",
      };
      setUser(userData);
      localStorage.setItem("sleepsense_user", JSON.stringify(userData));
      return true;
    }

    return false;
  };

  const signup = (email: string, password: string, name: string, role: string): boolean => {
    // Check if user already exists
    const users = JSON.parse(localStorage.getItem("sleepsense_users") || "[]");
    const existingUser = users.find((u: any) => u.email === email);

    if (existingUser) {
      return false; // User already exists
    }

    // Add new user
    const newUser = {
      email,
      password,
      name,
      role: "user",
      role,
      createdAt: new Date().toISOString(),
    };

    users.push(newUser);
    localStorage.setItem("sleepsense_users", JSON.stringify(users));

    // Auto-login after signup
    const userData = {
      email: newUser.email,
      name: newUser.name,
      role: newUser.role,
    };
    setUser(userData);
    localStorage.setItem("sleepsense_user", JSON.stringify(userData));

    return true;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("sleepsense_user");
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        signup,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}