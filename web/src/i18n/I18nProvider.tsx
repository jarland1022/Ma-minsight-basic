import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getInitialLang,
  interpolate,
  lookup,
  persistLang,
  type Lang,
} from "./core";
import type { Messages } from "./messages";
import en from "./en";
import zh from "./zh";

type I18nContextValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (path: string, vars?: Record<string, string | number>) => string;
  messages: Messages;
};

const catalogs: Record<Lang, Messages> = { en, zh };

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => getInitialLang());

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    persistLang(next);
  }, []);

  const messages = catalogs[lang];

  const t = useCallback(
    (path: string, vars?: Record<string, string | number>) => {
      const fromCurrent = lookup(messages as Record<string, unknown>, path);
      const fromEn = lookup(en as Record<string, unknown>, path);
      const template = fromCurrent ?? fromEn ?? path;
      return interpolate(template, vars);
    },
    [messages],
  );

  const value = useMemo(
    () => ({ lang, setLang, t, messages }),
    [lang, setLang, t, messages],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return ctx;
}
