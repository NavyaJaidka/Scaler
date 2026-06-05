const { execSync, spawnSync } = require("child_process");

function run(command) {
  return execSync(command, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
}

function findWindowsPids() {
  const output = run("wmic process where \"name='node.exe'\" get ProcessId,CommandLine /format:csv");
  return output
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line.includes("next") && line.includes("dev"))
    .map(line => line.split(",").pop())
    .filter(Boolean);
}

function findPortPids() {
  const ports = Array.from({ length: 11 }, (_, index) => 3000 + index);
  const pids = new Set();

  for (const port of ports) {
    try {
      const output = run(`netstat -ano | findstr :${port}`);
      for (const line of output.split(/\r?\n/)) {
        const parts = line.trim().split(/\s+/);
        if (!parts.includes("LISTENING")) continue;
        const pid = parts[parts.length - 1];
        if (/^\d+$/.test(pid) && pid !== "0") pids.add(pid);
      }
    } catch {
      // No process is listening on this port.
    }
  }

  return [...pids];
}

const pids = new Set();
try {
  for (const pid of findWindowsPids()) pids.add(pid);
} catch {
  // wmic is not available on every Windows install.
}
for (const pid of findPortPids()) pids.add(pid);

if (pids.size === 0) {
  console.log("No stale Next.js dev server found on ports 3000-3010.");
  process.exit(0);
}

for (const pid of pids) {
  console.log(`Stopping dev server PID ${pid}`);
  spawnSync("taskkill", ["/PID", pid, "/F"], { stdio: "inherit", shell: true });
}
