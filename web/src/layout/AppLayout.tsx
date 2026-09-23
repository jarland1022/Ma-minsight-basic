import { useMemo, type ReactNode } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  DashboardOutlined,
  ClusterOutlined,
  MessageOutlined,
  SafetyOutlined,
  SettingOutlined,
  ExperimentOutlined,
  QuestionCircleOutlined,
  BookOutlined,
  KeyOutlined,
} from "@ant-design/icons";
import { api, logout } from "../api/client";

type NavChild = {
  path: string;
  label: string;
  icon: ReactNode;
};

type NavModule = {
  key: string;
  label: string;
  children: NavChild[];
};

const MODULES: NavModule[] = [
  {
    key: "home",
    label: "首页",
    children: [{ path: "/", label: "仪表盘", icon: <DashboardOutlined /> }],
  },
  {
    key: "review",
    label: "研判",
    children: [
      { path: "/events", label: "事件队列", icon: <ClusterOutlined /> },
      { path: "/human-review", label: "人工协查 (Pro)", icon: <MessageOutlined /> },
      { path: "/playbooks", label: "技能库", icon: <BookOutlined /> },
    ],
  },
  {
    key: "defense",
    label: "防御",
    children: [{ path: "/defense-assets", label: "防御资产 (Pro)", icon: <SafetyOutlined /> }],
  },
  {
    key: "system",
    label: "系统",
    children: [
      { path: "/guide", label: "使用指南", icon: <QuestionCircleOutlined /> },
      { path: "/eval", label: "评测 (Pro)", icon: <ExperimentOutlined /> },
      { path: "/license", label: "License", icon: <KeyOutlined /> },
      { path: "/settings", label: "设置", icon: <SettingOutlined /> },
    ],
  },
];

function matchModule(pathname: string): { module: NavModule; child: NavChild } {
  // Investigation trace belongs under 事件队列
  if (pathname.startsWith("/investigations/")) {
    const review = MODULES.find((m) => m.key === "review")!;
    const events = review.children.find((c) => c.path === "/events")!;
    return { module: review, child: events };
  }
  for (const mod of MODULES) {
    for (const child of mod.children) {
      if (child.path === "/") {
        if (pathname === "/") {
          return { module: mod, child };
        }
        continue;
      }
      if (pathname === child.path || pathname.startsWith(`${child.path}/`)) {
        return { module: mod, child };
      }
    }
  }
  return { module: MODULES[0], child: MODULES[0].children[0] };
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { module, child } = useMemo(() => matchModule(location.pathname), [location.pathname]);

  const { data: me } = useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => (await api.get("/auth/me")).data,
  });

  return (
    <div className="ms-shell">
      <header className="ms-header">
        <Link to="/" className="ms-header-brand">
          <span className="ms-header-logo">MA-MinSight</span>
          <span className="ms-header-model">Community</span>
        </Link>
        <nav className="ms-topnav" aria-label="主模块">
          {MODULES.map((mod) => (
            <button
              key={mod.key}
              type="button"
              className={`ms-topnav-item${mod.key === module.key ? " active" : ""}`}
              onClick={() => navigate(mod.children[0].path)}
            >
              {mod.label}
            </button>
          ))}
        </nav>
        <div className="ms-header-right">
          {me?.username && <span className="ms-chip">{me.username}</span>}
          <Link className="ms-header-link" to="/guide">
            使用指南
          </Link>
          <button type="button" className="ms-header-link" onClick={logout}>
            退出
          </button>
        </div>
      </header>

      <div className="ms-body">
        <aside className="ms-sidebar">
          <div className="ms-side-title">{module.label}</div>
          <nav className="ms-sidenav" aria-label="子菜单">
            {module.children.map((item) => {
              const active =
                item.path === "/"
                  ? location.pathname === "/"
                  : location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`ms-sidenav-item${active ? " active" : ""}`}
                >
                  {item.icon}
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="ms-main">
          <div className="ms-crumb">
            {module.label} / {child.label}
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
