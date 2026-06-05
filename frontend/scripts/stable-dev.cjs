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
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, HOST);
  });
}

function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    shell: true,
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

(async () => {
  const busyPorts = [];
  for (const port of DEV_PORTS) {
    if (!(await isPortFree(port))) busyPorts.push(port);
  }

  if (busyPorts.length > 0) {
    console.error(`Frontend port(s) already in use: ${busyPorts.join(", ")}.`);
    console.error("Run npm run dev:stop first, or close the old frontend terminal.");
    process.exit(1);
  }

  run("node", [path.join("scripts", "clean-next.cjs")]);
  run("node", [path.join("scripts", "next-run.cjs"), "build"]);
  run("node", [path.join("scripts", "next-run.cjs"), "start", "-p", String(PORT)]);
})();
