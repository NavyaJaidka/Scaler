const fs = require("fs");
const path = require("path");

const frontendDir = path.resolve(__dirname, "..");
const targets = [
  ".next",
  ".turbo",
  "tsconfig.tsbuildinfo",
].map(target => path.join(frontendDir, target));

let removed = false;
for (const target of targets) {
  if (fs.existsSync(target)) {
    fs.rmSync(target, { recursive: true, force: true });
    console.log(`Removed ${path.basename(target)}`);
    removed = true;
  }
}

if (!removed) console.log("Next.js cache already clean");
