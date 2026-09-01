import React, { useState } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../../context/AuthContext";
import NotificationBell from "./NotificationBell";
import BrandLogo from "../shared/BrandLogo";
import { isPathLocked, isPathPreview } from "../../lib/featureAccess";
import {
  LayoutDashboard,
  Users,
  Megaphone,
  Settings,
  LogOut,
  Menu,
  X,
  Bell,
  ChevronRight,
  Phone,
  BarChart3,
  UserCircle,
  TrendingUp,
  Lock,
} from "lucide-react";

const DashboardLayout = () => {
  const { user, logout, isAdmin } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const navItems = [
    ...(isAdmin ? [{ path: "/dashboard", icon: LayoutDashboard, label: "Dashboard" }] : []),
    ...(isAdmin ? [] : [{ path: "/my-dashboard", icon: UserCircle, label: "My Dashboard" }]),
    { path: "/virtual-customer", icon: Users, label: "Virtual Customer" },
    { path: "/ai-calling", icon: Phone, label: "AI Calling" },
    ...(isAdmin
      ? [
          { path: "/campaigns", icon: Megaphone, label: "Campaigns" },
          { path: "/sales-dashboard", icon: BarChart3, label: "Sales Dashboard" },
          { path: "/marketing-dashboard", icon: TrendingUp, label: "Marketing" },
        ]
      : []),
    { path: "/notifications", icon: Bell, label: "Notifications" },
    ...(isAdmin ? [{ path: "/settings", icon: Settings, label: "Settings" }] : []),
  ];

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const currentPage =
    navItems.find((item) => location.pathname.startsWith(item.path))?.label || "Dashboard";

  const renderNavLink = (item, onNavigate) => {
    const locked = isPathLocked(item.path);
    const preview = isPathPreview(item.path);
    const Icon = item.icon;

    return (
      <NavLink
        key={item.path}
        to={item.path}
        onClick={onNavigate}
        aria-label={
          preview
            ? `${item.label} (preview)`
            : locked
              ? `${item.label} (premium feature)`
              : item.label
        }
        className={({ isActive }) =>
          [
            "mx-3 mb-1 flex items-center gap-3 rounded-2xl px-4 py-2.5 text-sm font-medium transition-all",
            locked ? "opacity-70" : "",
            isActive ? "nav-link-active" : "nav-link-idle",
          ]
            .filter(Boolean)
            .join(" ")
        }
        data-testid={`nav-${item.label.toLowerCase().replace(" ", "-")}`}
      >
        <Icon className="nav-icon shrink-0" size={19} strokeWidth={1.7} />
        <span className="min-w-0 flex-1 truncate">{item.label}</span>
        {preview ? (
          <span
            className="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
            style={{
              background: "rgb(var(--royal-rgb)/0.08)",
              color: "rgb(var(--royal-rgb)/1)",
            }}
          >
            Preview
          </span>
        ) : null}
        {locked ? <Lock size={14} className="shrink-0 text-[var(--executive-accent)]" /> : null}
      </NavLink>
    );
  };

  const userInitial = user?.full_name?.charAt(0) || "U";

  return (
    <div className="executive-shell min-h-screen text-slate-900">
      <div className="exec-blob-mid" />
      <div
        className="sticky top-0 z-[60] h-[2px] w-full"
        style={{
          background:
            "linear-gradient(90deg, rgba(27,79,140,0.88) 0%, rgba(74,122,181,0.42) 52%, transparent 100%)",
        }}
      />

      <aside className="executive-glass fixed inset-y-4 left-4 z-50 hidden w-72 flex-col overflow-hidden lg:flex">
        <div className="border-b px-5 py-4" style={{ borderColor: "rgb(var(--navy-rgb)/0.09)" }}>
          <BrandLogo variant="sidebar" darkBackground={false} testId="sidebar-logo" />
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
          {navItems.map((item) => renderNavLink(item))}
        </nav>

        <div className="border-t p-4" style={{ borderColor: "rgb(var(--navy-rgb)/0.09)" }}>
          <div className="mb-3 flex items-center gap-3 rounded-2xl bg-white/80 px-3 py-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
              style={{ background: "linear-gradient(135deg,#8d57de,#5d27ca)" }}
            >
              {userInitial}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-900">{user?.full_name || "User"}</p>
              <p className="truncate text-xs" style={{ color: "var(--executive-text-muted)" }}>
                {user?.email}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="brand-button-ghost w-full px-4 py-2 text-sm"
            data-testid="logout-btn"
          >
            <LogOut size={17} strokeWidth={1.7} />
            Sign Out
          </button>
        </div>
      </aside>

      <motion.aside
        className={`executive-glass fixed inset-y-3 left-3 z-50 w-[min(19rem,calc(100vw-1.5rem))] overflow-hidden lg:hidden ${
          sidebarOpen ? "block" : "hidden"
        }`}
        initial={{ x: -320 }}
        animate={{ x: sidebarOpen ? 0 : -320 }}
        transition={{ duration: 0.2 }}
      >
        <button
          type="button"
          onClick={() => setSidebarOpen(false)}
          className="absolute right-4 top-4 rounded-full p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          data-testid="close-sidebar-btn"
        >
          <X size={22} />
        </button>
        <div className="border-b px-5 py-4" style={{ borderColor: "rgb(var(--navy-rgb)/0.09)" }}>
          <BrandLogo variant="sidebar" darkBackground={false} />
        </div>
        <nav className="py-4">{navItems.map((item) => renderNavLink(item, () => setSidebarOpen(false)))}</nav>
      </motion.aside>

      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-[rgba(12,8,40,0.32)] backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="relative z-10 min-w-0 lg:pl-[19.5rem]">
        <header
          className="sticky top-[2px] z-30 backdrop-blur-xl"
          style={{
            background: "rgba(255,255,255,0.94)",
            borderBottom: "1px solid rgb(var(--navy-rgb)/0.09)",
            boxShadow: "0 1px 2px rgb(var(--navy-rgb)/0.04), 0 4px 20px rgb(var(--navy-rgb)/0.04)",
          }}
        >
          <div className="px-4 sm:px-6 lg:px-8">
            <div className="flex h-14 items-center justify-between gap-4">
              <div className="flex min-w-0 items-center gap-3">
                <button
                  type="button"
                  onClick={() => setSidebarOpen(true)}
                  className="brand-button-ghost h-10 w-10 p-0 lg:hidden"
                  data-testid="open-sidebar-btn"
                >
                  <Menu size={21} />
                </button>
                <div className="lg:hidden">
                  <BrandLogo variant="header" darkBackground={false} />
                </div>
                <div className="hidden min-w-0 items-center gap-2 lg:flex">
                  <span className="text-xs" style={{ color: "var(--executive-text-muted)" }}>
                    Home
                  </span>
                  <ChevronRight size={14} style={{ color: "var(--executive-text-muted)" }} />
                  <span className="truncate text-sm font-semibold text-slate-900">{currentPage}</span>
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-2">
                <NotificationBell darkMode={false} />
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold text-white lg:hidden"
                  style={{ background: "linear-gradient(135deg,#8d57de,#5d27ca)" }}
                >
                  {userInitial}
                </div>
              </div>
            </div>
          </div>
        </header>

        <div className="px-4 py-6 pb-24 sm:px-6 lg:px-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default DashboardLayout;
