import pytest
from app.skills.registry import skill_registry
from app.models.user import User
from app.core.database import get_db

def test_skill_authorization_required_permissions():
    """Test that a skill with required permissions fails for user without permissions."""
    # Import the admin skill to ensure it's registered
    from app.skills import admin_skill
    skill = skill_registry.get_skill("admin_skill")
    assert skill is not None
    assert skill.required_permissions == ["admin"]

    # Get a database session and create a test user with no permissions
    db = next(get_db())
    try:
        # Create a test user
        test_user = User(
            id="test-user-id-auth",
            tenant_id="712dd85e-398d-4890-a030-07f811bc159f",  # default tenant
            username="testuserauth",
            email="testuserauth@example.com",
            hashed_password="hashedpassword",
            is_active=True,
            permissions="",  # No permissions
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        # Try to execute the skill without permissions -> should raise PermissionError
        input_data = {"action": "test"}
        with pytest.raises(PermissionError) as exc_info:
            skill.execute(input_data, user=test_user)
        assert "Insufficient permissions" in str(exc_info.value)
        assert "admin_skill" in str(exc_info.value)
        assert "admin" in str(exc_info.value)

        # Now give the user the admin permission
        test_user.permissions = "admin"
        db.commit()
        db.refresh(test_user)

        # Now the skill should execute successfully
        result = skill.execute(input_data, user=test_user)
        assert result.result == "Admin action 'test' performed successfully."
    finally:
        # Clean up
        db.query(User).filter(User.id == "test-user-id-auth").delete()
        db.commit()
        db.close()

def test_skill_authorization_missing_permissions():
    """Test that a skill with multiple required permissions fails if any are missing."""
    from app.skills import admin_skill
    skill = skill_registry.get_skill("admin_skill")
    assert skill is not None

    db = next(get_db())
    try:
        # Create a temporary skill that requires two permissions
        from app.skills.registry import Skill, SkillInput, SkillOutput
        from pydantic import BaseModel

        class MultiPermInput(SkillInput):
            value: int

        class MultiPermOutput(SkillOutput):
            result: int

        def multi_perm_func(input: MultiPermInput) -> MultiPermOutput:
            return MultiPermOutput(result=input.value * 2)

        multi_perm_skill = Skill(
            name="multi_perm_skill",
            description="A skill that requires two permissions.",
            input_model=MultiPermInput,
            output_model=MultiPermOutput,
            func=multi_perm_func,
            required_permissions=["perm1", "perm2"],
        )
        skill_registry.register_skill(multi_perm_skill)

        # Create a user with only perm1
        test_user = User(
            id="test-user-id-multi",
            tenant_id="712dd85e-398d-4890-a030-07f811bc159f",  # default tenant
            username="testusermulti",
            email="testusermulti@example.com",
            hashed_password="hashedpassword",
            is_active=True,
            permissions="perm1",  # Only has perm1
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        # Try to execute the skill -> should raise PermissionError for missing perm2
        input_data = {"value": 5}
        with pytest.raises(PermissionError) as exc_info:
            multi_perm_skill.execute(input_data, user=test_user)
        assert "Insufficient permissions" in str(exc_info.value)
        assert "multi_perm_skill" in str(exc_info.value)
        assert "perm2" in str(exc_info.value)

        # Now give the user both permissions
        test_user.permissions = "perm1,perm2"
        db.commit()
        db.refresh(test_user)

        # Now the skill should execute successfully
        result = multi_perm_skill.execute(input_data, user=test_user)
        assert result.result == 10

        # Clean up the temporary skill
        skill_registry._skills.pop("multi_perm_skill", None)
    finally:
        db.query(User).filter(User.id == "test-user-id-multi").delete()
        db.commit()
        db.close()

def test_skill_authorization_unknown_identity():
    """Test that executing a skill with a None user fails if permissions are required."""
    from app.skills import admin_skill
    skill = skill_registry.get_skill("admin_skill")
    assert skill is not None

    input_data = {"action": "test"}
    # Execute with user=None -> should raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        skill.execute(input_data, user=None)
    assert "Authentication required" in str(exc_info.value)
    assert "admin_skill" in str(exc_info.value)
    assert "admin" in str(exc_info.value)
