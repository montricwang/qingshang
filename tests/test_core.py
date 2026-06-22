"""不访问真实数据库和 LLM 的核心回归测试。"""

from types import SimpleNamespace
from unittest import TestCase

from app.main import app
from app.schemas.poem import PoemCore
from app.services.poem_analyzer import extract_json
from scripts.clean_zhoubangyan_working_text import parse_meta_line, split_lines


class PoemSchemaTests(TestCase):
    def test_poem_core_validates_nested_orm_objects(self) -> None:
        poem = SimpleNamespace(
            poem_id="test-0001",
            author_order=1,
            author="测试作者",
            dynasty="宋",
            tune_name="测试词牌",
            musical_mode=None,
            title=None,
            series_label=None,
            preface=None,
            full_text="第一句。第二句。",
            source=None,
            sections=[
                SimpleNamespace(
                    section_no=1,
                    section_name=None,
                    lines=[
                        SimpleNamespace(
                            global_line_no=1,
                            section_line_no=1,
                            text="第一句。",
                        ),
                        SimpleNamespace(
                            global_line_no=2,
                            section_line_no=2,
                            text="第二句。",
                        ),
                    ],
                )
            ],
        )

        result = PoemCore.model_validate(poem)

        self.assertEqual(result.poem_id, "test-0001")
        self.assertEqual(result.sections[0].lines[1].text, "第二句。")


class AnalyzerTests(TestCase):
    def test_extract_json_removes_markdown_fence(self) -> None:
        self.assertEqual(extract_json('```json\n{"ok": true}\n```'), '{"ok": true}')


class RouteTests(TestCase):
    def test_openapi_contains_only_supported_api_routes(self) -> None:
        paths = app.openapi()["paths"]

        self.assertIn("/api/poems", paths)
        self.assertIn("/api/poems/{poem_id}/allusion-candidates", paths)
        self.assertNotIn("/api/poetry/explain", paths)
        self.assertNotIn("/api/chat/test", paths)


class CleanerTests(TestCase):
    def test_parse_meta_line_extracts_mode_and_title(self) -> None:
        result = parse_meta_line("大石秋怨")

        self.assertEqual(result["musical_mode"], "大石")
        self.assertEqual(result["title"], "秋怨")

    def test_split_lines_keeps_global_numbering(self) -> None:
        lines, next_number = split_lines("第一句，第二句。", 3)

        self.assertEqual([line["global_line_no"] for line in lines], [3, 4])
        self.assertEqual(next_number, 5)
