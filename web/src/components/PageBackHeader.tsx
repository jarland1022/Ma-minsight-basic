import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { Link } from "react-router-dom";

type PageBackHeaderProps = {
  to: string;
  label: string;
};

export default function PageBackHeader({ to, label }: PageBackHeaderProps) {
  return (
    <Link to={to}>
      <Button type="link" icon={<ArrowLeftOutlined />} style={{ paddingLeft: 0, marginBottom: 8 }}>
        {label}
      </Button>
    </Link>
  );
}
