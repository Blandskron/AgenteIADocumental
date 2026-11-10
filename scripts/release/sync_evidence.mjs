// Derive service-specific snapshots from the immutable central scan, never from hand-entered counts.
import fs from "node:fs";
import { createHash } from "node:crypto";

const source = "docs/release/IMAGE_AUDIT.json";
const report = JSON.parse(fs.readFileSync(source, "utf8"));
if (!report.finished_utc || report.images.length !== 12 || report.requires_review.length) {
  throw Error("Complete and review the twelve-image audit before updating service evidence.");
}
for (const [service, folder, card] of [
  ["profile-service", "ProfileServices", "PROFILE-008 / PLAT-002"],
  ["document-export-service", "DocumentExportServices", "EXPORT-007 / PLAT-002"],
  ["google-drive-import-service", "GoogleDriveImportServices", "DRIVE-007/008 / PLAT-002"],
]) {
  const image = report.images.find((entry) => entry.service === service);
  if (!image || image.image_id === undefined || image.saved_config_id !== image.scanned_image_id) throw Error("Invalid scanned artifact");
  const inputs = image.build_inputs;
  const snapshot = {
    card, source_report: source, date_utc: image.collected_utc, scanner: "Trivy 0.76.2",
    scanner_image: report.scanner_image, severity_filter: report.severity_filter,
    runtime_image_id: image.image_id, archive_sha256: image.archive_sha256,
    saved_config_id: image.saved_config_id, scanned_config_id: image.scanned_image_id,
    os: image.os, runtime: image.inventory, build_inputs: inputs,
    build_inputs_sha256: createHash("sha256").update(JSON.stringify(inputs)).digest("hex"),
    findings: image.findings, counts: { ...image.counts, matches: image.findings.length },
  };
  fs.writeFileSync(`backend/${folder}/docs/IMAGE_AUDIT.json`, JSON.stringify(snapshot, null, 2) + "\n");
}
console.log("Updated three service snapshots from the complete central audit.");
