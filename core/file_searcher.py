import os
import re
from pathlib import Path
from typing import List, Tuple

IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".devseek", "dist", "build"}
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".cpp", ".c", ".h",
    ".html", ".css", ".scss", ".json", ".yaml", ".yml", ".md", ".txt",
    ".xml", ".sql", ".sh", ".bat", ".env", ".toml", ".ini", ".cfg", ".rs",
    ".go", ".rb", ".php", ".swift", ".kt",
}
MAX_FILE_SIZE = 150 * 1024  # 150 KB

STOP_WORDS = {
    "the", "and", "or", "in", "on", "at", "to", "for", "of", "with", "a", "an",
    "que", "para", "com", "uma", "um", "como", "não", "por", "mas", "mais",
    "seu", "sua", "dos", "das", "this", "that", "from", "have", "has",
}


class FileSearcher:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def search_relevant_files(self, query: str, max_files: int = 5) -> List[Tuple[str, str]]:
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        candidates: List[Tuple[int, Path]] = []
        for file_path in self._walk_files():
            score = self._score_file(file_path, keywords)
            if score > 0:
                candidates.append((score, file_path))

        candidates.sort(reverse=True, key=lambda x: x[0])

        result = []
        for _, file_path in candidates[:max_files]:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(file_path.relative_to(self.project_path))
                result.append((rel_path, content))
            except Exception:
                continue

        return result

    def _extract_keywords(self, query: str) -> List[str]:
        words = re.findall(r"[a-zA-Z_]\w*", query)
        return [w for w in words if len(w) >= 3 and w.lower() not in STOP_WORDS]

    def _walk_files(self):
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for file in files:
                fp = Path(root) / file
                if fp.suffix.lower() in TEXT_EXTENSIONS:
                    try:
                        if fp.stat().st_size < MAX_FILE_SIZE:
                            yield fp
                    except OSError:
                        pass

    def _score_file(self, file_path: Path, keywords: List[str]) -> int:
        score = 0
        file_name = file_path.stem.lower()

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower == file_name:
                score += 20
            elif kw_lower in file_name:
                score += 10

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
            for kw in keywords:
                count = content.count(kw.lower())
                if count > 0:
                    score += min(count * 2, 10)
        except Exception:
            pass

        return score
