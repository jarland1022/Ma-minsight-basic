import { Button, Form, Input, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  SESSION_EXPIRED_KEY,
  changePassword,
  formatApiError,
  login,
  verifyMfa,
  type LoginResult,
} from "../api/client";
import BrandMark from "../components/BrandMark";
import LanguageSwitch from "../components/LanguageSwitch";
import { useI18n } from "../i18n/I18nProvider";

type Step = "password" | "changePassword" | "mfa" | "setup";

export default function LoginPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [step, setStep] = useState<Step>("password");
  const [busy, setBusy] = useState(false);
  const [challenge, setChallenge] = useState<LoginResult | null>(null);

  useEffect(() => {
    if (sessionStorage.getItem(SESSION_EXPIRED_KEY)) {
      sessionStorage.removeItem(SESSION_EXPIRED_KEY);
      message.warning(t("login.sessionExpired"));
    }
  }, [t]);

  const finishOk = () => {
    message.success(t("login.success"));
    navigate("/");
  };

  const handleAuthResult = (data: LoginResult): boolean => {
    if (data.must_change_password && data.access_token) {
      setStep("changePassword");
      return true;
    }
    if (data.mfa_setup_required && data.mfa_token) {
      setChallenge(data);
      setStep("setup");
      return true;
    }
    if (data.mfa_required && data.mfa_token) {
      setChallenge(data);
      setStep("mfa");
      return true;
    }
    if (data.access_token && data.token_class !== "bootstrap") {
      finishOk();
      return true;
    }
    if (data.access_token && data.token_class === "bootstrap") {
      setStep("changePassword");
      return true;
    }
    return false;
  };

  const onPassword = async (values: { username: string; password: string }) => {
    setBusy(true);
    try {
      const data = await login(values.username, values.password);
      if (!handleAuthResult(data)) {
        message.error(t("login.failed"));
      }
    } catch (e) {
      message.error(formatApiError(e) || t("login.failed"));
    } finally {
      setBusy(false);
    }
  };

  const onChangePassword = async (values: {
    current_password: string;
    new_password: string;
    confirm_password: string;
  }) => {
    if (values.new_password !== values.confirm_password) {
      message.error(t("login.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      const data = await changePassword(values.current_password, values.new_password);
      message.success(t("login.passwordChanged"));
      if (!handleAuthResult(data)) {
        message.error(t("login.failed"));
      }
    } catch (e) {
      message.error(formatApiError(e) || t("login.passwordChangeFailed"));
    } finally {
      setBusy(false);
    }
  };

  const onMfa = async (values: { code: string }) => {
    if (!challenge?.mfa_token) return;
    setBusy(true);
    try {
      const data = await verifyMfa(challenge.mfa_token, values.code);
      if (!handleAuthResult(data)) {
        message.error(t("login.mfaInvalid"));
      }
    } catch (e) {
      message.error(formatApiError(e) || t("login.mfaInvalid"));
    } finally {
      setBusy(false);
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

        {step === "password" && (
          <Form
            layout="vertical"
            onFinish={onPassword}
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
            <Button type="primary" htmlType="submit" block loading={busy}>
              {t("login.submit")}
            </Button>
          </Form>
        )}

        {step === "changePassword" && (
          <Form layout="vertical" onFinish={onChangePassword} requiredMark={false}>
            <Typography.Paragraph type="secondary">
              {t("login.mustChangePasswordHint")}
            </Typography.Paragraph>
            <Form.Item
              name="current_password"
              label={t("login.currentPassword")}
              rules={[{ required: true, message: t("login.passwordRequired") }]}
            >
              <Input.Password autoComplete="current-password" />
            </Form.Item>
            <Form.Item
              name="new_password"
              label={t("login.newPassword")}
              rules={[
                { required: true, message: t("login.passwordRequired") },
                { min: 8, message: t("login.passwordMinLength") },
              ]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Form.Item
              name="confirm_password"
              label={t("login.confirmPassword")}
              rules={[{ required: true, message: t("login.passwordRequired") }]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy}>
              {t("login.changePasswordSubmit")}
            </Button>
          </Form>
        )}

        {step === "mfa" && (
          <Form layout="vertical" onFinish={onMfa} requiredMark={false}>
            <Typography.Paragraph type="secondary">{t("login.mfaHint")}</Typography.Paragraph>
            <Form.Item
              name="code"
              label={t("login.mfaCode")}
              rules={[{ required: true, len: 6, message: t("login.mfaCodeRequired") }]}
            >
              <Input
                autoFocus
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                maxLength={8}
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy}>
              {t("login.mfaSubmit")}
            </Button>
            <Button
              type="link"
              block
              style={{ marginTop: 8 }}
              onClick={() => {
                setStep("password");
                setChallenge(null);
              }}
            >
              {t("login.back")}
            </Button>
          </Form>
        )}

        {step === "setup" && challenge && (
          <Form layout="vertical" onFinish={onMfa} requiredMark={false}>
            <Typography.Paragraph type="secondary">{t("login.mfaSetupHint")}</Typography.Paragraph>
            {challenge.qr_png_data_url && (
              <div style={{ textAlign: "center", marginBottom: 12 }}>
                <img
                  src={challenge.qr_png_data_url}
                  alt="MFA QR"
                  width={180}
                  height={180}
                  style={{ borderRadius: 8 }}
                />
              </div>
            )}
            {challenge.mfa_secret && (
              <Typography.Paragraph copyable={{ text: challenge.mfa_secret }}>
                {t("login.mfaSecret")}: <code>{challenge.mfa_secret}</code>
              </Typography.Paragraph>
            )}
            <Form.Item
              name="code"
              label={t("login.mfaCode")}
              rules={[{ required: true, len: 6, message: t("login.mfaCodeRequired") }]}
            >
              <Input
                autoFocus
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                maxLength={8}
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy}>
              {t("login.mfaConfirmSetup")}
            </Button>
            <Button
              type="link"
              block
              style={{ marginTop: 8 }}
              onClick={() => {
                setStep("password");
                setChallenge(null);
              }}
            >
              {t("login.back")}
            </Button>
          </Form>
        )}
      </div>
    </div>
  );
}
