import * as vscode from "vscode";

type DelegateTaskInput = {
  recipient: string;
  content: string;
  timeout_seconds?: number;
};

const TOOL_NAME = "delegate_task";

export function registerMaibloxTool(
  context: vscode.ExtensionContext,
  backendPort: () => number
): void {
  context.subscriptions.push(
    vscode.lm.registerTool<DelegateTaskInput>(TOOL_NAME, new DelegateTaskTool(backendPort))
  );
}

class DelegateTaskTool implements vscode.LanguageModelTool<DelegateTaskInput> {
  constructor(private readonly backendPort: () => number) {}

  async prepareInvocation(
    options: vscode.LanguageModelToolInvocationPrepareOptions<DelegateTaskInput>
  ): Promise<vscode.PreparedToolInvocation> {
    return {
      invocationMessage: `Delegating task to ${options.input.recipient}`,
      confirmationMessages: {
        title: "Delegate task to worker",
        message: new vscode.MarkdownString(
          `Send a task to \`${options.input.recipient}\` and wait for the worker response?`
        ),
      },
    };
  }

  async invoke(
    options: vscode.LanguageModelToolInvocationOptions<DelegateTaskInput>,
    token: vscode.CancellationToken
  ): Promise<vscode.LanguageModelToolResult> {
    const result = await delegateTask(this.backendPort(), options.input, token);
    return new vscode.LanguageModelToolResult([new vscode.LanguageModelTextPart(result)]);
  }
}

async function delegateTask(
  port: number,
  input: DelegateTaskInput,
  token: vscode.CancellationToken
): Promise<string> {
  if (!input.recipient?.trim()) {
    throw new Error("The recipient parameter is required.");
  }
  if (!input.content?.trim()) {
    throw new Error("The content parameter is required.");
  }

  const controller = new AbortController();
  const subscription = token.onCancellationRequested(() => controller.abort());
  try {
    const response = await fetch(`http://127.0.0.1:${port}/delegate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        recipient: input.recipient,
        content: input.content,
        timeoutSeconds: input.timeout_seconds ?? 300,
      }),
      signal: controller.signal,
    });

    const payload = (await response.json()) as { ok?: boolean; response?: string; error?: string };
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Delegation failed with status ${response.status}.`);
    }
    return payload.response || "";
  } catch (error) {
    if ((error as Error).name === "AbortError") {
      throw new Error("Delegation was cancelled.");
    }
    throw error;
  } finally {
    subscription.dispose();
  }
}
