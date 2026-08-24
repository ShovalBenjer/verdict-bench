"""Fetch the IEEE-CIS Fraud Detection dataset (Kaggle competition ieee-fraud-detection).

Source: https://www.kaggle.com/c/ieee-fraud-detection
License: competition-specific rules, gated behind accepting them on the
competition page. Not a fixed CC/ODbL tag; see PROVENANCE.md for the pointer
and the explicit "check at <url>" note this project uses when a license
string cannot be verified from a page fetch.
Intended use in this project: feature distributions (amount/decline/chargeback
shapes) that inform the synthetic case factory. See docs/prd/SPEC.md, section
"Data sources". No raw rows from this dataset ship in the repo or are sent to
any model; only aggregate distribution shapes inform synthetic generation.

This script never downloads silently. Because IEEE-CIS is a Kaggle
COMPETITION (not a plain dataset), the data is gated behind an account that
has accepted the competition rules on the page above. This script always
prints manual instructions and exits 0 unless the kaggle CLI is present,
authenticated, AND competition access is confirmed to work; even then it errs
towards the manual path, since accepted-rules state cannot be checked without
attempting the download.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

COMPETITION_SLUG = "ieee-fraud-detection"
COMPETITION_URL = f"https://www.kaggle.com/c/{COMPETITION_SLUG}"
TARGET_DIR = Path("data/raw/ieee_cis")

MANUAL_STEPS = f"""
IEEE-CIS Fraud Detection: manual download required
====================================================

This is a Kaggle COMPETITION, not a plain dataset. Kaggle gates competition
data behind an account that has explicitly accepted the competition rules.
This script does not accept rules on your behalf and does not attempt a
download that would fail on an unaccepted-rules account, so the steps below
are the supported path, not a fallback for an error.

1. Open {COMPETITION_URL} in a browser, sign in, and click "Join Competition"
   / accept the rules if you have not already.
2. Install and authenticate the Kaggle CLI if you have not already:
     pip install kaggle
     Place your API token at ~/.kaggle/kaggle.json
     (Kaggle account settings -> Create New API Token)
3. Download the competition files:
     mkdir -p {TARGET_DIR}
     kaggle competitions download -c {COMPETITION_SLUG} -p {TARGET_DIR}
4. Unzip in place:
     cd {TARGET_DIR} && unzip -o {COMPETITION_SLUG}.zip

The resulting CSVs land in {TARGET_DIR}/, which is gitignored (data/raw/ is
in .gitignore). Nothing from this dataset should be committed or sent to a
model; only aggregate feature-distribution shapes derived locally inform the
synthetic case factory described in docs/prd/SPEC.md.
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
    so all three are checked here. This script never auto-downloads
    IEEE-CIS regardless of auth state (see module docstring), but the
    printed status should still reflect reality.
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


def main() -> int:
    if not kaggle_cli_available():
        print("kaggle CLI not found on PATH.")
        print(MANUAL_STEPS)
        return 0

    if not kaggle_authenticated():
        print("kaggle CLI found, but no ~/.kaggle/kaggle.json token detected.")
        print(MANUAL_STEPS)
        return 0

    # Competition access additionally requires accepted rules, which cannot
    # be verified without attempting the call. Per this project's policy for
    # a rules-gated competition, always hand back the manual instructions
    # rather than risk a partial/failed automated download.
    print("kaggle CLI is installed and authenticated.")
    print(
        f"IEEE-CIS ({COMPETITION_SLUG}) is a rules-gated competition: this "
        "script will not attempt the download automatically, because "
        "accepted-rules state cannot be confirmed without trying the call "
        "and risking a partial failure. Follow the manual steps below; "
        "step 3 is a single command once rules are accepted."
    )
    print(MANUAL_STEPS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
