// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { describe, expect, it } from "vitest";
import { canConnectGoogle, changedSecrets, connectionLines, groupFields, parseSettings } from "./settings";

const field = (key: string, group: string, kind = "text") => ({ key, label: key, group, kind, options: [], help: "" });

describe("settings screen", () => {
  it("reads the backend's view and drops malformed fields", () => {
    const view = parseSettings({
      fields: [field("A", "Meetings"), { key: "B", kind: "weird" }],
      values: { A: "x", B: 3 },
      secretsSet: ["GITHUB_TOKEN"],
    });
    expect(view?.fields.map((item) => item.key)).toEqual(["A"]);
    expect(view?.values).toEqual({ A: "x" });
    expect(parseSettings({ fields: [] })).toBeNull();
  });

  it("groups fields in order", () => {
    const groups = groupFields([field("A", "Meetings"), field("B", "AI"), field("C", "Meetings")] as never);
    expect(groups.map(([name, fields]) => [name, fields.map((item) => item.key)])).toEqual([
      ["Meetings", ["A", "C"]],
      ["AI", ["B"]],
    ]);
  });

  it("sends only secrets that were typed or cleared", () => {
    expect(changedSecrets({ A: " new ", B: "   " }, new Set(["C"]))).toEqual({ A: "new", C: "" });
  });
});

describe("canConnectGoogle", () => {
  it("needs the saved client ID and secret", () => {
    const view = { fields: [], values: { GOOGLE_CLIENT_ID: "id" }, secretsSet: ["GOOGLE_CLIENT_SECRET"] };
    expect(canConnectGoogle(view)).toBe(true);
    expect(canConnectGoogle({ ...view, secretsSet: [] })).toBe(false);
    expect(canConnectGoogle({ ...view, values: {} })).toBe(false);
  });
});

describe("connectionLines", () => {
  it("marks each service as working, failing or unchecked", () => {
    expect(
      connectionLines([
        { service: "GitHub", ok: true, detail: "signed in as ana" },
        { service: "Jira", ok: false, detail: "HTTP 401: Unauthorized" },
        { service: "Slack", ok: null, detail: "configured" },
        { service: 3 },
      ]),
    ).toEqual(["✓ GitHub: signed in as ana", "✗ Jira: HTTP 401: Unauthorized", "– Slack: configured"]);
  });

  it("explains an empty or unreadable reply", () => {
    expect(connectionLines([])).toEqual(["Nothing to test: no AI provider or integration is configured."]);
    expect(connectionLines("oops")).toEqual(["The connection test returned nothing readable."]);
  });
});
