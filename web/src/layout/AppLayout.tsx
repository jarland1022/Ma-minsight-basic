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
import LanguageSwitch from "../components/LanguageSwitch";
import { useI18n } from "../i18n/I18nProvider";

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

function useModules(): NavModule[] {
  const { t } = useI18n();
  return useMemo(
    () => [
      {
        key: "home",
        label: t("nav.home"),
        children: [{ path: "/", label: t("nav.dashboard"), icon: <DashboardOutlined /> }],
      },
      {
        key: "review",
        label: t("nav.review"),
        children: [
          { path: "/events", label: t("nav.events"), icon: <ClusterOutlined /> },
          { path: "/human-review", label: t("nav.humanReview"), icon: <MessageOutlined /> },
          { path: "/playbooks", label: t("nav.playbooks"), icon: <BookOutlined /> },
        ],
      },
      {
        key: "defense",
        label: t("nav.defense"),
        children: [
          { path: "/defense-assets", label: t("nav.defenseAssets"), icon: <SafetyOutlined /> },
        ],
      },
      {
        key: "system",
        label: t("nav.system"),
        children: [
          { path: "/guide", label: t("nav.guide"), icon: <QuestionCircleOutlined /> },
          { path: "/eval", label: t("nav.eval"), icon: <ExperimentOutlined /> },
          { path: "/license", label: t("nav.license"), icon: <KeyOutlined /> },
          { path: "/settings", label: t("nav.settings"), icon: <SettingOutlined /> },
        ],
      },
    ],
    [t],
  );
}

function matchModule(
  pathname: string,
  modules: NavModule[],
): { module: NavModule; child: NavChild } {
  if (pathname.startsWith("/investigations/")) {
    const review = modules.find((m) => m.key === "review")!;
    const events = review.children.find((c) => c.path === "/events")!;
    return { module: review, child: events };
  }
  for (const mod of modules) {
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
  return { module: modules[0], child: modules[0].children[0] };
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useI18n();
  const modules = useModules();
  const { module, child } = useMemo(
    () => matchModule(location.pathname, modules),
    [location.pathname, modules],
  );

  const { data: me } = useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => (await api.get("/auth/me")).data,
  });

  const { data: licenseData } = useQuery({
    queryKey: ["license-status"],
    queryFn: async () =>
      (await api.get("/license/status")).data as {
        edition?: string;
        pro_enabled?: boolean;
        license: { status: string; hint?: string; days_remaining?: number };
      },
    refetchInterval: 60_000,
  });
  const lic = licenseData?.license;
  const proEnabled = Boolean(licenseData?.pro_enabled);
  const showLicenseBanner = Boolean(lic && lic.status !== "active");
  const bannerTone =
    lic?.status === "community" || lic?.status === "no_license" ? "warn" : "error";

  return (
    <div className="ms-shell">
      <header className="ms-header">
        <Link to="/" className="ms-header-brand">
          <span className="ms-header-logo">{t("brand.product")}</span>
          <span className="ms-header-model">
            {proEnabled ? t("brand.pro") : t("brand.community")}
          </span>
        </Link>
        <nav className="ms-topnav" aria-label="Main">
          {modules.map((mod) => (
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
          <LanguageSwitch />
          {me?.username && <span className="ms-chip">{me.username}</span>}
          <Link className="ms-header-link" to="/guide">
            {t("common.guide")}
          </Link>
          <button type="button" className="ms-header-link" onClick={logout}>
            {t("nav.logout")}
          </button>
        </div>
      </header>

      <div className="ms-body">
        <aside className="ms-sidebar">
          <div className="ms-side-title">{module.label}</div>
          <nav className="ms-sidenav" aria-label="Submenu">
            {module.children.map((item) => {
              const active =
                item.path === "/"
                  ? location.pathname === "/"
                  : location.pathname === item.path ||
                    location.pathname.startsWith(`${item.path}/`);
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
          {showLicenseBanner && lic && (
            <div className={`ms-license-banner ${bannerTone}`} role="status">
              <span>
                {lic.status === "community"
                  ? t("license.bannerCommunity")
                  : lic.hint || t("license.bannerStatus", { status: lic.status })}
              </span>
              <Link to="/license">{t("license.goLicense")}</Link>
            </div>
          )}
          <div className="ms-crumb">
            {module.label} / {child.label}
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
