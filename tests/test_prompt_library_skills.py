import tempfile
import unittest
from pathlib import Path

from digital_ic_agent.prompt_loader import PromptLibrary


class PromptLibrarySkillsTest(unittest.TestCase):
    def test_build_stage_prompt_includes_stage_relevant_skills_and_feedback_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = Path(temp_dir)
            (prompt_dir / "system_prompt.md").write_text("base system", encoding="utf-8")
            (prompt_dir / "FPGA_constrains_prompt.md").write_text("fpga constraints", encoding="utf-8")
            output_dir = prompt_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "fpga_feedback_memory.md").write_text("Top recurring issue: narrow carry handling.", encoding="utf-8")

            library = PromptLibrary(prompt_dir)

            prompt_text = library.build_stage_system_prompt(
                stage="rtl_generation",
                role_instruction="Role text.",
            )

            self.assertIn("base system", prompt_text)
            self.assertIn("fpga constraints", prompt_text)
            self.assertIn("Arithmetic Width and Signedness Discipline", prompt_text)
            self.assertIn("Adaptive feedback memory", prompt_text)
            self.assertIn("Role text.", prompt_text)

    def test_build_stage_prompt_filters_out_unrelated_skills(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = Path(temp_dir)
            (prompt_dir / "system_prompt.md").write_text("base system", encoding="utf-8")
            (prompt_dir / "FPGA_constrains_prompt.md").write_text("fpga constraints", encoding="utf-8")

            library = PromptLibrary(prompt_dir)

            prompt_text = library.build_stage_system_prompt(
                stage="tb_generation",
                role_instruction="Role text.",
            )

            self.assertIn("External Stimulus and Self-Checking Testbench", prompt_text)
            self.assertNotIn("Clock and Reset Discipline", prompt_text)


if __name__ == "__main__":
    unittest.main()