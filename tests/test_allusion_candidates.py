"""测试典故候选提示词、原文定位与数量约束，不调用真实 LLM。"""

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from app.services.allusion_candidate_extractor import (
    build_allusion_candidate_prompt,
    extract_allusion_candidates,
    filter_allusion_candidates,
)


def make_poem() -> SimpleNamespace:
    lines = [
        SimpleNamespace(
            global_line_no=1,
            section_line_no=1,
            text="柳阴直，烟里丝丝弄碧。",
        ),
        SimpleNamespace(
            global_line_no=2,
            section_line_no=2,
            text="隋堤上、曾见几番，拂水飘绵送行色。",
        ),
        SimpleNamespace(
            global_line_no=3,
            section_line_no=3,
            text="又酒趁哀弦，灯照离席。梨花榆火催寒食。",
        ),
    ]
    return SimpleNamespace(
        poem_id="zhoubangyan-test",
        author="周邦彦",
        tune_name="兰陵王",
        title="柳",
        preface=None,
        sections=[
            SimpleNamespace(section_no=1, section_name="上片", lines=lines)
        ],
    )


def candidate(
    line_no: int,
    anchor_text: str,
    candidate_type: str = "allusion",
) -> dict[str, object]:
    return {
        "line_no": line_no,
        "anchor_text": anchor_text,
        "candidate_type": candidate_type,
        "query": anchor_text,
        "reason": "该短语可能带有固定文化语境，值得进一步查证。",
        "confidence": "medium",
    }


class AllusionCandidateFilterTests(TestCase):
    def test_prompt_draws_a_narrow_boundary(self) -> None:
        messages = build_allusion_candidate_prompt(make_poem())
        prompt = "\n".join(message["content"] for message in messages)

        self.assertIn("兰陵王", prompt)
        self.assertIn("隋堤上", prompt)
        self.assertIn("不要识别普通意象", prompt)
        self.assertIn("不得声称候选出自某书", prompt)

    def test_filter_rejects_bad_anchors_and_limits_each_line(self) -> None:
        raw = [
            candidate(2, "隋堤", "historical_place"),
            candidate(2, "送行色", "conventional_motif"),
            candidate(2, "拂水"),
            candidate(1, "不存在的原文"),
            candidate(99, "隋堤"),
            candidate(3, "榆火", "cultural_institution"),
        ]

        result = filter_allusion_candidates(raw, make_poem())

        self.assertEqual([item.anchor_text for item in result], ["隋堤", "送行色", "榆火"])
        self.assertTrue(all(item.anchor_text in make_poem().sections[0].lines[item.line_no - 1].text for item in result))
        self.assertNotIn("隋炀帝", result[0].reason)
        self.assertIn("历史文化语境", result[0].reason)

    def test_filter_limits_the_whole_poem_to_ten_candidates(self) -> None:
        poem = make_poem()
        poem.sections[0].lines = [
            SimpleNamespace(
                global_line_no=line_no,
                section_line_no=line_no,
                text=f"候选{line_no}甲，候选{line_no}乙。",
            )
            for line_no in range(1, 7)
        ]
        raw = [
            candidate(line_no, f"候选{line_no}{suffix}", "uncertain")
            for line_no in range(1, 7)
            for suffix in ("甲", "乙")
        ]

        result = filter_allusion_candidates(raw, poem)

        self.assertEqual(len(result), 10)


class AllusionCandidateExtractorTests(IsolatedAsyncioTestCase):
    async def test_extractor_parses_json_and_returns_narrow_response(self) -> None:
        mocked_response = json.dumps(
            {
                "candidates": [
                    candidate(2, "隋堤", "historical_place"),
                    candidate(3, "榆火", "cultural_institution"),
                    candidate(3, "寒食", "cultural_institution"),
                ]
            },
            ensure_ascii=False,
        )
        with patch(
            "app.services.allusion_candidate_extractor.chat_completion",
            new=AsyncMock(return_value=mocked_response),
        ):
            result = await extract_allusion_candidates(make_poem())

        self.assertEqual(result.poem_id, "zhoubangyan-test")
        self.assertEqual([item.anchor_text for item in result.candidates], ["隋堤", "榆火", "寒食"])
        self.assertLessEqual(len(result.candidates), 10)
