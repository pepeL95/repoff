import * as vscode from "vscode";
import { AskRequest, AskResponse, AskStreamEvent, LoggerLike, ProbeRoute } from "./types";

export class FallbackLm {
  constructor(private readonly logger: LoggerLike) {}

  async ask(request: AskRequest, emit: (event: AskStreamEvent) => void): Promise<AskResponse> {
    const lm = (vscode as unknown as { lm?: { selectChatModels?: (selector?: Record<string, unknown>) => Promise<unknown[]> } }).lm;
    if (!lm?.selectChatModels) {
      return {
        ok: false,
        route: "unavailable",
        error: "VS Code Language Model API is not available in this build."
      };
    }

    try {
      const models = await lm.selectChatModels({
        vendor: "copilot"
      });

      if (!models.length) {
        return {
          ok: false,
          route: "unavailable",
          error: "No compatible chat models were returned by VS Code."
        };
      }

      const model = models[0] as {
        sendRequest?: (
          messages: unknown[],
          options?: Record<string, unknown>,
          token?: vscode.CancellationToken
        ) => Promise<{ text?: AsyncIterable<string>; stream?: AsyncIterable<unknown> }>;
      };

      if (!model.sendRequest) {
        return {
          ok: false,
          route: "unavailable",
          error: "Selected model does not expose sendRequest."
        };
      }

      emit({ type: "start", route: "fallback-lm" });

      const response = await model.sendRequest([
        {
          role: "user",
          content: request.prompt
        }
      ]);

      const collected = await collectStream(response.text ?? response.stream, emit, "fallback-lm");
      return {
        ok: true,
        route: "fallback-lm",
        text: collected
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.logger.warn("Fallback LM request failed", { error: message });
      emit({ type: "error", route: "fallback-lm", message });
      return {
        ok: false,
        route: "fallback-lm",
        error: message
      };
    }
  }
}

async function collectStream(
  stream: AsyncIterable<unknown> | undefined,
  emit: (event: AskStreamEvent) => void,
  route: ProbeRoute
): Promise<string> {
  if (!stream) {
    emit({ type: "end", route, text: "" });
    return "";
  }

  let text = "";

  for await (const chunk of stream) {
    const token = normalizeChunk(chunk);
    if (!token) {
      continue;
    }

    text += token;
    emit({ type: "token", route, text: token });
  }

  emit({ type: "end", route, text });
  return text;
}

function normalizeChunk(chunk: unknown): string {
  if (typeof chunk === "string") {
    return chunk;
  }

  if (chunk && typeof chunk === "object") {
    const maybeText = (chunk as { value?: string; text?: string }).value ?? (chunk as { text?: string }).text;
    if (typeof maybeText === "string") {
      return maybeText;
    }
  }

  return "";
}
