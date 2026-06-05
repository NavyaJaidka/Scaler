const { spawnSync } = require("child_process");

const args = process.argv.slice(2);
const result = spawnSync("next", args, {
  env: {
    ...process.env,
    NEXT_TELEMETRY_DISABLED: "1",
  },
  shell: true,
  stdio: "inherit",
});

process.exit(result.status ?? 1);
