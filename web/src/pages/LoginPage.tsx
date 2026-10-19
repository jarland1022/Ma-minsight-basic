import { Button, Form, Input, message } from "antd";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { SESSION_EXPIRED_KEY, login } from "../api/client";
import BrandMark from "../components/BrandMark";
import LanguageSwitch from "../components/LanguageSwitch";
import { useI18n } from "../i18n/I18nProvider";

export default function LoginPage() {
  const navigate = useNavigate();
  const { t } = useI18n();

  useEffect(() => {
    if (sessionStorage.getItem(SESSION_EXPIRED_KEY)) {
      sessionStorage.removeItem(SESSION_EXPIRED_KEY);
      message.warning(t("login.sessionExpired"));
    }
  }, [t]);

  const onFinish = async (values: { username: string; password: string }) => {
    try {
      await login(values.username, values.password);
      message.success(t("login.success"));
      navigate("/");
    } catch {
      message.error(t("login.failed"));
    }
  };

  return (
    <div className="ms-login-wrap">
      <div className="ms-login-card">
        <div className="ms-login-lang">
          <LanguageSwitch />
        </div>
        <div className="ms-brand">
          <BrandMark className="ms-brand-mark" />
          <div>
            <h1>{t("brand.product")}</h1>
            <p>{t("brand.tagline")}</p>
          </div>
        </div>
        <Form
          layout="vertical"
          onFinish={onFinish}
          initialValues={{ username: "admin" }}
          requiredMark={false}
        >
          <Form.Item
            name="username"
            label={t("login.username")}
            rules={[{ required: true, message: t("login.usernameRequired") }]}
          >
            <Input autoComplete="username" placeholder="admin" />
          </Form.Item>
          <Form.Item
            name="password"
            label={t("login.password")}
            rules={[{ required: true, message: t("login.passwordRequired") }]}
          >
            <Input.Password
              autoComplete="current-password"
              placeholder={t("login.passwordPlaceholder")}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            {t("login.submit")}
          </Button>
        </Form>
        <p className="ms-login-hint">admin / changeme</p>
      </div>
    </div>
  );
}
