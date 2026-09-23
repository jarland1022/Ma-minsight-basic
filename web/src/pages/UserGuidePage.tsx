import { Card, Space, Steps, Table, Typography } from "antd";
import {
  EVENT_STATUS_GUIDE,
  PAGE_GUIDES,
  QUICK_START_STEPS,
  VERDICT_GUIDE,
} from "../content/userGuide";
import UserGuidePanel from "../components/UserGuidePanel";

export default function UserGuidePage() {
  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="MA-MinSight 使用指南（面向业务/运维人员）">
        <Typography.Paragraph>
          本系统用 AI 帮您<strong>读告警、查背景、给建议</strong>。您不需要成为安全专家，只需在 AI
          提问时用日常语言补充您知道的业务事实。
        </Typography.Paragraph>
        <Typography.Title level={5}>四步快速上手</Typography.Title>
        <Steps
          direction="vertical"
          size="small"
          current={-1}
          items={QUICK_START_STEPS.map((desc) => ({ title: desc }))}
        />
      </Card>

      <UserGuidePanel guide={PAGE_GUIDES.dashboard} defaultExpanded />
      <UserGuidePanel guide={PAGE_GUIDES.humanReview} defaultExpanded />
      <UserGuidePanel guide={PAGE_GUIDES.eventDetail} />
      <UserGuidePanel guide={PAGE_GUIDES.defenseAssets} />

      <Card title="事件状态说明">
        <Table
          rowKey="status"
          pagination={false}
          size="small"
          dataSource={Object.entries(EVENT_STATUS_GUIDE).map(([status, desc]) => ({ status, desc }))}
          columns={[
            { title: "状态", dataIndex: "status", width: 140 },
            { title: "含义与您的操作", dataIndex: "desc" },
          ]}
        />
      </Card>

      <Card title="AI 结论（verdict）通俗解释">
        <Table
          rowKey="key"
          pagination={false}
          size="small"
          dataSource={Object.entries(VERDICT_GUIDE).map(([key, v]) => ({
            key,
            label: v.label,
            meaning: v.meaning,
            action: v.action,
          }))}
          columns={[
            { title: "代码", dataIndex: "key", width: 180 },
            { title: "中文", dataIndex: "label", width: 120 },
            { title: "含义", dataIndex: "meaning" },
            { title: "您该做什么", dataIndex: "action" },
          ]}
        />
      </Card>

      <Card title="常见问题">
        <Typography.Paragraph>
          <Typography.Text strong>Q：我要在哪里点「误报」或「真实攻击」？</Typography.Text>
          <br />
          A：没有人工直判按钮。请在「人工协查」补充事实，AI 复跑后会给出 likely_false_positive（误报）或
          attack_confirmed（攻击）结论。
        </Typography.Paragraph>
        <Typography.Paragraph>
          <Typography.Text strong>Q：点了「确认处置」会自动封 IP 吗？</Typography.Text>
          <br />
          A：不会。仅记录您已审阅该建议；真实封禁/隔离需在防火墙、WAF、主机安全等设备上由运维执行。
        </Typography.Paragraph>
        <Typography.Paragraph>
          <Typography.Text strong>Q：人工协查页是空的？</Typography.Text>
          <br />
          A：先确认仪表盘「协查中」是否大于 0；若大于 0，请管理员在「设置 → 协查派发」执行一次，或等待 2
          分钟自动派发。
        </Typography.Paragraph>
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          <Typography.Text strong>Q：协查问题里出现 LLM 404 报错？</Typography.Text>
          <br />
          A：这是 AI 服务配置问题，不是告警本身。请联系管理员检查 DEEPSEEK_API_KEY 和 DEEPSEEK_BASE_URL。
        </Typography.Paragraph>
      </Card>
    </Space>
  );
}
