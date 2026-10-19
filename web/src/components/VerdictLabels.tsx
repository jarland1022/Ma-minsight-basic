import { Tag } from "antd";
import {
  DISPOSITION_GRADE_GUIDE,
  EVIDENCE_STRENGTH_GUIDE,
  VERDICT_GUIDE,
} from "../content/userGuide";

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

export function DispositionGradeTag({ grade }: { grade: string | null | undefined }) {
  if (!grade) return null;
  const info = DISPOSITION_GRADE_GUIDE[grade];
  return (
    <Tag color={info?.color || "default"} title={info?.action}>
      {info?.label ?? grade}
    </Tag>
  );
}

export function EvidenceStrengthTag({ strength }: { strength: string | null | undefined }) {
  if (!strength) return null;
  const info = EVIDENCE_STRENGTH_GUIDE[strength];
  return <Tag color={info?.color || "default"}>{info?.label ?? strength}</Tag>;
}

export function eventStatusLabel(
  status: string | null | undefined,
  t?: (path: string) => string,
): string {
  if (!status) return "—";
  if (t) {
    const key = `events.status.${status}`;
    const labeled = t(key);
    if (labeled !== key) return labeled;
  }
  const map: Record<string, string> = {
    pending_review: "Pending review",
    investigating: "Investigating",
    human_pending: "Human review",
    concluded: "Concluded",
    closed: "Closed",
  };
  return map[status] ?? status;
}
