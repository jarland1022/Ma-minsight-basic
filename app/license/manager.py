"""MA-MinSight License Manager (Ma-WAF aligned: ECDSA P-256 + SHA-256)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.license.edition import is_community_edition

PRODUCT_NAME = "MA-MinSight"
FP_V2_PREFIX = "ma-minsight-fp-v2"
FP_DEV_PREFIX = "ma-minsight-dev:"

ERR_EXPIRED = "license_expired"
ERR_FINGERPRINT = "fingerprint_mismatch"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_license_dir() -> Path:
    override = os.environ.get("MA_MINSIGHT_LICENSE_DIR", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "configs" / "license"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _secure_equal(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)


def _read_trimmed(path: Path) -> str | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw or raw.lower() == "not settable":
        return None
    return raw


def _read_windows_machine_guid() -> str | None:
    try:
        import winreg  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if isinstance(value, str) and value.strip():
                return value.strip()
    except OSError:
        return None
    return None


@dataclass
class FingerprintCandidate:
    hash: str
    source: str


@dataclass
class Payload:
    client_name: str
    issue_date: str
    expiry_date: str
    fingerprint: str
    product: str = ""
    max_nodes: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Payload:
        max_nodes = int(data.get("max_nodes") or data.get("max_sites") or 0)
        return cls(
            client_name=str(data.get("client_name", "")),
            issue_date=str(data.get("issue_date", "")),
            expiry_date=str(data.get("expiry_date", "")),
            fingerprint=str(data.get("fingerprint", "")),
            product=str(data.get("product", "")),
            max_nodes=max_nodes,
        )


@dataclass
class Status:
    activated: bool = False
    status: str = "inactive"
    client_name: str = ""
    issue_date: str = ""
    expiry_date: str = ""
    days_remaining: int = 0
    parse_error: str = ""
    grace_remaining_hours: float = 0.0
    grace_elapsed_hours: float = 0.0
    grace_expired: bool = False
    product: str = PRODUCT_NAME
    hint: str = ""
    max_nodes: int = 0
    fingerprint_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Manager:
    """License verification, grace period, and import."""

    def __init__(
        self,
        license_dir: Path | str | None = None,
        *,
        grace_hours: float = 72.0,
    ) -> None:
        root = Path(license_dir) if license_dir else _default_license_dir()
        self.license_dir = root
        self.license_file = root / "license.lic"
        self.public_key_file = root / "ma-minsight-public.pem"
        self.grace_file = root / ".grace_start"
        self.grace_expired_file = root / ".grace_expired"
        self.grace_hours = grace_hours

    @classmethod
    def default(cls, product_root: Path | str | None = None) -> Manager:
        if product_root is not None:
            return cls(Path(product_root) / "configs" / "license")
        return cls()

    def fingerprint_candidates(self) -> list[FingerprintCandidate]:
        out: list[FingerprintCandidate] = []
        uuid = _read_trimmed(Path("/sys/class/dmi/id/product_uuid"))
        mid = _read_trimmed(Path("/etc/machine-id"))

        if uuid is None:
            uuid = _read_windows_machine_guid()
            if uuid:
                uuid = uuid.lower()

        if uuid and mid:
            out.append(
                FingerprintCandidate(
                    hash=_sha256_hex(f"{FP_V2_PREFIX}|uuid:{uuid}|mid:{mid}"),
                    source="dmi_product_uuid+machine-id",
                )
            )
        if uuid:
            out.append(
                FingerprintCandidate(
                    hash=_sha256_hex(uuid),
                    source="dmi_product_uuid",
                )
            )
        if mid:
            out.append(
                FingerprintCandidate(
                    hash=_sha256_hex(mid),
                    source="machine-id",
                )
            )
        if out:
            return out

        host = socket.gethostname()
        if not host:
            return []
        return [
            FingerprintCandidate(
                hash=_sha256_hex(f"{FP_DEV_PREFIX}{host}"),
                source="hostname",
            )
        ]

    def hardware_fingerprint(self) -> tuple[str, str]:
        cands = self.fingerprint_candidates()
        if not cands:
            raise RuntimeError("无法采集硬件指纹")
        return cands[0].hash, cands[0].source

    def fingerprint_detail(self) -> dict[str, str]:
        fp_hash, source = self.hardware_fingerprint()
        detail = {
            "fingerprint": fp_hash,
            "source": source,
            "hint": (
                "将 fingerprint 发给厂商（微信 jarlandliu / jarland@mingansec.com），"
                "获取专业版 license.lic 后在控制台导入"
            ),
            "algo": FP_V2_PREFIX,
        }
        cands = self.fingerprint_candidates()
        if len(cands) > 1:
            legacy = [f"{c.hash}({c.source})" for c in cands[1:]]
            detail["legacy_accepted"] = ", ".join(legacy)
        return detail

    def _load_public_key(self) -> ec.EllipticCurvePublicKey:
        if not self.public_key_file.is_file():
            raise FileNotFoundError(f"公钥不存在: {self.public_key_file}")
        pub = serialization.load_pem_public_key(self.public_key_file.read_bytes())
        if not isinstance(pub, ec.EllipticCurvePublicKey):
            raise ValueError("需要 ECDSA P-256 公钥")
        if pub.curve.name != "secp256r1":
            raise ValueError("需要 ECDSA P-256 公钥")
        return pub

    def parse_and_verify(self, path: Path | str | None = None) -> Payload:
        lic_path = Path(path) if path else self.license_file
        if not lic_path.is_file():
            raise FileNotFoundError(f"License 文件不存在: {lic_path}")

        try:
            combined = base64.b64decode(lic_path.read_text(encoding="utf-8").strip())
        except Exception as exc:
            raise ValueError(f"Base64 解码失败: {exc}") from exc

        dot = combined.rfind(b".")
        if dot < 0:
            raise ValueError("License 结构错误：缺少签名分隔符")

        payload_bytes = combined[:dot]
        sig_b64 = combined[dot + 1 :]
        try:
            sig = base64.b64decode(sig_b64)
        except Exception as exc:
            raise ValueError(f"签名解码失败: {exc}") from exc

        pub = self._load_public_key()
        try:
            pub.verify(sig, payload_bytes, ec.ECDSA(hashes.SHA256()))
        except InvalidSignature as exc:
            raise ValueError("签名验证失败，文件可能被篡改") from exc

        try:
            data = json.loads(payload_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"载荷 JSON 解析失败: {exc}") from exc

        payload = Payload.from_dict(data)
        for field_name in (
            payload.client_name,
            payload.issue_date,
            payload.expiry_date,
            payload.fingerprint,
        ):
            if not str(field_name).strip():
                raise ValueError("License 缺少必要字段")
        return payload

    def verify_full(self, path: Path | str | None = None) -> tuple[Payload, int]:
        payload = self.parse_and_verify(path)
        try:
            expiry = datetime.strptime(payload.expiry_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"有效期格式错误: {payload.expiry_date}") from exc

        today = date.today()
        if today > expiry:
            raise RuntimeError(f"{ERR_EXPIRED}: {payload.expiry_date}")

        want = payload.fingerprint.strip().lower()
        matched = any(_secure_equal(c.hash, want) for c in self.fingerprint_candidates())
        if not matched:
            raise RuntimeError(ERR_FINGERPRINT)

        days = (expiry - today).days
        return payload, days

    @staticmethod
    def _classify_verify_error(err: Exception) -> tuple[str, str]:
        msg = str(err)
        if ERR_EXPIRED in msg or "已过期" in msg:
            return "expired", "License 已过期，变更类操作已锁定；请续期后重新导入"
        if ERR_FINGERPRINT in msg or "指纹" in msg:
            return "fingerprint_mismatch", "硬件指纹不匹配，本机无法使用该 License"
        if "签名" in msg:
            return "invalid", "License 签名校验失败，文件可能被篡改"
        return "invalid", f"License 无效: {msg}"

    def _fill_payload_meta(self, info: Status, payload: Payload | None) -> None:
        if payload is None:
            return
        info.client_name = payload.client_name
        info.issue_date = payload.issue_date
        info.expiry_date = payload.expiry_date
        info.product = payload.product or PRODUCT_NAME
        info.max_nodes = payload.max_nodes

    def status(self) -> Status:
        info = Status(activated=False, status="inactive", product=PRODUCT_NAME)
        try:
            _, source = self.hardware_fingerprint()
            info.fingerprint_source = source
        except RuntimeError:
            pass

        if self.license_file.is_file():
            payload: Payload | None = None
            try:
                payload, days = self.verify_full(self.license_file)
                info.activated = True
                info.status = "active"
                info.days_remaining = days
                self._fill_payload_meta(info, payload)
                self.grace_file.unlink(missing_ok=True)
                self.grace_expired_file.unlink(missing_ok=True)
                return info
            except Exception as exc:
                info.parse_error = str(exc)
                st, hint = self._classify_verify_error(exc)
                info.status = st
                info.hint = hint
                if payload is not None:
                    self._fill_payload_meta(info, payload)
                else:
                    try:
                        self._fill_payload_meta(info, self.parse_and_verify(self.license_file))
                    except Exception:
                        pass
                return info

        # Community packaging: no silent Pro trial. Core triage stays free;
        # Agent / WeCom / defense / eval need an imported license.lic.
        if is_community_edition():
            info.status = "community"
            info.hint = (
                "当前为社区版：入库/初筛/聚合/事件台可用。"
                "导入专业版 license.lic 后可解锁 AI Agent、企微协查、防御资产与评测。"
            )
            return info

        if self.grace_expired_file.is_file():
            info.status = "grace_expired"
            info.grace_expired = True
            info.hint = "试用宽限期已结束，请导入有效 license.lic"
            return info

        if self.grace_file.is_file():
            start = self._parse_grace_start(self.grace_file.read_text(encoding="utf-8"))
            if start is not None:
                elapsed = (datetime.now() - start).total_seconds() / 3600.0
                remain = self.grace_hours - elapsed
                info.grace_elapsed_hours = round(elapsed, 1)
                if remain > 0:
                    info.status = "grace_period"
                    info.grace_remaining_hours = round(remain, 1)
                    info.hint = "未激活 License，处于试用宽限期"
                    return info
                self.grace_expired_file.write_text(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    encoding="utf-8",
                )
                info.status = "grace_expired"
                info.grace_expired = True
                info.grace_remaining_hours = 0.0
                info.hint = "试用宽限期已结束，请导入有效 license.lic"
                return info

        self.license_dir.mkdir(parents=True, exist_ok=True)
        if not self.grace_file.is_file():
            self.grace_file.write_text(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                encoding="utf-8",
            )
            info.status = "grace_period"
            info.grace_remaining_hours = self.grace_hours
            info.hint = "已进入试用宽限期，请尽快导入 License"
            return info

        info.status = "no_license"
        info.hint = "请在控制台导入 license.lic（由厂商签发）"
        return info

    @staticmethod
    def _parse_grace_start(raw: str) -> datetime | None:
        text = raw.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S",):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def allow_operation(self) -> bool:
        st = self.status().status
        return st in ("active", "grace_period")

    def allow_nodes(self, current_count: int) -> bool:
        if not self.allow_operation():
            return False
        st = self.status()
        if st.max_nodes <= 0:
            return True
        return current_count < st.max_nodes

    def import_file(self, src: Path | str) -> None:
        src_path = Path(src)
        self.license_dir.mkdir(parents=True, exist_ok=True)
        backup = self.license_file.with_suffix(".lic.bak")
        if self.license_file.is_file():
            self.license_file.replace(backup)

        try:
            self.license_file.write_bytes(src_path.read_bytes())
            self.verify_full(self.license_file)
        except Exception as exc:
            self.license_file.unlink(missing_ok=True)
            if backup.is_file():
                backup.replace(self.license_file)
            raise RuntimeError(f"导入失败（未生效）: {exc}") from exc

        self.grace_file.unlink(missing_ok=True)
        self.grace_expired_file.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)


_manager: Manager | None = None


def get_manager() -> Manager:
    global _manager
    if _manager is None:
        _manager = Manager()
    return _manager
