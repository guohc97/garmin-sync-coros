"""Download Garmin or COROS activities to a local backup directory."""

import argparse
import io
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

from coros.coros_client import CorosClient
from garmin.garmin_client import GarminClient


TIMESTAMP_FIELDS = (
    "startTimeLocal",
    "startTime",
    "startTimeGMT",
    "beginTime",
    "startTimeStamp",
)


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set.")
    return value


def activity_timestamp(activity: dict) -> str:
    for field in TIMESTAMP_FIELDS:
        value = activity.get(field)
        if value is None or value == "":
            continue

        if isinstance(value, (int, float)) or (
            isinstance(value, str) and value.replace(".", "", 1).isdigit()
        ):
            seconds = float(value)
            if seconds > 100_000_000_000:
                seconds /= 1_000
            return datetime.fromtimestamp(seconds, timezone.utc).strftime(
                "%Y%m%dT%H%M%S"
            )

        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized).strftime("%Y%m%dT%H%M%S")
            except ValueError:
                continue

    raise RuntimeError(
        "Activity does not include a recognized start timestamp "
        f"({', '.join(TIMESTAMP_FIELDS)})."
    )


def backup_exists(output_dir: Path, activity_id: Union[int, str]) -> bool:
    legacy_files = (
        output_dir / f"{activity_id}.fit",
        output_dir / f"{activity_id}.zip",
    )
    return any(path.exists() for path in legacy_files) or any(
        output_dir.glob(f"*_{activity_id}.fit")
    ) or any(output_dir.glob(f"*_{activity_id}.zip"))


def write_activity(destination: Path, content: bytes, overwrite: bool) -> bool:
    if destination.exists() and not overwrite:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return True


def backup_garmin(output_dir: Path, overwrite: bool) -> tuple[int, int]:
    client = GarminClient(
        required_environment("GARMIN_EMAIL"),
        required_environment("GARMIN_PASSWORD"),
        os.getenv("GARMIN_AUTH_DOMAIN", "COM"),
        0,
    )
    downloaded = 0
    skipped = 0

    for activity in client.getAllActivities():
        activity_id = activity["activityId"]
        if not overwrite and backup_exists(output_dir, activity_id):
            skipped += 1
            continue
        destination = output_dir / f"{activity_timestamp(activity)}_{activity_id}.zip"
        if write_activity(destination, client.downloadFitActivity(activity_id), overwrite):
            downloaded += 1

    return downloaded, skipped


def backup_coros(output_dir: Path, overwrite: bool) -> tuple[int, int]:
    client = CorosClient(
        required_environment("COROS_EMAIL"),
        required_environment("COROS_PASSWORD"),
    )
    client.login()
    downloaded = 0
    skipped = 0

    for activity in client.getAllActivities():
        activity_id = activity["labelId"]
        sport_type = activity["sportType"]
        if not overwrite and backup_exists(output_dir, activity_id):
            skipped += 1
            continue
        response = client.downloadActivitie(activity_id, sport_type)
        content = response.data
        extension = "zip" if zipfile.is_zipfile(io.BytesIO(content)) else "fit"
        destination = output_dir / (
            f"{activity_timestamp(activity)}_{activity_id}.{extension}"
        )
        if write_activity(destination, content, overwrite):
            downloaded += 1
        else:
            skipped += 1

    return downloaded, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Garmin or COROS activities without syncing them elsewhere."
    )
    parser.add_argument(
        "--source",
        choices=("garmin", "coros"),
        required=True,
        help="Account from which to download activities.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(CURRENT_DIR).parent / "backups",
        help="Root directory for backups (default: <repository>/backups).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Download again even when an activity file already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve() / args.source

    if args.source == "garmin":
        downloaded, skipped = backup_garmin(output_dir, args.overwrite)
    else:
        downloaded, skipped = backup_coros(output_dir, args.overwrite)

    print(
        f"Backup complete: {downloaded} downloaded, {skipped} already present "
        f"in {output_dir}"
    )


if __name__ == "__main__":
    main()
