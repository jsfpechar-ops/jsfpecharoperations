"use strict";
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const { PASSKEY_CASES, runPasskeyClientCase } = require("./passkeys_client_cases.js");
const source = fs.readFileSync(path.join(__dirname, "../app/static/passkeys.js"), "utf8");
for (const name of PASSKEY_CASES) {
  test(name, async () => { await runPasskeyClientCase(source, name); });
}
