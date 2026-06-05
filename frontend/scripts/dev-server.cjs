const { spawnSync } = require("child_process");
const net = require("net");
const path = require("path");

const PORT = Number(process.env.PORT || 3000);
const HOST = "127.0.0.1";
const DEV_PORTS = Array.from({ length: 11 }, (_, index) => 3000 + index);

function isPortFree(port) {
  return new Promise(resolve => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, HOST);
  });
}

(async () => {
  const busyPorts = [];
  for (const port of DEV_PORTS) {
    if (!(await isPortFree(port))) busyPorts.push(port);
  }

  const allowedBusyPort = process.env.ALLOW_BUSY_DEV_PORT === "1" ? PORT : null;
  const blockingPorts = busyPorts.filter(port => port !== allowedBusyPort);

  if (blockingPorts.length > 0) {
    console.error(`Next.js dev port(s) already in use: ${blockingPorts.join(", ")}.`);
    console.error("Stop old frontend terminals before running npm run dev again.");
    console.error("This protects .next from being deleted while another dev server is still using it.");
    console.error("PowerShell helper: netstat -ano | findstr \":300\"");
    process.exit(1);
  }

  const clean = spawnSync("node", [path.join("scripts", "clean-next.cjs")], {
    stdio: "inherit",
    shell: true,
  });
  if (clean.status !== 0) process.exit(clean.status ?? 1);

  const args = ["dev", "-p", String(PORT)];
  if (process.argv.includes("--turbo")) args.push("--turbo");

  const next = spawnSync("node", [path.join("scripts", "next-run.cjs"), ...args], {
    stdio: "inherit",
    shell: true,
  });

  process.exit(next.status ?? 1);
})();
