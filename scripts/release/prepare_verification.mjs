// Private, synthetic credentials for a dedicated bd-final-check installation.
// Prints only the file path; never use this file with personal data/volumes.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomBytes } from "node:crypto";

const directory = fs.mkdtempSync(path.join(os.tmpdir(), "bd-final-check-"));
fs.chmodSync(directory, 0o700);
const filename = path.join(directory, "verification.env");
const secret = () => randomBytes(40).toString("base64url");
const example = fs.readFileSync(".env.example", "utf8");
const credentials = `POSTGRES_PASSWORD=${secret()}\nDJANGO_SECRET_KEY=${secret()}\nINITIAL_ADMIN_USERNAME=synthetic-release-admin\nINITIAL_ADMIN_PASSWORD=${secret()}\n`;
fs.writeFileSync(filename, example + "\n" + credentials, { mode: 0o600 });
if (process.argv.includes("--github")) {
  if (!process.env.GITHUB_ENV) throw Error("--github requires the Actions environment file");
  fs.appendFileSync(process.env.GITHUB_ENV, `VERIFICATION_ENV_FILE=${filename}\n` + credentials);
}
console.log(filename);
