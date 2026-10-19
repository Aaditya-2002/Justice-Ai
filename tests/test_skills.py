import pytest
from app.skills.registry import skill_registry
from app.skills.word_count import word_count_skill


def test_word_count_skill_registered():
    """Test that the word count skill is registered."""
    assert "wordcount" in skill_registry.list_skills()


def test_word_count_skill_execution():
    """Test the word count skill execution."""
    skill = skill_registry.get_skill("wordcount")
    assert skill is not None

    input_data = {"text": "Hello world"}
    result = skill.execute(input_data)
    assert result.word_count == 2

    input_data = {"text": "This is a test."}
    result = skill.execute(input_data)
    assert result.word_count == 4

    input_data = {"text": ""}
    result = skill.execute(input_data)
    assert result.word_count == 0

    input_data = {"text": "   "}  # Only spaces
    result = skill.execute(input_data)
    assert result.word_count == 0  # split() on empty string or spaces gives []


def test_word_count_skill_invalid_input():
    """Test the word count skill with invalid input."""
    skill = skill_registry.get_skill("wordcount")
    assert skill is not None

    # Missing text field
    with pytest.raises(ValueError):
        skill.execute({})

    # text is not a string
    with pytest.raises(ValueError):
        skill.execute({"text": 123})


def test_skill_not_found():
    """Test that executing a non-existent skill raises an error."""
    with pytest.raises(ValueError):
        skill_registry.execute_skill("nonexistent", {})


def test_skill_registry_execute_skill():
    """Test the skill registry's execute_skill method."""
    input_data = {"text": "Hello world from the registry"}
    result = skill_registry.execute_skill("wordcount", input_data)
    assert result == {"word_count": 5}
