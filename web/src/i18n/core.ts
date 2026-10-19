/** Lightweight i18n — no extra npm deps. Default language: English (GitHub). */

export type Lang = "en" | "zh";

export const LANG_STORAGE_KEY = "ma_minsight_lang";

export function normalizeLang(raw: string | null | undefined): Lang {
  if (!raw) return "en";
  const v = raw.toLowerCase();
  if (v === "zh" || v.startsWith("zh-") || v === "zh_cn" || v === "cn") return "zh";
  return "en";
}

/** Default English for GitHub / international visitors. Persisted choice wins. */
export function getInitialLang(): Lang {
  try {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    if (stored) return normalizeLang(stored);
  } catch {
    /* ignore */
  }
  return "en";
}

export function persistLang(lang: Lang): void {
  try {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch {
    /* ignore */
  }
  if (typeof document !== "undefined") {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = lang === "zh" ? "MA-MinSight Console" : "MA-MinSight Console";
  }
}

type Dict = Record<string, unknown>;

export function lookup(dict: Dict, path: string): string | undefined {
  const parts = path.split(".");
  let cur: unknown = dict;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Dict)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

export function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{\{(\w+)\}\}/g, (_, key: string) =>
    vars[key] !== undefined && vars[key] !== null ? String(vars[key]) : "",
  );
}
