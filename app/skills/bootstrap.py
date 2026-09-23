"""Register built-in investigation skills."""

import app.skills.query_asset  # noqa: F401
import app.skills.query_entity_graph  # noqa: F401
import app.skills.query_history_alerts  # noqa: F401
import app.skills.query_threat_intel  # noqa: F401
import app.skills.simulate_disposition  # noqa: F401
from app.skills.query_asset import QueryAssetSkill
from app.skills.query_entity_graph import QueryEntityGraphSkill
from app.skills.query_history_alerts import QueryHistoryAlertsSkill
from app.skills.query_threat_intel import QueryThreatIntelSkill
from app.skills.simulate_disposition import SimulateDispositionSkill
from app.skills.registry import SkillRegistry

SkillRegistry.register(QueryAssetSkill)
SkillRegistry.register(QueryEntityGraphSkill)
SkillRegistry.register(QueryHistoryAlertsSkill)
SkillRegistry.register(QueryThreatIntelSkill)
SkillRegistry.register(SimulateDispositionSkill)
