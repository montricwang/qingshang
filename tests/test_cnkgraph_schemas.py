"""验证 CNKGraph Tool Layer 的本地响应契约。"""

from unittest import TestCase

from app.schemas.cnkgraph import EvidenceItem, ReadingAidResponse


class CNKGraphSchemaTests(TestCase):
    def test_evidence_item_keeps_raw_without_exposing_it_as_main_fields(self) -> None:
        evidence = EvidenceItem(
            tool_name="allusion",
            anchor_text="前度刘郎",
            title="刘郎",
            raw={"Id": 123, "UnstableExternalField": ["value"]},
        )

        self.assertEqual(evidence.title, "刘郎")
        self.assertEqual(evidence.raw, {"Id": 123, "UnstableExternalField": ["value"]})
        self.assertEqual(evidence.match_status, "candidate")

    def test_reading_aid_list_defaults_are_independent(self) -> None:
        first = ReadingAidResponse(poem_id="test-0001")
        second = ReadingAidResponse(poem_id="test-0002")

        first.errors.append("upstream unavailable")

        self.assertEqual(second.errors, [])
