from typing import Optional
from pydantic import BaseModel
from app.skills.registry import SkillInput, SkillOutput, Skill


class WordCountInput(SkillInput):
    text: str


class WordCountOutput(SkillOutput):
    word_count: int


def word_count_func(input: WordCountInput) -> WordCountOutput:
    words = input.text.split()
    return WordCountOutput(word_count=len(words))


word_count_skill = Skill(
    name="wordcount",
    description="Counts the number of words in the given text.",
    input_model=WordCountInput,
    output_model=WordCountOutput,
    func=word_count_func,
    required_permissions=[],  # No special permissions required
)

# Register the skill when the module is imported
from app.skills.registry import skill_registry
skill_registry.register_skill(word_count_skill)
