"""Verify the captured runtime graph using audit tooling, without shipping pip in runtime."""

import json
import sys

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def main():
    data = json.load(sys.stdin)
    versions = {
        canonicalize_name(name): version for name, version in data["packages"].items()
    }
    extras = {"uvicorn": ["standard"], "psycopg": ["binary"]}
    for name, requirements in data["requirements"].items():
        for item in requirements:
            requirement = Requirement(item)
            active = not requirement.marker or any(
                requirement.marker.evaluate({**default_environment(), "extra": extra})
                for extra in ["", *extras.get(canonicalize_name(name), [])]
            )
            if active:
                installed = versions.get(canonicalize_name(requirement.name))
                if installed is None or installed not in requirement.specifier:
                    raise RuntimeError("Runtime dependency graph is inconsistent.")
    print(
        "Runtime dependency graph valid:",
        len(versions),
        "packages; no installer required.",
    )


if __name__ == "__main__":
    main()
