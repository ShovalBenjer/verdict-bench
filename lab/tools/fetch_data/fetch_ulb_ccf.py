"""Fetch the ULB Credit Card Fraud dataset (Kaggle mlg-ulb/creditcardfraud).

Source: https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
License: Kaggle's page metadata names it verbatim as "Database: Open
Database, Contents: Database Contents", url
http://opendatacommons.org/licenses/dbcl/1.0/, verified from the dataset
page's embedded schema.org metadata on 2026-08-24. See PROVENANCE.md for
the full JSON-LD quote and the independently confirmed target of that URL
(Database Contents License v1.0 on Open Data Commons).
Intended use in this project: the extreme class imbalance (fraud ~0.17% of
transactions) informs the class-imbalance framing used in this project's
writeup, i.e. why accuracy is the wrong headline metric for a rare-event
decision task. See docs/prd/SPEC.md, section "Data sources". No raw rows
from this dataset ship in the repo or are sent to any model; only the
imbalance ratio and aggregate shape inform the writeup and synthetic factory.

Download target is data/raw/ulb_ccf/, which is gitignored (data/raw/ is in
.gitignore). This is a plain Kaggle dataset (~70MB), not a gated competition,
so this script will attempt the download automatically when the kaggle CLI
is present and authenticated; otherwise it prints manual steps and exits 0,
which is a supported outcome, not a failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

DATASET_SLUG = "mlg-ulb/creditcardfraud"
DATASET_URL = "https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud"
TARGET_DIR = Path("data/raw/ulb_ccf")

MANUAL_STEPS = f"""
ULB Credit Card Fraud: manual download required
=================================================

1. Install and authenticate the Kaggle CLI if you have not already:
     pip install kaggle
     Place your API token at ~/.kaggle/kaggle.json
     (Kaggle account settings -> Create New API Token)
2. Download the dataset:
     mkdir -p {TARGET_DIR}
     kaggle datasets download -d {DATASET_SLUG} -p {TARGET_DIR} --unzip

Or download the zip by hand from {DATASET_URL} and unzip it into
{TARGET_DIR}/.

The resulting CSV lands in {TARGET_DIR}/, which is gitignored (data/raw/ is
in .gitignore). Nothing from this dataset should be committed or sent to a
model; only the class-imbalance ratio and aggregate shape derived locally
inform the writeup and synthetic case factory described in
docs/prd/SPEC.md.
"""


def kaggle_cli_available() -> bool:
    """Return True if a `kaggle` executable is on PATH."""
    return shutil.which("kaggle") is not None


def kaggle_authenticated() -> bool:
    """Return True if a Kaggle API token is configured and the CLI runs.

    The kaggle CLI accepts credentials from any of three places: the
    KAGGLE_USERNAME/KAGGLE_KEY environment variables, a kaggle.json under
    KAGGLE_CONFIG_DIR, or the default ~/.kaggle/kaggle.json. Checking only
    the default file path would wrongly report "not authenticated" on a
    machine using env-var or KAGGLE_CONFIG_DIR auth (the normal CI shape),
    so all three are checked here.
    """
    has_env_creds = bool(os.environ.get("KAGGLE_USERNAME")) and bool(
        os.environ.get("KAGGLE_KEY")
    )
    config_dir = os.environ.get("KAGGLE_CONFIG_DIR")
    has_config_dir_token = bool(config_dir) and (Path(config_dir) / "kaggle.json").exists()
    has_default_token = (Path.home() / ".kaggle" / "kaggle.json").exists()

    if not (has_env_creds or has_config_dir_token or has_default_token):
        return False
    try:
        result = subprocess.run(
            ["kaggle", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def download(target_dir: Path) -> bool:
    """Attempt the dataset download via the kaggle CLI.

    Returns True on a clean (returncode 0) download, False otherwise. Never
    raises: a subprocess failure is reported and handled by the caller, not
    swallowed.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [
                "kaggle",
                "datasets",
                "download",
                "-d",
                DATASET_SLUG,
                "-p",
                str(target_dir),
                "--unzip",
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Download attempt raised {type(exc).__name__}: {exc}")
        return False

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return False
    return True


def main() -> int:
    if not kaggle_cli_available():
        print("kaggle CLI not found on PATH.")
        print(MANUAL_STEPS)
        return 0

    if not kaggle_authenticated():
        print("kaggle CLI found, but no ~/.kaggle/kaggle.json token detected.")
        print(MANUAL_STEPS)
        return 0

    print(f"kaggle CLI authenticated. Downloading {DATASET_SLUG} to {TARGET_DIR}/ ...")
    if download(TARGET_DIR):
        print(f"Download complete: {TARGET_DIR}/")
        return 0

    print("Automated download failed.")
    print(MANUAL_STEPS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
