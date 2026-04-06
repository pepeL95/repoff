import * as vscode from "vscode";
import { BridgeServer, runApprovedTerminalCommand } from "./bridgeServer";
import { runDiscovery, summarizeCommandDiff } from "./copilotDiscovery";
import { CopilotProbe } from "./copilotProbe";
import { gatherPromptContext } from "./contextGatherer";
import { FallbackLm } from "./fallbackLm";
import { OutputManager } from "./output";
import { AskRequest, AskResponse, AskStreamEvent, DiscoverySnapshot, StatusSummary } from "./types";

let bridgeServer: BridgeServer | undefined;
let statusSummary: StatusSummary | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const output = new OutputManager(context);
  const config = vscode.workspace.getConfiguration("copilotBridge");
  const port = config.get<number>("port", 8765);
  const allowDangerousRun = config.get<boolean>("enableDangerousRun", false);
  const autoActivateCopilot = config.get<boolean>("discovery.autoActivateCopilot", true);

  const probe = new CopilotProbe(output);
  const fallback = new FallbackLm(output);

  output.info("Extension activating", { port, logFile: output.logFile, allowDangerousRun, autoActivateCopilot });

  const runtime = {
    ask: async (request: AskRequest, emit: (event: AskStreamEvent) => void): Promise<AskResponse> => {
      const contextualPrompt = request.includeContext === false
        ? request.prompt
        : await buildContextualPrompt(request.prompt);

      const privateResult = await probe.tryAsk({ ...request, prompt: contextualPrompt }, emit);
      if (privateResult?.ok) {
        statusSummary = { ...statusSummary!, lastRoute: privateResult.route, lastProbes: probe.recentAttempts() };
        return privateResult;
      }

      const fallbackResult = await fallback.ask({ ...request, prompt: contextualPrompt }, emit);
      statusSummary = { ...statusSummary!, lastRoute: fallbackResult.route, lastProbes: probe.recentAttempts() };
      return fallbackResult;
    },
    context: async () => await gatherPromptContext(),
    run: async (command: string) => {
      if (!allowDangerousRun) {
        return { ok: false, error: "Command execution is disabled by copilotBridge.enableDangerousRun." };
      }

      return await runApprovedTerminalCommand(command, output);
    }
  };

  bridgeServer = new BridgeServer(port, runtime, output);
  await bridgeServer.start();
  context.subscriptions.push(bridgeServer);

  const discovery = await runDiscovery(output, autoActivateCopilot);
  const initialProbes = await probe.runBenignProbes();
  output.info("Probe results", initialProbes);

  statusSummary = {
    port,
    logFile: output.logFile,
    lastDiscovery: discovery,
    lastProbes: probe.recentAttempts()
  };

  context.subscriptions.push(
    vscode.commands.registerCommand("copilotBridge.showStatus", async () => {
      output.show();
      void vscode.window.showInformationMessage(renderStatus(statusSummary));
    }),
    vscode.commands.registerCommand("copilotBridge.runDiscovery", async () => {
      const refreshed = await runDiscovery(output, autoActivateCopilot);
      statusSummary = { ...statusSummary!, lastDiscovery: refreshed };
      output.info("Discovery rerun complete", { newCommands: summarizeCommandDiff(refreshed) });
      void vscode.window.showInformationMessage("Copilot Bridge discovery rerun completed.");
    }),
    vscode.commands.registerCommand("copilotBridge.restartBridge", async () => {
      bridgeServer?.dispose();
      bridgeServer = new BridgeServer(port, runtime, output);
      await bridgeServer.start();
      context.subscriptions.push(bridgeServer);
      void vscode.window.showInformationMessage(`Copilot Bridge restarted on port ${port}.`);
    })
  );
}

export function deactivate(): void {
  bridgeServer?.dispose();
}

async function buildContextualPrompt(prompt: string): Promise<string> {
  const context = await gatherPromptContext();
  return [
    prompt,
    "",
    "Workspace context:",
    JSON.stringify(context, null, 2)
  ].join("\n");
}

function renderStatus(status: StatusSummary | undefined): string {
  if (!status) {
    return "Copilot Bridge is not initialized.";
  }

  return [
    `Bridge: ws://127.0.0.1:${status.port}`,
    `Log file: ${status.logFile}`,
    `Last route: ${status.lastRoute ?? "none"}`,
    `Discovery timestamp: ${status.lastDiscovery?.timestamp ?? "none"}`,
    `Recent probes: ${status.lastProbes.length}`
  ].join(" | ");
}
