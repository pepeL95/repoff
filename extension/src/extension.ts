import * as vscode from "vscode";

type ChatModel = {
  vendor?: string;
  family?: string;
  id?: string;
  sendRequest?: (
    messages: unknown[],
    options?: Record<string, unknown>,
    token?: vscode.CancellationToken
  ) => Promise<{ text?: AsyncIterable<string>; stream?: AsyncIterable<unknown> }>;
};

const OUTPUT_NAME = "Copilot Bridge";

let outputChannel: vscode.OutputChannel | undefined;
let statusBarItem: vscode.StatusBarItem | undefined;
let lastStatus = "idle";
let lastModel = "none";
let lastError = "none";

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel(OUTPUT_NAME);
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.command = "copilotBridge.showStatus";
  updateStatusBar("ready");

  appendLog("Extension activated");

  context.subscriptions.push(
    outputChannel,
    statusBarItem,
    vscode.commands.registerCommand("copilotBridge.showStatus", async () => {
      outputChannel?.show(true);
      void vscode.window.showInformationMessage(renderStatus());
    }),
    vscode.commands.registerCommand("copilotBridge.listModels", async () => {
      await withCommandHandling("listModels", async () => {
        const models = await selectModels();
        const lines = models.map(renderModel);
        appendLog(`Models (${lines.length})`);
        for (const line of lines) {
          appendLog(`- ${line}`);
        }
        void vscode.window.showInformationMessage(lines.length > 0 ? `Found ${lines.length} model(s).` : "No chat models found.");
      });
    }),
    vscode.commands.registerCommand("copilotBridge.smokeTest", async () => {
      await withCommandHandling("smokeTest", async () => {
        const model = await selectFirstModel();
        const modelLabel = renderModel(model);
        lastModel = modelLabel;
        appendLog(`Smoke test using ${modelLabel}`);

        const response = await model.sendRequest?.([
          {
            role: "user",
            content: "Reply with exactly OK"
          }
        ]);

        if (!response) {
          throw new Error("Selected model did not expose sendRequest.");
        }

        const text = await collectText(response.text ?? response.stream);
        appendLog(`Smoke test response: ${JSON.stringify(text)}`);
        void vscode.window.showInformationMessage(`Smoke test response: ${text || "(empty)"}`);
      });
    })
  );
}

export function deactivate(): void {
  outputChannel?.dispose();
  statusBarItem?.dispose();
}

async function withCommandHandling(name: string, fn: () => Promise<void>): Promise<void> {
  try {
    lastStatus = `${name}:running`;
    lastError = "none";
    updateStatusBar("busy");
    await fn();
    lastStatus = `${name}:ok`;
    updateStatusBar("ready");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    lastStatus = `${name}:error`;
    lastError = message;
    appendLog(`${name} failed: ${message}`);
    updateStatusBar("error");
    void vscode.window.showErrorMessage(`${name} failed: ${message}`);
  }
}

async function selectModels(): Promise<ChatModel[]> {
  const lm = (vscode as unknown as {
    lm?: {
      selectChatModels?: (selector?: Record<string, unknown>) => Promise<ChatModel[]>;
    };
  }).lm;

  if (!lm?.selectChatModels) {
    throw new Error("VS Code Language Model API is not available in this build.");
  }

  const preferred = await lm.selectChatModels({ vendor: "copilot" });
  if (preferred.length > 0) {
    return preferred;
  }

  return await lm.selectChatModels();
}

async function selectFirstModel(): Promise<ChatModel> {
  const models = await selectModels();
  if (models.length === 0) {
    throw new Error("No chat models were returned by VS Code.");
  }

  const model = models[0];
  if (!model.sendRequest) {
    throw new Error("Selected model does not expose sendRequest.");
  }

  return model;
}

async function collectText(stream: AsyncIterable<unknown> | undefined): Promise<string> {
  if (!stream) {
    return "";
  }

  let text = "";
  for await (const chunk of stream) {
    text += normalizeChunk(chunk);
  }
  return text;
}

function normalizeChunk(chunk: unknown): string {
  if (typeof chunk === "string") {
    return chunk;
  }

  if (chunk && typeof chunk === "object") {
    const candidate = (chunk as { value?: string; text?: string }).value ?? (chunk as { text?: string }).text;
    return typeof candidate === "string" ? candidate : "";
  }

  return "";
}

function renderModel(model: ChatModel): string {
  return [model.vendor, model.family ?? model.id].filter(Boolean).join(":") || "unknown-model";
}

function renderStatus(): string {
  return [
    `Status: ${lastStatus}`,
    `Model: ${lastModel}`,
    `Error: ${lastError}`
  ].join(" | ");
}

function appendLog(message: string): void {
  outputChannel?.appendLine(`[${new Date().toISOString()}] ${message}`);
}

function updateStatusBar(state: "ready" | "busy" | "error"): void {
  if (!statusBarItem) {
    return;
  }

  if (state === "busy") {
    statusBarItem.text = "$(sync~spin) LM Smoke Test";
    statusBarItem.tooltip = renderStatus();
  } else if (state === "error") {
    statusBarItem.text = "$(error) LM Smoke Test";
    statusBarItem.tooltip = renderStatus();
  } else {
    statusBarItem.text = "$(beaker) LM Smoke Test";
    statusBarItem.tooltip = renderStatus();
  }

  statusBarItem.show();
}
