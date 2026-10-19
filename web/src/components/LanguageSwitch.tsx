import { useI18n } from "../i18n/I18nProvider";

/** Compact EN | 中文 toggle (default language is English). */
export default function LanguageSwitch({ className }: { className?: string }) {
  const { lang, setLang, t } = useI18n();

  return (
    <span className={className ?? "ms-lang-switch"} role="group" aria-label="Language">
      <button
        type="button"
        className={`ms-lang-btn${lang === "en" ? " active" : ""}`}
        onClick={() => setLang("en")}
      >
        {t("nav.langEn")}
      </button>
      <span className="ms-lang-sep" aria-hidden>
        |
      </span>
      <button
        type="button"
        className={`ms-lang-btn${lang === "zh" ? " active" : ""}`}
        onClick={() => setLang("zh")}
      >
        {t("nav.langZh")}
      </button>
    </span>
  );
}
