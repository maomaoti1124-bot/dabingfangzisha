#!/usr/bin/env python3
"""Build an importable WorkBuddy ZIP from the shared conversation skill."""

import json
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "dabing-fangzisha-skill"


def build(output=None):
    output = Path(output) if output else ROOT / "dist" / "dabing-fangzisha-workbuddy.zip"
    parts = (ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)
    if len(parts) != 3 or not parts[2].strip():
        raise ValueError("SKILL.md is missing its frontmatter or body")
    fields = {
        "name": NAME,
        "display_name": "大冰防zisha skill",
        "description": "支持表达当前自杀或自伤念头的用户，或协助关心此类亲友的人；引用文本或编写文档不自动视为当前危机。",
        "description_zh": "温和倾听、关注当下安全，并帮助连接现实陪伴和专业支持的对话原型。",
        "description_en": "A supportive conversation prototype for people expressing suicidal or self-harm thoughts and those supporting them; not a clinical or emergency service.",
        "version": "0.1.0",
        "author": "maomaoti1124-bot",
    }
    header = "---\n" + "\n".join(key + ": " + json.dumps(value, ensure_ascii=False) for key, value in fields.items()) + "\n---"
    files = {NAME + "/SKILL.md": (header + parts[2]).encode("utf-8")}
    # Deliberate allowlist: no API keys, application files or personal corpus.
    reference = "references/conversation-examples.md"
    files[NAME + "/" + reference] = (ROOT / reference).read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)
    return output


if __name__ == "__main__":
    print(build())
