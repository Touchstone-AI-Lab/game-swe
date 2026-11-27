# Source notices

The Adaptive Storage production baseline is commit
31ee88b46651cfbe37da3f89620bc0b907165cc0. Most files are MIT;
Fishery files retaining Mozilla Public License headers are MPL-2.0, not MIT.
The full applicable MPL is in LICENSES/MPL-2.0.txt. Original copyright and
license notices are retained. The .NET Foundation MIT headers in diagnostics
are also retained.

Benchmark adaptations expand 13 preview field-backed properties into explicit
C#12 fields in StorageRenderer, GodModeGizmos, ContentsITab, PrintDatas/PrintData,
DefEditorWindow and Fishery/Reflection. Three StorageRenderer lambdas also
declare their parameter types explicitly for C#12; their bodies and in
parameter passing are unchanged. The MPL-covered Reflection modification
remains available as source under MPL-2.0. The starter alone reconstructs the
historical slot-limit transition in ThingClass. These files are not all
byte-exact upstream. No production method body was deleted.

The upstream StorageCellRect implementation is excluded: its stated derivation
from Verse is not treated as a license grant. The build supplies an independently
authored thin wrapper over the public CellRect API. No game implementation is
copied by that wrapper.

The separately restored Multiplayer API 0.6.0 library is MIT (Zetrith); its
license is in LICENSES/MultiplayerAPI-MIT.txt. It is a library, not a requirement
to load the Multiplayer Mod. RimWorld references and actual game content remain
subject to their own rights; no game assemblies or assets are included here.
