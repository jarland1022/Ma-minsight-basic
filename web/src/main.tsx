import React, { useMemo } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import { I18nProvider, useI18n } from "./i18n/I18nProvider";
import { persistLang, getInitialLang } from "./i18n/core";
import "antd/dist/reset.css";
import "./styles/theme.css";

persistLang(getInitialLang());

const theme = {
  token: {
    colorPrimary: "#1a6db5",
    colorInfo: "#1a6db5",
    colorLink: "#0b4f8a",
    borderRadius: 4,
    fontFamily: '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
    colorBgLayout: "#f0f3f7",
    colorBorder: "#d5dee8",
    colorText: "#1f2a37",
    colorTextSecondary: "#6b7c90",
  },
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (isAxiosError(error) && error.response?.status === 401) {
          return false;
        }
        return failureCount < 3;
      },
    },
  },
});

function AntLocaleRoot({ children }: { children: React.ReactNode }) {
  const { lang } = useI18n();
  const locale = useMemo(() => (lang === "zh" ? zhCN : enUS), [lang]);
  return (
    <ConfigProvider locale={locale} theme={theme}>
      {children}
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <AntLocaleRoot>
          <App />
        </AntLocaleRoot>
      </I18nProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
