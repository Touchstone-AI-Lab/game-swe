// Unit-only fake Steam bindings. No client, network, account, or game is used.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).expression;
const command = 'download_depot 2379780 2379781 3512319404653808464';
function setup() {
  const window = {};
  let callback;
  let unregisters = 0;
  const commands = [];
  const SteamClient = {Console: {
    RegisterForSpewOutput(fn) { callback = fn; return {unregister() {unregisters++;}}; },
    ExecCommand(value) { commands.push(value); },
  }};
  const run = new Function('window', 'SteamClient', 'setTimeout', 'clearTimeout', 'queueMicrotask', `return ${source}`);
  const execute = () => run(window, SteamClient, () => 1, () => {}, fn => fn());
  assert.deepEqual(execute(), {issued: true});
  assert.deepEqual(commands, [command]);
  return {window, emit: text => callback({spew:text,spew_type:0}), execute, commands,
    unregisters:()=>unregisters};
}
const first = setup();
first.emit('unrelated console message');
assert.equal(first.window.__rheniumDepotV1.phase, 'waiting');
first.emit('unrelated\nDepot download complete : "/home/steamprobe/.steam/debian-installation/steamapps/content/app_2379780/depot_2379781" (manifest 3512319404653808464) \n');
assert.equal(first.window.__rheniumDepotV1.phase, 'console_complete');
assert.equal(first.window.__rheniumDepotV1.manifest, '3512319404653808464');
assert.equal(first.window.__rheniumDepotV1.pathMatches, true);
assert.equal(first.unregisters(), 1);
assert.throws(first.execute, /Already attempted/);
assert.deepEqual(first.commands, [command]);
const failed = setup();
failed.emit('Depot download failed : test (unit fixture) \n');
assert.equal(failed.window.__rheniumDepotV1.phase, 'download_failed');
assert.equal(failed.window.__rheniumDepotV1.failureEvents, 1);
const wrongPath = setup();
wrongPath.emit('Depot download complete : "/different/path" (manifest 3512319404653808464) \n');
assert.equal(wrongPath.window.__rheniumDepotV1.pathMatches, false);
console.log('Steam observer unit checks passed: identity, newline parsing, exact uint64 string, failure, duplicate guard.');
