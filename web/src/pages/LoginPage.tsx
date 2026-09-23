import { Button, Form, Input, message } from "antd";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { SESSION_EXPIRED_KEY, login } from "../api/client";
import BrandMark from "../components/BrandMark";

export default function LoginPage() {
  const navigate = useNavigate();

  useEffect(() => {
    if (sessionStorage.getItem(SESSION_EXPIRED_KEY)) {
      sessionStorage.removeItem(SESSION_EXPIRED_KEY);
      message.warning("登录已过期，请重新登录");
    }
  }, []);

  const onFinish = async (values: { username: string; password: string }) => {
    try {
      await login(values.username, values.password);
      message.success("登录成功");
      navigate("/");
    } catch {
      message.error("用户名或密码错误");
    }
  };

  return (
    <div className="ms-login-wrap">
      <div className="ms-login-card">
        <div className="ms-brand">
          <BrandMark className="ms-brand-mark" />
          <div>
            <h1>MA-MinSight</h1>
            <p>Community · SIEM 告警分诊</p>
          </div>
        </div>
        <Form
          layout="vertical"
          onFinish={onFinish}
          initialValues={{ username: "admin" }}
          requiredMark={false}
        >
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input autoComplete="username" placeholder="admin" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password
              autoComplete="current-password"
              placeholder="默认 changeme（请通过 ADMIN_INITIAL_PASSWORD 修改）"
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            登录
          </Button>
        </Form>
        <p className="ms-login-hint">默认账号 admin / changeme（请通过 ADMIN_INITIAL_PASSWORD 修改）</p>
      </div>
    </div>
  );
}
