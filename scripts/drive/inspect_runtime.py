"""Package-only inventory: no Settings, environment dump, DB or document access."""

import importlib.metadata as metadata
import json
import os
import platform
import subprocess
from pathlib import Path


def main():
    try:
        import pip

        vendor = Path(pip.__file__).parent / "_vendor/vendor.txt"
    except ImportError:
        vendor = None
    print(
        json.dumps(
            {
                "uid": os.geteuid(),
                "python": platform.python_version(),
                "packages": dict(
                    sorted(
                        (dist.metadata["Name"], dist.version)
                        for dist in metadata.distributions()
                    )
                ),
                "requirements": {
                    dist.metadata["Name"]: dist.requires or []
                    for dist in metadata.distributions()
                },
                "pip_vendor_setuptools": [
                    line
                    for line in vendor.read_text().splitlines()
                    if line.startswith("setuptools==")
                ]
                if vendor
                else [],
                "pip_vendor_pkg_resources_present": (
                    vendor.parent / "pkg_resources"
                ).is_dir()
                if vendor
                else False,
                "os_packages": subprocess.check_output(
                    ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"],
                    text=True,
                ).splitlines(),
            }
        )
    )


if __name__ == "__main__":
    main()
