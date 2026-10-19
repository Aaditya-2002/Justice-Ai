from typing import Optional
from pydantic import BaseModel
from app.skills.registry import SkillInput, SkillOutput, Skill

class AdminSkillInput(SkillInput):
    action: str

class AdminSkillOutput(SkillOutput):
    result: str

def admin_skill_func(input: AdminSkillInput) -> AdminSkillOutput:
    return AdminSkillOutput(result=f"Admin action '{input.action}' performed successfully.")

admin_skill = Skill(
    name="admin_skill",
    description="A skill that requires admin permissions.",
    input_model=AdminSkillInput,
    output_model=AdminSkillOutput,
    func=admin_skill_func,
    required_permissions=["admin"],  # Requires admin permission
)

# Register the skill when the module is imported
from app.skills.registry import skill_registry
skill_registry.register_skill(admin_skill)
