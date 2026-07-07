"""
test_validation.py
Unit tests for validate_infographic.py, ensuring:
- Relative-max scaling does not exceed 100% when non-first element is highest.
- Part-of-whole scaling normalizes correctly.
- Dropping unsourced facts works.
- Rejection of dataset if all bars lack source references.
"""
import unittest
from validate_infographic import (
    normalize_bars,
    validate_and_source_bars,
    validate_infographic,
    ValidationError
)

class TestInfographicValidation(unittest.TestCase):

    def test_relative_max_scaling_non_first_highest(self):
        # A dataset where a non-first category has the highest raw value (25 is highest)
        bars = [
            {"label": "Seahawk", "raw_value": 24},
            {"label": "Chetak", "raw_value": 25},
            {"label": "Dhruv", "raw_value": 20}
        ]
        
        normalized = normalize_bars(bars, "relative_max")
        
        # Chetak should be 100%
        self.assertEqual(normalized[1]["value"], "100%")
        # Seahawk should be 24/25 = 96%
        self.assertEqual(normalized[0]["value"], "96%")
        # Dhruv should be 20/25 = 80%
        self.assertEqual(normalized[2]["value"], "80%")
        
        # Confirm no bar exceeds 100%
        for b in normalized:
            val_pct = float(b["value"].rstrip("%"))
            self.assertTrue(val_pct <= 100.0, f"Value {b['value']} exceeds 100%")

    def test_part_of_whole_scaling(self):
        # A dataset representing parts of a whole (operational fleet breakdown)
        bars = [
            {"label": "Operational", "raw_value": 15},
            {"label": "Training", "raw_value": 3},
            {"label": "Upgrading", "raw_value": 3},
            {"label": "Pending", "raw_value": 3}
        ]
        
        normalized = normalize_bars(bars, "part_of_whole")
        
        # Total is 24.
        # Operational: 15/24 = 62.5% -> round/formatted to 62% or 63%
        self.assertEqual(normalized[0]["value"], "62%") # 15/24 * 100 = 62.5 (Python float division block: int(15/24 * 100) or round-to-nearest depending on format string. :.0f formatting rounds 62.5 to 62 in Python's banker rounding or 62 depending on floating point representation)
        self.assertEqual(normalized[1]["value"], "12%") # 3/24 * 100 = 12.5%
        
        # Confirm no bar exceeds 100%
        for b in normalized:
            val_pct = float(b["value"].rstrip("%"))
            self.assertTrue(val_pct <= 100.0, f"Value {b['value']} exceeds 100%")

    def test_sourcing_validation_keeps_sourced_drops_unsourced(self):
        # Mock verified facts
        verified_facts = [
            {"value": 24, "source": "Navy Chief via ANI", "url": "http://example.com/24", "topic_tags": ["helicopter"]},
            {"value": 15, "source": "Navy Chief via ANI", "url": "http://example.com/15", "topic_tags": ["helicopter"]}
        ]
        
        # Bars with raw values. "Chetak (25)" is NOT in verified facts.
        bars = [
            {"label": "Seahawk Total (24)", "raw_value": 24},
            {"label": "Chetak Total (25)", "raw_value": 25},
            {"label": "Seahawk Operational (15)", "raw_value": 15}
        ]
        
        topic_tags = ["helicopter"]
        
        kept_bars = validate_and_source_bars(bars, topic_tags, verified_facts)
        
        # Should drop Chetak (25) and keep Seahawk (24) and Operational (15)
        self.assertEqual(len(kept_bars), 2)
        labels = [b["label"] for b in kept_bars]
        self.assertIn("Seahawk Total (24)", labels)
        self.assertIn("Seahawk Operational (15)", labels)
        self.assertNotIn("Chetak Total (25)", labels)
        
        # Check source attributes populated
        self.assertEqual(kept_bars[0]["source"], "Navy Chief via ANI")
        self.assertEqual(kept_bars[0]["source_url"], "http://example.com/24")

    def test_all_bars_dropped_raises_validation_error(self):
        # If no bars can be verified, validate_infographic should raise ValidationError
        verified_facts = [
            {"value": 10, "source": "A", "url": "U", "topic_tags": ["other"]}
        ]
        infographic_data = {
            "chart_type": "relative_max",
            "topic_tags": ["helicopter"],
            "bars": [
                {"label": "Unsourced (24)", "raw_value": 24}
            ]
        }
        
        with self.assertRaises(ValidationError):
            validate_infographic(infographic_data, verified_facts)

    def test_invalid_chart_type_raises_error(self):
        verified_facts = [{"value": 24, "source": "A", "url": "U", "topic_tags": ["helicopter"]}]
        infographic_data = {
            "chart_type": "invalid_type",
            "topic_tags": ["helicopter"],
            "bars": [
                {"label": "Sourced (24)", "raw_value": 24}
            ]
        }
        with self.assertRaises(ValidationError):
            validate_infographic(infographic_data, verified_facts)

if __name__ == "__main__":
    unittest.main()
