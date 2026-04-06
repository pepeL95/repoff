import * as vscode from "vscode";
import { BridgeServer } from "./bridgeServer";
import { gatherPromptContext } from "./contextGatherer";
import { FallbackLm } from "./fallbackLm";
import { OutputManager } from "./output";
import { AskRequest, AskResponse, AskStreamEvent, BridgeRuntime, StatusSummary } from "./types";

let bridgeServer: BridgeServer | undefined;
let statusBarItem: vscode.StatusBarItem | undefined;
let statusSummary: StatusSummary | undefined;

export function activate(context: vscode.ExtensionContext): void {
  void activateAsync(context);
}

async function activateAsync(context: vscode.ExtensionContext): Promise<void> {
  const output = new OutputManager(context);
  const config = vscode.workspace.getConfiguration("copilotBridge");
  const port = config.get<number>("port", 8765);

  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.command = "copilotBridge.showStatus";
  context.subscriptions.push(statusBarItem);

  const lm = new FallbackLm(output);

  statusSummary = {
    port,
    logFile: output.logFile,
    bridgeReady: false
  };

  output.info("Extension activating", { port, logFile: output.logFile });
  updateStatusBar("starting", port);

  const runtime: BridgeRuntime = {
    ask: async (request: AskRequest, emit: (event: AskStreamEvent) => void): Promise<AskResponse> => {
      const prompt = request.includeContext === false
        ? request.prompt
        : await buildContextualPrompt(request.prompt);

      const response = await lm.ask({ ...request, prompt }, emit);
      statusSummary = {
        ...(statusSummary ?? { port, logFile: output.logFile, bridgeReady: true }),
        lastRoute: response.route,
        lastError: response.error,
        lastModel: response.modelLabel
      };
      return response;
    },
    context: async () => await gatherPromptContext()
  };

  registerCommands(context, output, runtime, port);
  void startBridge(output, runtime, port, context);
}

export function deactivate(): void {
  bridgeServer?.dispose();
  statusBarItem?.dispose();
}

function registerCommands(
  context: vscode.ExtensionContext,
  output: OutputManager,
  runtime: BridgeRuntime,
  port: number
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("copilotBridge.showStatus", async () => {
      output.show();
      void vscode.window.showInformationMessage(renderStatus(statusSummary));
    }),
    vscode.commands.registerCommand("copilotBridge.restartBridge", async () => {
      bridgeServer?.dispose();
      await startBridge(output, runtime, port, context);
      void vscode.window.showInformationMessage(`Copilot Bridge restarted on port ${port}.`);
    }),
    vscode.commands.registerCommand("copilotBridge.copyEndpoint", async () => {
      await vscode.env.clipboard.writeText(`ws://127.0.0.1:${port}`);
      void vscode.window.showInformationMessage(`Copied Copilot Bridge endpoint ws://127.0.0.1:${port}`);
    })
  );
}

async function startBridge(
  output: OutputManager,
  runtime: BridgeRuntime,
  port: number,
  context: vscode.ExtensionContext
): Promise<void> {
  updateStatusBar("starting", port);

  try {
    bridgeServer = new BridgeServer(port, runtime, output);
    await bridgeServer.start();
    context.subscriptions.push(bridgeServer);
    statusSummary = {
      ...(statusSummary ?? { port, logFile: output.logFile }),
      bridgeReady: true,
      lastError: undefined
    };
    updateStatusBar("ready", port);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.error("Bridge failed to start", { error: message, port });
    statusSummary = {
      ...(statusSummary ?? { port, logFile: output.logFile }),
      bridgeReady: false,
      lastError: message
    };
    updateStatusBar("error", port);
  }
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
    `Ready: ${status.bridgeReady ? "yes" : "no"}`,
    `Last route: ${status.lastRoute ?? "none"}`,
    `Last model: ${status.lastModel ?? "none"}`,
    `Last error: ${status.lastError ?? "none"}`,
    `Log file: ${status.logFile}`
  ].join(" | ");
}

function updateStatusBar(state: "starting" | "ready" | "error", port: number): void {
  if (!statusBarItem) {
    return;
  }

  switch (state) {
    case "starting":
      statusBarItem.text = `$(sync~spin) LM Bridge ${port}`;
      statusBarItem.tooltip = "VS Code LM Bridge is starting.";
      break;
    case "ready":
      statusBarItem.text = `$(radio-tower) LM Bridge ${port}`;
      statusBarItem.tooltip = "VS Code LM Bridge is running in this window.";
      break;
    case "error":
      statusBarItem.text = `$(error) LM Bridge ${port}`;
      statusBarItem.tooltip = "VS Code LM Bridge failed to start. Use Show Status for details.";
      break;
  }

  statusBarItem.show();
}
