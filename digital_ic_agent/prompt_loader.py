from __future__ import annotations

from pathlib import Path

from .fpga_skills import build_fpga_skill_prompt


PROMPT_FILES = {
    "system_prompt": "system_prompt.md",
    "spec_generation": "spec_generation_prompt.md",
    "rtl_generation": "RTL_generation.md",
    "tb_generation": "TB_generation.md",
    "simulation_repair": "simulation_repair.md",
    "fpga_constraints": "FPGA_constrains_prompt.md",
}


class PromptLibrary:
    def __init__(self, prompt_dir: Path) -> None:
        self.prompt_dir = prompt_dir

    def load(self, name: str) -> str:
        try:
            file_name = PROMPT_FILES[name]
        except KeyError as exc:
            raise KeyError(f"Unknown prompt name: {name}") from exc

        path = self.prompt_dir / file_name
        if not path.exists():
            package_prompt = Path(__file__).resolve().parents[1] / "project_prompt" / file_name
            if package_prompt.exists():
                path = package_prompt
        return path.read_text(encoding="utf-8")

    def format(self, name: str, **kwargs: str) -> str:
        template = self.load(name)
        rendered = template
        for key, value in kwargs.items():
            rendered = rendered.replace(f"{{{key}}}", value)
        return rendered

    def build_shared_fpga_context(self, *, stage: str) -> str:
        sections = [
            self.load("system_prompt"),
            self.load("fpga_constraints"),
            build_fpga_skill_prompt(stage=stage),
            self._load_adaptive_feedback_memory(),
        ]
        return "\n\n".join(section.strip() for section in sections if section.strip())

    def build_stage_system_prompt(self, *, stage: str, role_instruction: str) -> str:
        return "\n\n".join(
            [
                self.build_shared_fpga_context(stage=stage),
                role_instruction.strip(),
            ]
        )

    def build_rtl_system_prompt(self) -> str:
        return self.build_shared_fpga_context(stage="rtl_generation")

    def _load_adaptive_feedback_memory(self) -> str:
        adaptive_memory_path = self.prompt_dir / "output" / "fpga_feedback_memory.md"
        if not adaptive_memory_path.exists():
            return ""
        text = adaptive_memory_path.read_text(encoding="utf-8").strip()
        if not text:
            return ""
        return "Adaptive feedback memory:\n" + text
