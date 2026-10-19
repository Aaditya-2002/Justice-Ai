from typing import Dict, Any, Optional, List, Callable
from pydantic import BaseModel, ValidationError
import logging
import json
from app.models.user import User

logger = logging.getLogger(__name__)


class SkillInput(BaseModel):
    """Base class for skill input validation."""
    pass


class SkillOutput(BaseModel):
    """Base class for skill output."""
    pass


class Skill:
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[SkillInput],
        output_model: type[SkillOutput],
        func: Callable[[SkillInput], SkillOutput],
        required_permissions: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.output_model = output_model
        self.func = func
        self.required_permissions = required_permissions or []

    def execute(self, input_data: Dict[str, Any], user: Optional[User] = None) -> SkillOutput:
        # Validate input
        try:
            input_obj = self.input_model(**input_data)
        except ValidationError as e:
            logger.error(f"Skill {self.name} input validation failed: {e}")
            raise ValueError(f"Invalid input for skill {self.name}: {e}")

        # Check permissions if required
        if self.required_permissions:
            if user is None:
                raise PermissionError(f"Authentication required to execute skill {self.name}")
            # Get the user's permissions as a list
            user_permissions = []
            if user.permissions:
                user_permissions = [p.strip() for p in user.permissions.split(',') if p.strip()]
            # Check if the user has all required permissions
            missing_permissions = [perm for perm in self.required_permissions if perm not in user_permissions]
            if missing_permissions:
                raise PermissionError(f"Insufficient permissions to execute skill {self.name}. Missing permissions: {missing_permissions}")
        try:
            result = self.func(input_obj)
            # Validate output
            if not isinstance(result, self.output_model):
                # If the function returns a dict, try to convert it to the output model
                if isinstance(result, dict):
                    result = self.output_model(**result)
                else:
                    raise ValueError(f"Skill {self.name} did not return an instance of {self.output_model}")
            return result
        except Exception as e:
            logger.error(f"Skill {self.name} execution failed: {e}")
            raise


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def register_skill(self, skill: Skill) -> None:
        if skill.name in self._skills:
            logger.warning(f"Skill {skill.name} is already registered. Overwriting.")
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())

    def execute_skill(self, name: str, input_data: Dict[str, Any], user: Optional[User] = None) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if skill is None:
            raise ValueError(f"Skill {name} not found")
        try:
            output = skill.execute(input_data, user=user)
            return output.dict()
        except Exception as e:
            logger.error(f"Failed to execute skill {name}: {e}")
            raise


# Global skill registry instance
skill_registry = SkillRegistry()
