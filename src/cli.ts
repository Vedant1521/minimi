import readline from "readline";
import { AgentOrchestrator } from "./agent/orchestrator";
import { config } from "./config";

async function runCli() {
  const args = process.argv.slice(2);
  let query: string | null = null;
  let sessionId: string = crypto.randomUUID();

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--query" || args[i] === "-q") {
      query = args[i + 1];
      i++;
    } else if (args[i] === "--session-id" || args[i] === "-s") {
      sessionId = args[i + 1];
      i++;
    }
  }

  const orchestrator = new AgentOrchestrator();

  console.log("==============================================================");
  console.log("Minimi: Search-Grounded Agent with Temporal Memory");
  console.log(`Active Session: ${sessionId}`);
  console.log(`Configured Timezone: ${config.timezone}`);
  console.log(`Model Tool Limit: Exactly 1 ("web_search")`);
  console.log("==============================================================\n");

  if (query) {
    console.log(`User: ${query}\n`);
    for await (const event of orchestrator.processTurnStream(sessionId, query, config.timezone)) {
      if (event.type === "token") {
        process.stdout.write(String(event.data));
      } else if (event.type === "status") {
        const data = event.data as { message?: string };
        console.log(`\n[Status] ${data.message}`);
      }
    }
    console.log("\n");
    process.exit(0);
  }

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const promptUser = () => {
    rl.question("\nYou: ", async (input) => {
      const text = input.trim();
      if (!text || text.toLowerCase() === "exit" || text.toLowerCase() === "quit") {
        console.log("Exiting Minimi CLI.");
        rl.close();
        process.exit(0);
      }

      console.log("\nMinimi: ");
      for await (const event of orchestrator.processTurnStream(sessionId, text, config.timezone)) {
        if (event.type === "token") {
          process.stdout.write(String(event.data));
        } else if (event.type === "status") {
          const data = event.data as { message?: string };
          console.log(`\n[Status] ${data.message}`);
        }
      }
      console.log("\n");
      promptUser();
    });
  };

  promptUser();
}

runCli().catch((err) => {
  console.error("CLI error:", err);
  process.exit(1);
});
