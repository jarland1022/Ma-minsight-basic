import { Alert, Collapse, Typography } from "antd";
import type { GuideSection } from "../content/userGuide";

type Props = {
  guide: GuideSection;
  defaultExpanded?: boolean;
  type?: "info" | "success" | "warning";
};

function renderList(title: string, items: string[] | undefined, ordered = false) {
  if (!items?.length) return null;
  const Tag = ordered ? "ol" : "ul";
  return (
    <div style={{ marginTop: 8 }}>
      <Typography.Text strong>{title}</Typography.Text>
      <Tag style={{ marginTop: 4, paddingLeft: 20, marginBottom: 0 }}>
        {items.map((item) => (
          <li key={item} style={{ marginBottom: 4 }}>
            {item}
          </li>
        ))}
      </Tag>
    </div>
  );
}

export default function UserGuidePanel({
  guide,
  defaultExpanded = false,
  type = "info",
}: Props) {
  const body = (
    <>
      {guide.summary && (
        <Typography.Paragraph style={{ marginBottom: 8 }}>{guide.summary}</Typography.Paragraph>
      )}
      {renderList("操作步骤", guide.steps, true)}
      {renderList("参考回复示例", guide.examples)}
      {renderList("温馨提示", guide.tips)}
      {guide.warnings?.length ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 12 }}
          message="请注意"
          description={
            <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
              {guide.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          }
        />
      ) : null}
    </>
  );

  if (defaultExpanded) {
    return (
      <Alert type={type} showIcon message={guide.title} description={body} style={{ marginBottom: 16 }} />
    );
  }

  return (
    <Collapse
      style={{ marginBottom: 16 }}
      items={[
        {
          key: "guide",
          label: guide.title,
          children: body,
        },
      ]}
    />
  );
}
