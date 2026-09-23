import { Tag } from "antd";
import { VERDICT_GUIDE } from "../content/userGuide";

export function verdictLabel(verdict: string | null | undefined): string {
  if (!verdict) return "—";
  return VERDICT_GUIDE[verdict]?.label ?? verdict;
}

export function VerdictTag({ verdict }: { verdict: string | null | undefined }) {
  if (!verdict) return null;
  const info = VERDICT_GUIDE[verdict];
  const color =
    verdict === "attack_confirmed"
      ? "red"
      : verdict === "likely_false_positive"
        ? "green"
        : verdict === "needs_human_review" || verdict === "insufficient_information"
          ? "orange"
          : "blue";
  return (
    <Tag color={color} title={info?.meaning}>
      {info?.label ?? verdict}
    </Tag>
  );
}

export function eventStatusLabel(status: string | null | undefined): string {
  const map: Record<string, string> = {
    pending_review: "待调查",
    investigating: "调查中",
    human_pending: "协查中",
    concluded: "已结论",
    closed: "已关闭",
  };
  if (!status) return "—";
  return map[status] ?? status;
}
