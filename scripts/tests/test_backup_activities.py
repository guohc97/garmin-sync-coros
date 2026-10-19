import unittest

from scripts.backup_activities import activity_timestamp


class ActivityTimestampTests(unittest.TestCase):
    def test_formats_garmin_local_start_time(self):
        self.assertEqual(
            activity_timestamp({"startTimeLocal": "2026-09-07 09:22:27"}),
            "20260907T092227",
        )

    def test_formats_coros_epoch_milliseconds(self):
        self.assertEqual(
            activity_timestamp({"startTime": 1_788_769_347_000}),
            "20260907T082227",
        )


if __name__ == "__main__":
    unittest.main()
