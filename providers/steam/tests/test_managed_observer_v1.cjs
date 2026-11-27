// Provider unit fixture: no client, credentials, network or game.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const window={};
const complete='Depot download complete : "/home/steamprobe/.steam/debian-installation/ubuntu12_32/steamapps/content/app_123/depot_789" (manifest 3512319404653808464) \n';
let callback;
let unregisters=0;
const commands=[];
const SteamClient={Console:{
  RegisterForSpewOutput(fn){callback=fn;fn({spew:complete});return {unregister(){unregisters++;}};},
  ExecCommand(command){commands.push(command);callback({spew:command,spew_type:'input'});}
}};
const run=new Function('window','SteamClient','setTimeout','clearTimeout','queueMicrotask',`return ${input.expression}`);
const execute=()=>run(window,SteamClient,()=>1,()=>{},fn=>fn());
assert.deepEqual(execute(),{issued:true});
assert.equal(window.__rheniumPreparation.count,0); // Ignore completion before our command echo.
assert.equal(window.__rheniumPreparation.echoes,1);
callback({spew:'unrelated\n'+complete});
assert.equal(window.__rheniumPreparation.phase,'complete');
assert.equal(window.__rheniumPreparation.manifest,'3512319404653808464');
assert.equal(window.__rheniumPreparation.count,1);
assert.equal(unregisters,1);
assert.throws(execute,/Already attempted/);
assert.deepEqual(commands,['download_depot 123 789 3512319404653808464']);
console.log('Managed observer unit checks passed; stale events, exact identity and single-send guard verified.');
