"""Prompt templates — stored per project in .devseek/templates.json"""
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List


@dataclass
class PromptTemplate:
    name: str
    text: str
    tags: List[str] = field(default_factory=list)


class TemplateManager:
    def __init__(self, devseek_path: Path):
        self._path = devseek_path / "templates.json"
        self._templates: list[PromptTemplate] = []
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._templates = [PromptTemplate(**d) for d in data]
            except Exception:
                self._templates = []
        else:
            self._templates = _DEFAULT_TEMPLATES[:]

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([asdict(t) for t in self._templates], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_all(self) -> list[PromptTemplate]:
        return list(self._templates)

    def add(self, template: PromptTemplate):
        self._templates.append(template)
        self._save()

    def update(self, index: int, template: PromptTemplate):
        if 0 <= index < len(self._templates):
            self._templates[index] = template
            self._save()

    def delete(self, index: int):
        if 0 <= index < len(self._templates):
            del self._templates[index]
            self._save()


_DEFAULT_TEMPLATES = [
    PromptTemplate(
        name="Revisar código",
        text="Revise o código a seguir buscando bugs, problemas de performance e más práticas:\n\n```\n[cole o código aqui]\n```",
        tags=["revisão"],
    ),
    PromptTemplate(
        name="Explicar código",
        text="Explique passo a passo o que este código faz:\n\n```\n[cole o código aqui]\n```",
        tags=["explicação"],
    ),
    PromptTemplate(
        name="Criar testes",
        text="Crie testes unitários para a seguinte função/classe:\n\n```\n[cole o código aqui]\n```",
        tags=["testes"],
    ),
    PromptTemplate(
        name="Otimizar",
        text="Sugira otimizações de performance para o código abaixo. Mantenha a legibilidade:\n\n```\n[cole o código aqui]\n```",
        tags=["performance"],
    ),
    PromptTemplate(
        name="Documentar",
        text="Adicione docstrings e comentários explicativos ao código abaixo:\n\n```\n[cole o código aqui]\n```",
        tags=["docs"],
    ),
]
