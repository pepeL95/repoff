import * as vscode from "vscode";
import { BridgeServer } from "./bridgeServer";

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

type ConversationMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

type BridgeMessage = {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  toolCalls?: Array<{ callId?: string; name: string; input: Record<string, unknown> }>;
  toolCallId?: string;
  status?: "success" | "error";
};

const OUTPUT_NAME = "Copilot Bridge";

let outputChannel: vscode.OutputChannel | undefined;
let statusBarItem: vscode.StatusBarItem | undefined;
let bridgeServer: BridgeServer | undefined;
let lastStatus = "idle";
let lastModel = "none";
let lastError = "none";
let serverState = "stopped";
let lastPort = 8765;

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel(OUTPUT_NAME);
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.command = "copilotBridge.showStatus";
  lastPort = vscode.workspace.getConfiguration("copilotBridge").get<number>("port", 8765);
  updateStatusBar("ready");

  appendLog("Extension activated");

  context.subscriptions.push(
    outputChannel,
    statusBarItem,
    vscode.commands.registerCommand("copilotBridge.showStatus", async () => {
      outputChannel?.show(true);
      void vscode.window.showInformationMessage(renderStatus());
    }),
    vscode.commands.registerCommand("copilotBridge.startServer", async () => {
      await withCommandHandling("startServer", async () => {
        bridgeServer?.dispose();
        bridgeServer = new BridgeServer(lastPort, appendLog, async () => {
          const models = await selectModels();
          const defaultLabel = selectDefaultModelLabel(models);
          return models.map((model) => {
            const label = renderModel(model);
            return { label, isDefault: label === defaultLabel };
          });
        }, async (messages, preferredModel, tools, toolChoice) => {
          try {
            lastStatus = "chat:running";
            updateStatusBar("busy");
            const result = await askMessages(messages, preferredModel, tools, toolChoice);
            lastStatus = "chat:ok";
            lastError = "none";
            updateStatusBar("ready");
            return { ok: true, text: result.text, model: result.model, toolCalls: result.toolCalls };
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            lastStatus = "chat:error";
            lastError = message;
            updateStatusBar("error");
            appendLog(`chat failed: ${message}`);
            return { ok: false, error: message };
          }
        });
        await bridgeServer.start();
        context.subscriptions.push(bridgeServer);
        serverState = "started";
        appendLog(`LM adapter listening on http://127.0.0.1:${lastPort}`);
        void vscode.window.showInformationMessage(`LM adapter listening on http://127.0.0.1:${lastPort}`);
      });
    }),
    vscode.commands.registerCommand("copilotBridge.stopServer", async () => {
      bridgeServer?.dispose();
      bridgeServer = undefined;
      serverState = "stopped";
      lastStatus = "stopServer:ok";
      lastError = "none";
      appendLog("Bridge stopped");
      updateStatusBar("ready");
      void vscode.window.showInformationMessage("Bridge stopped.");
    }),
    vscode.commands.registerCommand("copilotBridge.listModels", async () => {
      await withCommandHandling("listModels", async () => {
        const models = await selectModels();
        const lines = models.map(renderModelDetails);
        appendLog(`Models (${lines.length})`);
        for (const line of lines) {
          appendLog(`- ${line}`);
        }
        void vscode.window.showInformationMessage(lines.length > 0 ? `Found ${lines.length} model(s).` : "No chat models found.");
      });
    }),
    vscode.commands.registerCommand("copilotBridge.smokeTest", async () => {
      await withCommandHandling("smokeTest", async () => {
        const text = await askModel("Reply with exactly OK");
        appendLog(`Smoke test response: ${JSON.stringify(text)}`);
        void vscode.window.showInformationMessage(`Smoke test response: ${text || "(empty)"}`);
      });
    })
  );
}

export function deactivate(): void {
  bridgeServer?.dispose();
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

function selectDefaultModelLabel(models: ChatModel[]): string {
  const preferred = models.find((model) => {
    const label = renderModel(model).toLowerCase();
    return label.includes("gpt-4.1");
  });

  return renderModel(preferred ?? models[0]);
}

async function selectFirstModel(): Promise<ChatModel> {
  const models = await selectModels();
  if (models.length === 0) {
    throw new Error("No chat models were returned by VS Code.");
  }

  const preferred = models.find((model) => {
    const label = renderModel(model).toLowerCase();
    return label.includes("gpt-4.1");
  });

  const model = preferred ?? models[0];
  if (!model.sendRequest) {
    throw new Error("Selected model does not expose sendRequest.");
  }

  return model;
}

async function askModel(prompt: string): Promise<string> {
  const result = await askMessages([{ role: "user", content: prompt }]);
  return result.text;
}

async function askMessages(
  messages: BridgeMessage[],
  preferredModel?: string,
  tools?: Array<{ name: string; description: string; inputSchema?: object }>,
  toolChoice?: string
): Promise<{ text: string; model: string; toolCalls: Array<{ callId: string; name: string; input: Record<string, unknown> }> }> {
  const model = await selectFirstModel();
  let selectedModel = model;
  if (preferredModel) {
    const models = await selectModels();
    const match = models.find((candidate) => renderModel(candidate) === preferredModel);
    if (match?.sendRequest) {
      selectedModel = match;
    }
  }
  lastModel = renderModel(selectedModel);

  const response = await selectedModel.sendRequest?.(
    messages.map(toLanguageModelChatMessage),
    tools && tools.length > 0
      ? {
          tools: tools,
          toolMode:
            toolChoice === "required" || toolChoice === "any"
              ? vscode.LanguageModelChatToolMode.Required
              : vscode.LanguageModelChatToolMode.Auto
        }
      : undefined
  );

  if (!response) {
    throw new Error("Selected model did not expose sendRequest.");
  }

  const collected = await collectResponse(response.stream ?? response.text);
  return { text: collected.text, model: lastModel, toolCalls: collected.toolCalls };
}

async function collectResponse(
  stream: AsyncIterable<unknown> | undefined
): Promise<{ text: string; toolCalls: Array<{ callId: string; name: string; input: Record<string, unknown> }> }> {
  if (!stream) {
    return { text: "", toolCalls: [] };
  }

  let text = "";
  const toolCalls: Array<{ callId: string; name: string; input: Record<string, unknown> }> = [];
  for await (const chunk of stream) {
    if (chunk instanceof vscode.LanguageModelTextPart) {
      text += chunk.value;
      continue;
    }
    if (chunk instanceof vscode.LanguageModelToolCallPart) {
      toolCalls.push({
        callId: chunk.callId,
        name: chunk.name,
        input: (chunk.input ?? {}) as Record<string, unknown>
      });
      continue;
    }
    text += normalizeChunk(chunk);
  }
  return { text, toolCalls };
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

function toLanguageModelChatMessage(message: BridgeMessage): vscode.LanguageModelChatMessage {
  if (message.role === "tool") {
    return vscode.LanguageModelChatMessage.User(
      [
        new vscode.LanguageModelToolResultPart(
          message.toolCallId ?? "",
          [new vscode.LanguageModelTextPart(message.content)]
        )
      ]
    );
  }

  if (message.role === "assistant") {
    const parts: Array<vscode.LanguageModelTextPart | vscode.LanguageModelToolCallPart> = [];
    if (message.content) {
      parts.push(new vscode.LanguageModelTextPart(message.content));
    }
    for (const toolCall of message.toolCalls ?? []) {
      parts.push(
        new vscode.LanguageModelToolCallPart(
          toolCall.callId ?? crypto.randomUUID(),
          toolCall.name,
          toolCall.input ?? {}
        )
      );
    }
    return vscode.LanguageModelChatMessage.Assistant(parts.length > 0 ? parts : "");
  }

  const content =
    message.role === "system"
      ? `[System instructions]\n${message.content}`
      : message.content;
  return vscode.LanguageModelChatMessage.User(content);
}

function renderModel(model: ChatModel): string {
  return [model.vendor, model.family ?? model.id].filter(Boolean).join(":") || "unknown-model";
}

function renderModelDetails(model: ChatModel): string {
  return [
    `vendor=${model.vendor ?? "unknown"}`,
    `family=${model.family ?? "unknown"}`,
    `id=${model.id ?? "unknown"}`
  ].join(" ");
}

function renderStatus(): string {
  return [
    `Status: ${lastStatus}`,
    `Model: ${lastModel}`,
    `Server: ${serverState}`,
    `Port: ${lastPort}`,
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
    statusBarItem.text = "$(sync~spin) LM Bridge";
    statusBarItem.tooltip = renderStatus();
  } else if (state === "error") {
    statusBarItem.text = "$(error) LM Bridge";
    statusBarItem.tooltip = renderStatus();
  } else {
    statusBarItem.text = "$(beaker) LM Bridge";
    statusBarItem.tooltip = renderStatus();
  }

  statusBarItem.show();
}
