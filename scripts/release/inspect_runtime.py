"""Metadata-only inventory; never loads app settings, credentials or documents."""
import importlib.metadata as metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess

packages = dict(sorted((dist.metadata["Name"], dist.version) for dist in metadata.distributions()))
native = None
if shutil.which("tesseract"):
    binary = shutil.which("tesseract")
    native = {
        "version": subprocess.check_output([binary, "--version"], text=True).splitlines()[0],
        "linked_libraries": subprocess.check_output(["ldd", binary], text=True).splitlines(),
    }
print(json.dumps({
    "uid": os.geteuid(), "python": platform.python_version(), "packages": packages,
    "requirements": {dist.metadata["Name"]: dist.requires or [] for dist in metadata.distributions()},
    "ensurepip_present": importlib.util.find_spec("ensurepip") is not None,
    "pip_vendor_setuptools": [], "pip_vendor_pkg_resources_present": False,
    "os_packages": subprocess.check_output(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"], text=True).splitlines(),
    "native_ocr": native,
}))
