"""FlowGuard contract export for the ResearchGuard umbrella Skill."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchguard_skill_contract_model_common import build_contract_model


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_contract_model("researchguard")
