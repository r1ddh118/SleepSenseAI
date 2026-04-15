import { createBrowserRouter } from "react-router";
import { Dashboard } from "./pages/Dashboard";
import { SessionDetail } from "./pages/SessionDetail";
import { ModelLeaderboard } from "./pages/ModelLeaderboard";
import { NewSession } from "./pages/NewSession";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Dashboard,
  },
  {
    path: "/dashboard",
    Component: Dashboard,
  },
  {
    path: "/session/new",
    Component: NewSession,
  },
  {
    path: "/session/:id",
    Component: SessionDetail,
  },
  {
    path: "/admin/models",
    Component: ModelLeaderboard,
  },
]);
