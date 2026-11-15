# Performance patch checks

## Current-source build and test entry points

Native fixtures reconstruct the ordered patch list from the current package
recipe, using the exact `MIXXX_COMMIT` in `source-versions`. Supply an explicit
local Git source containing that commit; historical recovery fixture trees are
not the current source of truth:

```sh
MIXXX_TEST_SOURCE=/absolute/path/to/upstream-mixxx \
  python3 -B tools/performance/required-native.py
```

The required gate is Linux-only, needs Qt6 development tools, the SQLite plugin,
libsndfile development files and working peer-pidfd support. Missing inputs,
skips and expected failures are failures, not successful acceptance. CI image
and package jobs depend on this gate; configuring it is not evidence that a CI
run has executed. Ordinary host discovery can still report platform skips.
On macOS, set `QT_SDK_PATH` for portable Qt checks; it does not qualify Linux IPC.

Source package builds preserve explicit `CMAKE_BUILD_PARALLEL_LEVEL` and
`CTEST_PARALLEL_LEVEL` (positive integers up to 64), defaulting to two jobs each.
`CCACHE_MAXSIZE` defaults to `1G` and accepts integral `16M`–`4096M` or `1G`–`4G`;
compression defaults on. These are resource settings, not measured peak-space
or memory admission. Do not restart an old VM or build under an old launch seal.

The shared recipe emits a mandatory `<package>.deb.candidate.json` sidecar.
It binds the DEB and packaged ELF to the composed source, ordered patches,
recipe, configuration and tools. Keep the sidecar basename with the package:

```sh
python3 tools/performance/mixxx-candidate.py verify --output-dir /fresh/package/output
```

Only the image's normal package-install path adds `--installed /usr/bin/mixxx`
after apt installation to compare the installed file and package ownership.
The manifest is provenance, not a signature, owner approval or runtime proof.
Do not retroactively label older accepted artifacts with a new sidecar, make
the sidecar optional, or substitute this for accepted-artifact import guards.
Keep source-build outputs fresh; existing packages/sidecars fail closed.

## November 11 field continuation

The owner confirms EOS boots/general operation, but native UI quality is
rejected and recording/first-start/media workflow remain incomplete. Prior
isolated tests did not qualify operational eject. Use the current stocktake
at `docs/ideas/FIELD-FIXES-20261111.md`, draft contract
`mixpi-field-fixes-20261111` in the adjacent climb-contract-tuner, and
`tools/ui-tuner/` for actual-photo versus historical-native comparison.
No live Pi/card writes or broker activation occur during this preparation.

Offline Step 2/4 preflight: `python3 tools/performance/check-controlled-media.py
--rootfs /explicit/unmounted/staged/rootfs` emits JSON without running image code
or changing policy. Exit 1 = static failure; 2 = unverified (never safe eject).
Fixtures: `python3 -m unittest discover -s tests -p test_controlled_media_profile.py -v`.
See `docs/setup/CONTROLLED-MEDIA.md` for provenance limitations, finite runtime
checks and the **proposed, unapproved** independent offline recovery procedure.
No current rootfs/full image is available; recipe/fixture passes are not installed-
image qualification. Step 1 ownership is done; Step 3 full rebuild/runtime/image
and Step 4 preservation/flash remain separate. Evidence:
`deploy/recovery-20261109/offline-qualification/`.

The corrected offline checker passed bounded independent re-review; evidence is
in `deploy/recovery-20261109/checker-fixes/`. Native controlled LOAD/mount and
EJECT GUI integration and its completion/Browse refresh fixes passed bounded
independent review. Final fix evidence: `deploy/recovery-20261109/gui-lazy-probes/`.
Step 3's consistent full native build and strict bounded provenance passed
independent review for attempt3 plus resume4. Its subsequent startup repair and
incremental candidate also passed artifact review. The repaired DEB `40fb4a74485a67c3ea0b33a3a01f661d4d2d6b19dc929d9441e7a50a878749c1`
now passes independent scoped package/runtime review: normal authenticated install,
six clean app exits, synthetic null playback, settings persistence and cache
denial/recovery/final-use release. Actual-image qualification remains pending.
Historical build hashes and evidence:
`deploy/recovery-20261110/full-native-build/attempt3/resume4/DELIVERY.md`.
A different HOME alone does not isolate native cache/IPC paths; follow the
disposable boundary requirements in `docs/setup/CONTROLLED-MEDIA.md`. Current
software evidence: `deploy/recovery-20261110/runtime-repaired-20261110T1542Z/`;
reviewed scope: `deploy/recovery-20261110/runtime-acceptance-20261110/REVIEWED-RESULT.json`.
LOAD coverage is ancestry-denial/refresh/cancel; EJECT covers denial only. IPC
listeners/locks release, but a stale private socket pathname remains and is
reclaimed on restart. Pathname existence is not a readiness/liveness check.
These source/build milestones do not qualify an actual image
or authorize activation or physical-media removal.

Exact-artifact ingestion for a fresh image build now has independent scoped
acceptance. It preserves the reviewed DEB and overlay rather than rebuilding
Mixxx or regenerating Pioneered; controlled profile must remain explicitly OFF.
The reviewed snapshot and usage are in
`deploy/recovery-20261110/artifact-ingestion-fixes-20261110/HANDOFF.txt`;
independent acceptance is retained in
`deploy/recovery-20261110/ingestion-acceptance-20261110/independent-review/REVIEW.txt`.
Actual Linux image assembly/export and recovery acceptance remain pending.

The accepted DEB records mode `0775` on three private package directories:
`usr/share/mixxx`, `usr/share/mixxx/udev`, and
`usr/share/mixxx/udev/rules.d`. Artifact ingestion explicitly hardens only these
directories to `0755` after normal installation, before payload verification.
The hardener prevalidates their approved manifest records, directory types,
ownership and exact `0775`/`0755` modes using non-following directory descriptors.
Shared system directories, the DEB, and regular-file bytes are not rewritten.
The existing writable-parent rejection remains unchanged; final verification
requires these three directories to stay `0755`. Independent Sol 6.1 review
accepted this exact offline delta. The next fresh Linux build passed exact-DEB
extraction, normal installation and final integration; image export then failed
because final chroot validation left virtual filesystems mounted. Evidence:
`deploy/recovery-20261110/image-directory-hardening-20261110T205621Z/independent-review/REVIEW.txt`.

Final accepted-artifact validation now requires checked unmount before export;
the unmount helper explicitly propagates its first failure rather than looping
under a conditional caller. This prevents sizing a still-mounted `/proc/kcore`
as image content. The 367-test host suite passes (59 skips), including the new
behavioral mount-lifecycle regression; the opt-in real Linux lifecycle check
passed on Linux with all eight regressions executed, zero skips. Independent
Sol 6.1/high delta review accepted the exact three-file change with 17 fresh
fixtures. A fresh normal-apt image is now assembled, statically inspected and
exported as gzip; independent Sol 6.1/high review accepts exact assembly,
static inspection evidence and export. No rebuild or repeat of the six accepted
runtime sessions is required. Image boot/recovery and production activation
remain unaccepted. Final root is observed
locked; pi has a private test credential and SSH is disabled. Stock sudo and
automount authority remains with controlled profile OFF.
Evidence: `deploy/recovery-20261111/image-export-unmount-fix/` and
`deploy/recovery-20261110/image-build-local-20261110T211642Z/HANDOFF.txt`.
The successful build and exported image identities are in
`deploy/recovery-20261111/image-build-local-20261110T220134Z/HANDOFF.txt`.
Independent image acceptance is retained in
`deploy/recovery-20261111/image-acceptance/independent-review/REPORT.txt`.
Recovery is not ready: a fresh bounded check found no exact September
historically booted image in the recorded local/GitHub locations. No replacement
image was downloaded or treated as known-good rollback. The accepted new image
and user-data backups are not independent bootable recovery. Evidence and the
remaining stopped-backup/physical gates are in
`deploy/recovery-20261111/recovery-availability-20261110T225034Z/REPORT.txt` and
`docs/setup/SAME-CARD-UPGRADE.md`. The unavailable recovery bytes do not require
another candidate build or repetition of accepted runtime sessions.

On November 11 the user-authorized 16 GB EOS spare was flashed with this exact
image using Raspberry Pi Imager 2.0.11.1 GUI, without library restoration or OS
customisation. Imager completed verification without skipping and automatically
ejected it; host inventory confirmed target disappearance at 08:52:04 UTC.
Earlier CLI/direct-write failures remain separate historical evidence. See
`deploy/recovery-20261111/eos-test-card-20261111/GUI-ATTEMPT.md` and its separate
`GUI-RESULT.json`. The original Pi card remains untouched; actual spare-card
boot/audio/controller/touch/USB tests and operational EJECT are not accepted.

Future package audits must prove executable equivalence rather than merely
allowing `usr/bin/mixxx` to differ from the stage. On a quiescent build host, run:

```sh
python3 tools/performance/check-stripped-executable.py \
  --staged /explicit/stage/usr/bin/mixxx \
  --packaged /explicit/extracted/usr/bin/mixxx \
  --strip-tool /explicit/frozen/toolchain/strip \
  --strip-sha256 "$FROZEN_STRIP_SHA256"
```

Set `FROZEN_STRIP_SHA256` from the prebuild tool manifest, not a new observation.
Treat a nonzero exit as audit failure. The helper executes only the explicitly
selected strip tool, writes to temporary scratch, compares exact output bytes,
and checks inputs remained unchanged. It never launches Mixxx or modifies either
executable. Freeze the tool's supporting dependencies separately; its digest alone
does not establish full tool provenance. The accepted resume4 bytes already passed
independent exact strip comparison; this future-run safeguard does not alter that
candidate or its historical receipts. Focused tests:
`python3 -m unittest discover -s tests -p test_stripped_executable.py -v`.

Controlled appliance broker implementation (review candidate): see
`docs/setup/CONTROLLED-MEDIA.md`. It adds actual normal mount/unmount backend
code, a root-only native drain/retirement protocol, a bounded authenticated
control endpoint and an opt-in restricted future-image profile. Neither the
review capability nor native GUI EJECT is enabled. Synthetic backend tests and
scratch Linux transport/object builds are not physical-eject acceptance.

Broker review fixes 1/4 use a root-authenticated namespace-fd proof for the
actual root broker/non-root native boundary, and `ready` → `commit`/`committing`
→ execution polling with acknowledged pre-cutoff cancellation. Tests cover real
Linux socketpairs/pidfds, cross-UID native transport and descriptor cleanup;
mount/unmount completion remains synthetic. See `CONTROLLED-MEDIA.md` for the
separate administrator/offline recovery blocker before profile activation.

`test-ram-cache.sh` extracts the actual cache header from the image patch,
compiles it with Qt 6, and exercises it independently of Mixxx. Run on Linux
with `g++`, `pkg-config`, `python3`, and Qt6Core development files:

```sh
bash tools/performance/test-ram-cache.sh
```

The test refuses to run while Mixxx is running or its fixed RAM-cache directory
already exists. It creates temporary source files, limits the cache to 1 MiB,
and checks copied bytes, shared-reader lifetime, stale-source replacement,
source removal, the size budget, missing files, concurrent requests and
WavPack companion cleanup. It uses no music library or audio devices.

On 2026-11-09 this exposed an ambiguous Qt 6 `qBound` overload on the Pi's
Qt 6.8.2. Explicit 64-bit bounds fixed compilation, and the smoke check passed.
The ARM package workflow now runs it before compiling Mixxx.

This does **not** validate audio decoding, playback, hotplug races, or safe
physical eject. The cache still falls back to the original track if copying
or decoding fails. Do not unplug a device based only on these results.

## Fast iteration and evidence

Reuse the implementation checkout for follow-up fixes; reviewers use a separate
read-only snapshot. Preserve the parent's dirty baseline and apply only verified
incremental changes. Do not rebuild or rehydrate unchanged sources every round.

Start with a failing regression, then the affected suite. The completion-recovery
test extracts the real activation, reconciliation and completion methods from
the pinned source plus image patches; Qt, observation and SQL dependencies are
test doubles, not runtime acceptance. Supply a local Mixxx git checkout containing
the pinned commit to avoid fetching source:

```sh
MIXXX_TEST_SOURCE=/path/to/mixxx python3 -m unittest discover -s tests -p test_media_completion.py -v
PIONEERED_TEST_SKIN=/path/to/pioneered python3 -m unittest discover -s tests -v
```

Record elapsed time separately for setup, focused tests, native compilation,
full tests and review. Reuse native outputs only with matching source/header,
generated-input, dependency and compiler-flag fingerprints. Compile affected
translation units first; full linking/package/image builds remain milestone
gates. Review and compilation may overlap on the same frozen revision, but any
subsequent edit invalidates the affected evidence. Model leases and mocked
unmounts never count as successful physical-eject acceptance.

### Native ownership foundation (not operational eject)

The media-selection image patch now contains a process-local native registry.
Its generation key includes boot, mount namespace, canonical physical sysfs
device, device number and diskseq. Admission and local drain share one mutex;
shared request ownership survives queue copies until the last consumer releases
it. Only control/worker/sidechain threads use this API, never the audio callback.
An idle local drain is **not** authorization to unmount.

Actual callers include the caching-reader pending request and audio proxy
(including RAM-cache copy/original fallback), analyzer worker queue, Rekordbox
discovery/import completion, BrowseThread, TrackLoader, cover-art futures,
metadata import/export, recording file/cue flush, and track-file export. Where
identity or complete destination accounting is unavailable, a temporary global
busy guard blocks every local drain until that operation completes. It is not
a permanently asserted coverage flag.

The host ownership regression compiles extracted production methods with
Qt/decoder/filesystem doubles. The ARM path smoke uses only a caller-owned
synthetic fixture directory. Neither is full Mixxx runtime or physical-eject
acceptance. Supply `MIXXX_TEST_SOURCE` for local pinned patch-stack testing
without a network clone.

The fallback regression also compiles the production cache-mode constructor,
not a substitute: failed Create/Existing cache acquisition must reject a changed
physical generation before initializing the original-file decoder. A failed
cache acquisition on unchanged media must still permit normal fallback.

Still required: independent review and full native validation of the finite
in-process closures and authenticated external-copy implementation below,
and a reviewed broker owning mount topology/automounter/namespace transitions.
Descriptors pin the inspected objects, not later pathname resolution. Unknown
aliases and stacked/uncontrolled topology cannot authorize removal. Production
EJECT remains BLOCKED; the next milestone must close these gaps, not replace
them with FD scans, Python coverage assertions, or check-path-then-umount.

Scanner/task and scheduler backlog admission is now implemented in the shipping
patch. The scanner acquires a temporary unknown-media lease before posting its
start callback, shares it with task state, and retains it through final cleanup.
Task construction registers with TaskWatcher before cancellation can destroy the
task, balancing deletion before pool admission as well as pool cancellation.
The scheduler guards its synchronous database/file-access handoff temporarily,
then queues a loaded track with a generation-specific lease. Worker retries keep
that lease; changed generations are discarded rather than stranding the backlog.
Stop clears queued ownership but does not release a worker's live ownership.

The unknown handoff and whole-scan guards are deliberately conservative: they
reject admission while any generation drains and block all local drains only
while that work is outstanding. Scheduler backlog leases themselves are per-drive.
`test_media_backlog.py` compiles extracted production admission, submission, stop,
scan posting, and task lifetime methods against the native registry, with Qt,
database and worker scheduling doubles. It covers pending work, busy-worker retry,
cancel/retry, stale generation rejection, distinct drives and task accounting;
it is not a linked Mixxx runtime or eject acceptance test. The finite GUI/helper
closures and external-copy implementation below supplement it; integrated runtime
and broker lifecycle still require validation.

### Location lookup and spawned cover work

The eighth patch now admits PlayerManager location requests before Library's
`TrackRef::fromFilePath`, carries the lease across both QObject handoffs, and
revalidates before resolving the location and before handing the Track to the
player. The existing synchronous player/engine/caching-reader chain inherits
that same path lease before the caching worker retains its pending request.
`PathUseScope` is an operation-local, thread-local stack for synchronous calls,
not ownership stored on a cached Track. Queued callbacks explicitly capture the
lease; rejected posting or callback destruction releases it. No audio callback
uses this scope or the registry.

TrackDAO's `getOrAddTrack`, `getTrackByRef`, cache-miss `getTrackById`, and
`addTracksAddFile` guard file resolution/import; direct bulk `resolveTrackIds`
and scanner `addTracksAddFile` callers therefore reach guarded import code.
The database cover scan guards each track. TrackLoader now retains a path lease
instead of an unknown-media lease, and cover-guess futures retain/revalidate
the originating track generation, including calls from WCoverArt/WSpinnyBase.
Unknown paths still use the existing temporary coarse admission; they are not
proof that a missing path belongs to a particular drive.

`test_media_location.py` compiles the actual PlayerManager/Library entry methods,
both production connection lambdas, TrackLoader methods, TrackDAO get-or-add
and add-file methods, and concurrent cover submission. Filesystem/Qt/SQL/decoder
dependencies are doubles. It checks drain-before-admission, replacement at both
GUI queues and the loader/cover queues, cancelled/rejected queues, missing paths,
and unrelated-drive idleness. The large get-by-ID and database cover-scan methods
have admission-order assertions and ARM compilation, not full runtime execution.
Evidence: `deploy/recovery-20261109/location-handoff/`.

### Finite in-process closures

The eighth patch now guards BrowseTableModel, both base external models,
Banshee's playlist model and legacy cover-digest lookup before TrackRef
resolution. These pass the path lease through `PathUseScope` to the DAO;
changed generations remain rejected. Banshee's location and ID helpers also
guard their earlier FileInfo resolution. Purge selection and `getAllTrackRefs`
use finite coarse ownership; cached relocation guards both the complete cache
walk and the DAO callback.

Direct cover guessing, directory enumeration, selected-image decoding and
`CoverInfo::loadImage` use finite unknown-media scopes. This covers the three
reload dialogs and a cover symlink pointing off the track's drive. A track's
lease alone does not authorize touching that other drive. Denied track guessing
preserves existing cover info. These guards conservatively block all local
drains while active, then release; they do not identify unknown destinations.

Sampler-bank load/save and playlist parsing/writing (M3U/M3U8, PLS, CSV and
readable text), plus the playlist/crate GUI's post-dialog filesystem work and
shared save-dialog extension/existence checks, now have
operation scopes. Engine Prime holds one scope through its worker's actual
run, including destination creation, copy, database work, cancellation and
error exits. Its three blocking GUI callbacks explicitly capture that scope's
lease. External-collection save/update/purge/relocation dispatches in
TrackCollectionManager and WTrackMenu are guarded for their synchronous calls;
the pinned source has no concrete ExternalTrackCollection subclass. This is
not a promise of ownership for future asynchronous plugin implementations.

`UnknownUseScope` shares only explicit operation-local ownership across nested
synchronous helpers; Engine Prime explicitly carries it across thread callbacks.
It is not a global or permanent busy flag. Existing per-path inheritance,
scanner/scheduler ownership and failed-copy fallback checks are unchanged.
The scanner already owns the actual `detectMovedTracks`/`verifyRemainingTracks`
callers. TrackLoader has no other production result consumer to close here.

`test_media_finite.py` compiles the actual Browse getTrack, sampler-bank save,
cover directory enumeration and cover selection methods. Synthetic filesystem,
Qt/DOM doubles and registry generations cover pre-I/O drain denial, symlinks,
cross-drive cover access, errors, new destinations, idle release, queued-scope
cleanup and same-generation path continuity. Other finite entry points have
admission-order assertions and affected-unit compilation, not full execution
coverage. Final host run: 226 tests, 200 passed, 26 skipped (17.782 seconds).
All 22 affected ARM translation units compiled, including Engine Prime with
`__ENGINEPRIME__`; final source/header/dependency hashes were rechecked. Evidence,
per-unit timings and compiler flags are recorded in
`deploy/recovery-20261109/finite-closures-1635/receipt.json`.

This is not universal filesystem or physical-eject acceptance. Independent
review, full header-consumer rebuild/link,
and runtime integration remain gates. External-copy admission is implemented below;
the controlled-topology broker remains the next milestone. EJECT stays BLOCKED.

Drain-denial recovery has dedicated production-extraction regressions in
`test_media_denial.py`. Track eviction still persists dirty metadata in the
internal database when removable-media admission is denied; tag export and
external-collection writes remain guarded, and source synchronization is
invalidated on denial. An actual internal database save failure still leaves
the track dirty; this change does not redesign existing database-failure recovery.
Engine Prime clears the previous waveform when loading a track, rejects a null
DAO result before analysis access, and reports worker failure on rejected callback
posting or unavailable tracks before exporting. Cancellation and normal waveform
loading are regression-tested too. The worker test extracts the actual handoff
segment, not the entire export/database implementation; Qt/DAO behavior is doubled.

### Authenticated external copy admission (review pending; no eject)

The shipping eighth patch now includes `library/media/copyservice.h`, owned by
the existing `MixpiMedia` Library control-thread timer. It directly acquires the
same native `media::registry()` Copy leases as in-process producers. No new
daemon, audio-callback I/O, command execution facility, or unmount path is added.
The 20 ms timer serves bounded Unix SEQPACKET requests (16 KiB, six paths,
32 sessions, eight accepts per tick; unstarted sessions expire after two seconds).
`/run/user/<uid>/mixpi-copy` is 0700, its socket and lock files 0600. Kernel
SO_PEERCRED and SO_PEERPIDFD authenticate the same appliance UID and bind ownership
to the connected process, not a reusable PID. The mount namespace must match.
Linux without SO_PEERPIDFD support is deliberately unsupported and fails closed.

BEGIN resolves each existing path or a validated existing ancestor, rejects
symlinks, unknown physical identity and unsupported topology, and retains both
generation and resolved mount identity. Missing destinations are never admitted
as unknown-media leases. Roots are restricted to the passwd home and that user's
`/media` and `/run/media` directories; an allowed existing ancestor is mandatory.
CHECK revalidates retained bindings and explicitly requested descendant paths.
The source and destination generations are independently counted; unrelated
drives do not become busy during normal transfers. A draining generation rejects
new admission but does not revoke a previously admitted operation.

`mixpi-media` now wraps planning/enumeration, copy, recordings listing/selection,
and recordings movement in native sessions, including verification, publication,
cleanup and verified source deletion. Plans and recording selections retain the
native proofs for the subsequent transfer. Existing filesystem safeguards remain.
FINISH or CANCEL is sent only after synchronous work and its finally blocks end.
The recordings mover refreshes its target under that existing session rather
than requesting nested admission. A drain begun after outer admission therefore
waits for the verified move to finish; target path and selection-proof checks
remain in force. A real Linux transport regression exercises this interleaving.
Disconnect retains ownership until the kernel pidfd reports process exit.
A watchdog checks every 100 ms (two-second socket timeout); loss or invalidation
terminates the actual helper process with status 74, rather than continuing or
reconnecting. This may leave an unpublished partial file for later cleanup.

The helper holds a shared session-file lock through the entire operation. A
replacement service starts with a fail-closed unknown guard until an exclusive
lock proves prior cooperating helpers have ceased. This is a restart quarantine,
not a claim that unknown paths resolve to a drive. The lock inode/runtime directory
must not be removed or replaced while helpers survive. The supported trust domain
is the cooperative appliance user, not hostile same-UID code, descriptor delegation,
new mount namespaces or arbitrary processes writing media. In-flight syscalls are
not synchronously revocable; restart quarantine prevents those being mistaken for
idle. A blocked control event loop fails closed via the helper watchdog.

Build/install wiring remains the existing eighth-patch application and
`stage3/02-desktop/04-run.sh` installation of `mixpi-media` into `/usr/local/bin`.
The new header is consumed by `library.cpp` through `mixpimedia.h`; no additional
build target is needed. Runtime requires the rebuilt Mixxx, an active Library
control event loop, the updated helper, same UID/mount namespace, and an intact
0700 user runtime directory. The old running trial has **not** been upgraded and
does not provide this endpoint; new helper operations fail explicitly against it.

`test_media_copy_ipc.py` exercises the actual service header/native registry with
synthetic generation observations and real Linux sockets, peer credentials,
pidfds and helper processes. It also executes both actual Python transfer bodies
against that transport on scratch files. Foreign UID, malformed requests,
drain-before-copy, two generations, missing destinations, descendant aliases,
replacement, normal/cancel completion, orphan retention, confirmed exit, cross-
session release rejection, service death and restart quarantine are covered.
PID reuse is prevented by kernel handles; tests do not force numeric PID recycling.
Existing copy-correctness tests explicitly inject `ScratchAdmission`; production
has no environment-controlled fake or automatic unguarded fallback.

Hash-bound evidence is in `deploy/recovery-20261109/copy-ipc-20261109/receipt.json`.
Only the changed header consumer is ARM-compiled; full header-consumer rebuild,
link, actual Mixxx event-loop/runtime integration and independent review remain
pending. Synthetic observations are not physical-drive acceptance. Path checks
do not close check/use races against uncontrolled mount changes: the next handoff
is the controlled appliance mount-lifecycle/automounter broker, after independent
review of this boundary. **Production EJECT remains BLOCKED.** No live installation,
restart, USB writes, or unmount trial was performed.
