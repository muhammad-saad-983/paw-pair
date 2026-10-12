"""T05 regression: bad CLI thresholds must not overwrite mining outputs."""
import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_pipeline


class PipelineInputTests(unittest.TestCase):
    def test_rejects_invalid_thresholds_before_preprocessing(self):
        for option in ("--min-support", "--min-confidence"):
            for value in ("0", "-0.1", "1.01", "nan", "inf", "not-a-number"):
                with self.subTest(option=option, value=value):
                    with patch.object(sys, "argv", ["run_pipeline.py", option, value]), \
                         patch.object(run_pipeline, "profile") as mock_profile, \
                         redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as exit_result:
                            run_pipeline.main()
                        self.assertEqual(exit_result.exception.code, 2)
                        mock_profile.assert_not_called()

    def test_boundary_thresholds_are_valid(self):
        self.assertEqual(run_pipeline.unit_interval("1"), 1.0)
        self.assertEqual(run_pipeline.unit_interval("0.002"), 0.002)


if __name__ == "__main__":
    unittest.main()
