"""Audit one immutable runtime image/archive; retain all findings, no CVE suppression."""
import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

SCANNER = "aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb"


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def inputs():
    base = Path("backend/DocumentExportServices")
    paths = [base / "Dockerfile", base / "requirements.txt"]
    paths += [path for path in (base / "app").rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"]
    inventory = []
    for path in sorted(paths):
        data = path.read_bytes()
        if path.suffix in (".py", ".txt", ".md") or path.name == "Dockerfile":
            data = data.replace(b"\r\n", b"\n")
        inventory.append({"path": path.as_posix(), "sha256": hashlib.sha256(data).hexdigest()})
    return inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    image = output("docker", "image", "inspect", "--format", "{{.Id}}", args.image)
    archive = args.out / "runtime-image.tar"
    subprocess.check_call(["docker", "save", "--output", str(archive), image])
    with archive.open("rb") as input_file:
        archive_hash = hashlib.file_digest(input_file, "sha256").hexdigest()
    inspector = Path(__file__).with_name("inspect_runtime.py").read_bytes()
    runtime = json.loads(subprocess.check_output(["docker", "run", "--rm", "-i", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16777216", "--entrypoint", "python", image, "-"], input=inspector))
    (args.out / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
    subprocess.check_call(["docker", "run", "--rm", "--mount", f"type=bind,source={args.out.resolve()},target=/audit", SCANNER,
        "image", "--scanners", "vuln", "--severity", "HIGH,CRITICAL", "--format", "json", "--output", "/audit/trivy.json",
        "--cache-dir", "/tmp/trivy-cache", "--input", "/audit/runtime-image.tar"])
    scan = json.loads((args.out / "trivy.json").read_text())
    findings = []
    for result in scan.get("Results", []):
        for finding in result.get("Vulnerabilities", []):
            target = result.get("Target", "")
            disposition = ("EXPORT-F01: OS has no fixed version indicated; rebuild/rescan before public deployment."
                           if result.get("Class") == "os-pkgs" and not finding.get("FixedVersion") else "REQUIRES_REVIEW")
            findings.append({"id": finding["VulnerabilityID"], "package": finding["PkgName"],
                             "installed": finding["InstalledVersion"], "fixed": finding.get("FixedVersion"),
                             "severity": finding["Severity"], "target": target, "disposition": disposition})
    build_inputs = inputs()
    report = {"card": "EXPORT-007", "date_utc": datetime.now(UTC).isoformat(), "scanner": "Trivy 0.76.2", "scanner_image": SCANNER,
              "severity_filter": ["HIGH", "CRITICAL"], "runtime_image_id": image,
              "archive_sha256": archive_hash, "scanned_config_id": scan.get("Metadata", {}).get("ImageID"),
              "base": Path("backend/DocumentExportServices/Dockerfile").read_text().splitlines()[0],
              "os": scan.get("Metadata", {}).get("OS"), "runtime": runtime,
              "source_hash_normalization": "UTF-8 LF for text, raw bytes for binaries", "build_inputs": build_inputs,
              "build_inputs_sha256": hashlib.sha256(json.dumps(build_inputs, sort_keys=True).encode()).hexdigest(),
              "findings": findings, "counts": {"matches": len(findings), "unique_ids": len({entry["id"] for entry in findings}),
                                               "critical": sum(entry["severity"] == "CRITICAL" for entry in findings)}}
    (args.out / "IMAGE_AUDIT.json").write_text(json.dumps(report, indent=2) + "\n")
    archive.unlink()
    print(json.dumps({"image": image, "counts": report["counts"], "review_required": sum(entry["disposition"] == "REQUIRES_REVIEW" for entry in findings)}))
    if runtime["uid"] != 10009 or any(name.lower() == "pip" for name in runtime["packages"]) or any(entry["severity"] == "CRITICAL" or entry["disposition"] == "REQUIRES_REVIEW" for entry in findings):
        raise SystemExit("Runtime audit requires explicit review; complete inventory retained.")


if __name__ == "__main__":
    main()
