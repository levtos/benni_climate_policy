"""Exercise the season matrix save and refresh with controlled response order."""
from __future__ import annotations

import json
import subprocess

from custom_components.benni_climate_policy.tuning_options import tuning_options_snapshot


def test_seasonal_boost_checkbox_reloads_after_each_save():
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("custom_components/benni_climate_policy/frontend/app/main.js", "utf8");
const sandbox = {
  HTMLElement: class { attachShadow() {} },
  customElements: { get() {}, define() {} },
};
const { BcpApp, renderThresholds } = vm.runInNewContext(
  source + "\n({ BcpApp, renderThresholds });", sandbox
);
const options = JSON.parse(fs.readFileSync(0, "utf8"));
const snapshot = () => ({ debug: { tuning_options: structuredClone(options) } });
const autumn = "threshold_autumn_boost_disabled";
const lateAutumn = "threshold_late_autumn_boost_disabled";
let requests = 0;
let delayNextFetch;
const writes = [];
const hass = {
  states: {},
  services: { benni_climate_policy: { update_options: {} } },
  async callApi(method, path) {
    assert.equal(method, "GET");
    assert.equal(path, "benni_climate_policy/debug");
    requests++;
    const data = snapshot();
    const delay = delayNextFetch;
    delayNextFetch = null;
    if (delay) await delay;
    return data;
  },
  async callService(domain, service, data) {
    assert.equal(domain, "benni_climate_policy");
    assert.equal(service, "update_options");
    writes.push(data.options);
    Object.assign(options.values, data.options);
  },
};

async function openPanel() {
  const app = new BcpApp();
  app._hass = hass;
  app._view = "thresholds";
  app._scheduleRender = () => {};
  app._toast = () => {};
  await app._fetchDebugPayload();
  return app;
}

function checked(app, key) {
  const checkbox = renderThresholds(hass, app)
    .match(new RegExp(`<input type="checkbox" data-tuning-key="${key}"[^>]*>`));
  assert.ok(checkbox, `Missing checkbox for ${key}`);
  return checkbox[0].includes(" checked");
}

async function verify() {
  let app = await openPanel();
  for (const [key, value] of [[lateAutumn, true], [autumn, true], [lateAutumn, false], [autumn, false]]) {
    const otherKey = key === autumn ? lateAutumn : autumn;
    const otherValue = checked(app, otherKey);
    assert.equal(checked(app, key), !value);
    app._handleTuningInput({ type: "checkbox", checked: value, dataset: { tuningKey: key } });
    assert.equal(checked(app, key), value);

    let finishOldFetch;
    delayNextFetch = new Promise(resolve => { finishOldFetch = resolve; });
    const oldFetch = app._fetchDebugPayload(true);
    const requestsBeforeSave = requests;
    await app._handleAction("tuning-save");
    assert.equal(requests, requestsBeforeSave + 1, "Saving must issue a fresh GET");
    assert.equal(JSON.stringify(writes.at(-1)), JSON.stringify({ [key]: value }));
    assert.equal(checked(app, key), value);

    finishOldFetch();
    await oldFetch;
    assert.equal(checked(app, key), value, "A late response must not undo the saved checkbox");
    assert.equal(checked(app, otherKey), otherValue);
    app = await openPanel();
    assert.equal(checked(app, key), value);
    assert.equal(checked(app, otherKey), otherValue);
  }
}

verify().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(tuning_options_snapshot({})),
        encoding="utf-8",
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
