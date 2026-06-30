// VS Code client for the tods-validate language server.
//
// It launches `tods-validate-lsp` (from the Python package's [lsp] extra) over
// stdio and points it at the TODS files in the workspace. The server does the
// real work: it re-validates the whole feed on open and save and returns
// diagnostics, hovers, and quick fixes. This file only wires the two together.

import { workspace, ExtensionContext, window } from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

// The TODS files the server validates; the client only attaches to these.
const TODS_FILENAMES = [
  "run_events.txt",
  "employee_run_dates.txt",
  "vehicles.txt",
  "vehicle_assignments.txt",
  "trips_supplement.txt",
  "stops_supplement.txt",
  "stop_times_supplement.txt",
  "routes_supplement.txt",
  "calendar_supplement.txt",
  "calendar_dates_supplement.txt",
];

let client: LanguageClient | undefined;

export function activate(context: ExtensionContext): void {
  const serverPath = workspace
    .getConfiguration("tods-validate")
    .get<string>("serverPath", "tods-validate-lsp");

  const serverOptions: ServerOptions = {
    command: serverPath,
    transport: TransportKind.stdio,
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: TODS_FILENAMES.map((name) => ({
      scheme: "file",
      pattern: `**/${name}`,
    })),
    outputChannelName: "TODS Validate",
  };

  client = new LanguageClient(
    "tods-validate",
    "TODS Validate",
    serverOptions,
    clientOptions,
  );

  client.start().catch((error) => {
    window.showErrorMessage(
      `TODS Validate could not start '${serverPath}'. Install it with ` +
        `"pip install 'tods-validate[lsp]'" and set tods-validate.serverPath if ` +
        `it is not on your PATH. (${error})`,
    );
  });
}

export function deactivate(): Thenable<void> | undefined {
  return client?.stop();
}
