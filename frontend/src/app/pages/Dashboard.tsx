import { Link } from "react-router";
import { Plus, TrendingDown, TrendingUp, Activity, Moon, Zap, LogOut, User } from "lucide-react";
import { SessionCard } from "../components/SessionCard";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { DoctorDashboard } from "./DoctorDashboard";
import { PatientDashboard } from "./PatientDashboard";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { mockSessions, patientInfo } from "../data/mockData";

export function Dashboard() {
  const { user, logout } = useAuth();

  // Route to appropriate dashboard based on role
  if (user?.role === "doctor") {
    return <DoctorDashboard />;
  }

  if (user?.role === "patient") {
    return <PatientDashboard />;
  }

  // Default dashboard for demo/admin users
}