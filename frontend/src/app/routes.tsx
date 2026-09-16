import { createBrowserRouter, Navigate } from "react-router";
import { Dashboard } from "./pages/Dashboard";
import { SessionDetail } from "./pages/SessionDetail";
import { ModelLeaderboard } from "./pages/ModelLeaderboard";
import { NewSession } from "./pages/NewSession";
import { RecordSleep } from "./pages/RecordSleep";
import { DoctorDashboard } from "./pages/DoctorDashboard";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { ProtectedRoute } from "./components/ProtectedRoute";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/login" replace />,
  },
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/signup",
    Component: Signup,
  },
  {
    path: "/dashboard",
    element: (
      <ProtectedRoute>
        <Dashboard />
      </ProtectedRoute>
    ),
  },
  {
    path: "/record-sleep",
    element: (
      <ProtectedRoute>
        <RecordSleep />
      </ProtectedRoute>
    ),
  },
  {
    path: "/session/new",
    element: (
      <ProtectedRoute>
        <NewSession />
      </ProtectedRoute>
    ),
  },
  {
    path: "/session/:id",
    element: (
      <ProtectedRoute>
        <SessionDetail />
      </ProtectedRoute>
    ),
  },
  {
    path: "/doctor",
    element: (
      <ProtectedRoute>
        <DoctorDashboard />
      </ProtectedRoute>
    ),
  },
  {
    path: "/admin/models",
    element: (
      <ProtectedRoute>
        <ModelLeaderboard />
      </ProtectedRoute>
    ),
  },
]);
