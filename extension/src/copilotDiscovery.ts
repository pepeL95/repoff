import * as vscode from "vscode";
import {
  CommandInventory,
  DiscoverySnapshot,
  DiscoveredExtension,
  ExportSummary,
  ExtensionActivationResult,
  LoggerLike
} from "./types";

const EXTENSION_KEYWORDS = ["copilot", "github", "chat"];
const COMMAND_KEYWORDS = ["copilot", "github.copilot", "chat", "agent", "inlinechat", "mcp"];

const CANDIDATE_EXTENSION_IDS = [
  "github.copilot",
  "github.copilot-chat",
  "GitHub.copilot",
  "GitHub.copilot-chat"
];

export async function runDiscovery(
  logger: LoggerLike,
  autoActivateCopilot: boolean
): Promise<DiscoverySnapshot> {
  const installedExtensions = vscode.extensions.all
    .filter((extension) => containsKeyword(extension.id, EXTENSION_KEYWORDS))
    .map<DiscoveredExtension>((extension) => ({
      id: extension.id,
      version: extension.packageJSON?.version ?? "unknown",
      isActive: extension.isActive,
      extensionPath: extension.extensionPath
    }))
    .sort((a, b) => a.id.localeCompare(b.id));

  const commandInventoryBefore = await listCommandInventory();
  logger.info("Discovery: installed extensions", installedExtensions);
  logger.info("Discovery: command inventory before activation", commandInventoryBefore);

  const attemptedActivations = autoActivateCopilot
    ? await activateCandidates(logger)
    : [];

  const commandInventoryAfter = autoActivateCopilot ? await listCommandInventory() : undefined;
  const exportSummaries = summarizeExports(logger);

  if (commandInventoryAfter) {
    logger.info("Discovery: command inventory after activation", commandInventoryAfter);
  }

  logger.info("Discovery: export summaries", exportSummaries);

  return {
    timestamp: new Date().toISOString(),
    installedExtensions,
    commandInventoryBefore,
    commandInventoryAfter,
    attemptedActivations,
    exportSummaries
  };
}

export function summarizeCommandDiff(snapshot: DiscoverySnapshot): string[] {
  if (!snapshot.commandInventoryAfter) {
    return [];
  }

  const before = new Set(snapshot.commandInventoryBefore.interesting);
  return snapshot.commandInventoryAfter.interesting.filter((command) => !before.has(command));
}

async function listCommandInventory(): Promise<CommandInventory> {
  const all = await vscode.commands.getCommands(true);
  const interesting = all.filter((command) => containsKeyword(command, COMMAND_KEYWORDS)).sort();
  return {
    all: all.sort(),
    interesting
  };
}

async function activateCandidates(logger: LoggerLike): Promise<ExtensionActivationResult[]> {
  const results: ExtensionActivationResult[] = [];

  for (const id of CANDIDATE_EXTENSION_IDS) {
    const extension = vscode.extensions.getExtension(id);
    if (!extension) {
      results.push({ id, wasInstalled: false, activated: false });
      continue;
    }

    try {
      await extension.activate();
      results.push({ id, wasInstalled: true, activated: extension.isActive });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.warn(`Discovery: failed to activate ${id}`, { error: message });
      results.push({ id, wasInstalled: true, activated: false, error: message });
    }
  }

  return results;
}

function summarizeExports(logger: LoggerLike): ExportSummary[] {
  const summaries: ExportSummary[] = [];

  for (const id of CANDIDATE_EXTENSION_IDS) {
    const extension = vscode.extensions.getExtension(id);
    if (!extension) {
      continue;
    }

    const exportsValue = extension.exports;
    const summary = summarizeSingleExport(id, exportsValue);
    summaries.push(summary);
    logger.info(`Discovery: exports for ${id}`, summary);
  }

  return summaries;
}

function summarizeSingleExport(id: string, value: unknown): ExportSummary {
  if (value === null) {
    return { id, exportKeys: [], exportType: "null" };
  }

  if (value === undefined) {
    return { id, exportKeys: [], exportType: "undefined" };
  }

  if (typeof value !== "object") {
    return { id, exportKeys: [], exportType: typeof value };
  }

  return {
    id,
    exportKeys: Object.keys(value as Record<string, unknown>).sort(),
    exportType: value.constructor?.name ?? "object"
  };
}

function containsKeyword(value: string, keywords: string[]): boolean {
  const haystack = value.toLowerCase();
  return keywords.some((keyword) => haystack.includes(keyword));
}
