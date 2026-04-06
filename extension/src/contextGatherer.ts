import * as path from "node:path";
import * as vscode from "vscode";
import { PromptContext, VscodeDiagnostics } from "./types";

export async function gatherPromptContext(): Promise<PromptContext> {
  const workspaceFolders = vscode.workspace.workspaceFolders?.map((folder) => folder.uri.fsPath) ?? [];
  const activeEditor = vscode.window.activeTextEditor;
  const diagnostics = collectDiagnostics(vscode.languages.getDiagnostics());

  return {
    cwd: workspaceFolders[0] ?? null,
    workspaceFolders,
    activeFile: activeEditor?.document.uri.fsPath ?? null,
    selection: activeEditor ? selectedText(activeEditor) : null,
    diagnostics
  };
}

function selectedText(editor: vscode.TextEditor): string | null {
  if (editor.selection.isEmpty) {
    return null;
  }

  const text = editor.document.getText(editor.selection).trim();
  return text.length > 0 ? text : null;
}

function collectDiagnostics(entries: VscodeDiagnostics): PromptContext["diagnostics"] {
  const flattened: PromptContext["diagnostics"] = [];

  for (const [uri, diagnostics] of entries) {
    for (const diagnostic of diagnostics) {
      flattened.push({
        file: uri.fsPath || path.basename(uri.path),
        message: diagnostic.message,
        severity: severityName(diagnostic.severity),
        range: `${diagnostic.range.start.line + 1}:${diagnostic.range.start.character + 1}`
      });
    }
  }

  return flattened.slice(0, 50);
}

function severityName(severity: vscode.DiagnosticSeverity): string {
  switch (severity) {
    case vscode.DiagnosticSeverity.Error:
      return "error";
    case vscode.DiagnosticSeverity.Warning:
      return "warning";
    case vscode.DiagnosticSeverity.Information:
      return "information";
    case vscode.DiagnosticSeverity.Hint:
      return "hint";
    default:
      return "unknown";
  }
}
