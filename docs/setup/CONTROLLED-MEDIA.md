# Controlled appliance media lifecycle — review candidate

## November 10 checkpoint — Step 3/4

Step 1 ownership is done. The four broker findings and corrected offline checker
passed bounded independent review. The recovery proposal passed review as an
unapproved proposal; user approval and verified prerequisites are still pending.
Native GUI review identified two success-refresh defects. The candidate now
queues owner-scoped completion callbacks instead of sampling transient states,
and uses a dedicated Browse invalidation entry point instead of right-click
context. Re-review closed those defects but found repaint-triggered directory
probes. The follow-up candidate defers model cache-miss probes before any row
notifications; attached-view regression tests and independent bounded re-review
pass. Step 2 implementation/review is accepted, not installed-image authority.
Step 3's coherent full ARM build, artifacts and strict bounded provenance now
pass independent review for attempt3 plus resume4. All 867 object/PCH outputs
have successful execution evidence. No further rebuild is required for this
bounded acceptance. Evidence and artifact hashes are in
`deploy/recovery-20261110/full-native-build/attempt3/resume4/HANDOFF.md` and
`DELIVERY.md` in that directory. The DEB excludes the separate Pioneered/tools
overlay; neither is a rootfs/image. Historical failed candidates remain uncertified.
The approved isolated ARM runtime subsequently failed normal and safe-mode startup
with recursive performance-settings publication. Independent review accepts the
seven-call `setAndConfirm()` repair and the subsequent incremental full candidate's
bounded artifact provenance and packaging. One object rebuilt and the normal
archive/relink completed; 866 object/PCH and 402 MOC outputs remained unchanged.
New DEB SHA-256: `40fb4a74485a67c3ea0b33a3a01f661d4d2d6b19dc929d9441e7a50a878749c1`.
No further rebuild is required. Independent review now accepts the exact repaired
candidate's scoped package and isolated full-app software tests. New delivery:
`deploy/recovery-20261110/settings-incremental-candidate/DELIVERY.md`.
Prior failure and repair evidence remain at
`deploy/recovery-20261110/runtime-20261110T0711Z/HANDOFF.md` and
`deploy/recovery-20261110/settings-startup-fix/HANDOFF.md`.
Authenticated recipe-matched Trixie plus Raspberry Pi repositories resolved the
unchanged dependencies; normal DEB installation and package checks passed. Six
full-app sessions exited 0, including normal/safe startup, synthetic null playback,
settings persistence/restart, final-deck cache release and denial/recovery paths.
Actual-image qualification remains pending; this is acceptance of the captured
repository snapshot and isolated software, not a Pi image or hardware trial.
Step 4 remains preservation and separately authorized flash. Neither the checker
nor accepted broker/GUI review enables safe eject.

### Next gate: exact image and recovery integration

**Accepted software milestone:** independent review verified the exact DEB/binary,
authenticated installation, prelaunch isolation and actual per-mode results.
Runtime evidence: `deploy/recovery-20261110/runtime-repaired-20261110T1542Z/HANDOFF.md`.
Scoped corrections and retained independent review:
`deploy/recovery-20261110/runtime-acceptance-20261110/REVIEWED-RESULT.json`.
LOAD passed ancestry-denial/refresh/cancel and EJECT passed service/profile denial;
successful provider selection/mount/eject remain unverified. IPC live-resource
release passes, while socket pathname removal fails nonblockingly: no listener
remains, locks release, connection attempts are refused and restart reclaims the
stale pathname. Do not infer liveness from pathname existence. The container shares
the guest kernel and user namespace; other checked namespaces are separate.
Guest virtual USB metadata was visible through sysfs, but no usable USB device
nodes or control sockets were exposed to the application. Null audio and software
rendering are not hardware quality/performance evidence.

Both VMs are stopped; all 200 protected records match and runtime services are
remasked. The working root retains intentional package/runtime writes and drop-ins.
Do not reuse a spent launch seal or claim the working root was restored. Next,
identify one exact actual image/root and review package-plus-overlay integration,
broker/profile authority and independent recovery prerequisites. Accepted package
and container evidence cannot substitute for an image or authorize activation.

**Isolated-environment incident, November 10:** the owned VM restart at
08:05:57 UTC (11:05:57 EAT) unintentionally reformatted its disposable data disk.
Lima's format-enabled check looked for a label longer than ext4 preserves and
reinitialized the existing disk when that label was absent. The agent's preboot
inspection missed this path. Prior Docker images/containers are no longer visible;
recovery is unverified. Post-incident independent disk snapshots and the original
runtime/artifact evidence are preserved. No Pi or USB operation occurred.
The first prevention proposal was insufficient: probe exit statuses and pre-guard
mount/growth/service behavior needed correction. Later preparation detached the
incident disk, used independently checked task-local ext4 tooling for bounded
working-root masks, and passed independent offline and actual diagnostic review.
The accepted boot then completed controlled package/runtime testing. Snapshots and
the original data disk remain untouched. This closes that disposable-environment
prerequisite, not a physical-card recovery rehearsal or production authority gate.
The user approved those owned-config changes, bounded working-root safety edits,
guarded diagnostics and isolated package/runtime tests.
The user subsequently approved verified task-local ext4 tooling acquisition and
broader autonomy for necessary software updates and automated checks, without
repeated approval for routine dependencies or reversible disposable-environment
preparation. Prefer task-local tooling, not system-wide installation. This does not
waive verification or preservation: the incident data disk and snapshots must remain
unchanged. Pi deployment, USB formatting/deletion and flashing remain separate.
Neither resetting protected storage nor rerunning old scripts is a workaround.
Incident evidence:
`deploy/recovery-20261110/vm-preservation-20261110T0812Z/HANDOFF.md`.

A different HOME or UID alone is insufficient: the native cache uses
`/dev/shm/mixpi-track-cache`, copy IPC uses `/run/user/<uid>/mixpi-copy`, and the
broker uses `/run/mixpi-mount/control`. Do not launch beside the live trial using
only profile or environment overrides.

The user approved a dedicated temporary ARM Colima VM. The retained test VM and
its containers are stopped; reuse only that owned environment, never the unrelated
VM sharing the host home. The completed software test used that disposable ARM environment
with private shared memory and runtime directories, synthetic media, an isolated
display and null audio. No live audio sockets, host broker connection, USB
passthrough, user drives or user profile may be exposed. Verify those boundaries
before launching the accepted candidate with its matching resources and overlay.
No synthetic broker/provider replaced production authority in this run: successful
controlled LOAD/EJECT lifecycle still needs separate qualification. Report synthetic
playback separately from real audio, installed-image authority and physical eject.
The user separately authorized ejecting the attached USB drives,
not formatting/deletion. That permission does not close the technical qualification
gates or authorize controlled-profile activation, live restart, recovery or flash.

Browse invalidation conservatively discards cached directory descendants under
the filesystem and quick-link roots, including aliases, while preserving root
and saved quick-link entries. Repopulation stays lazy: no source is activated or
automatically imported. This can collapse unrelated expanded Browse branches;
it avoids directory enumeration from completion-triggered model/view queries.
After lifecycle invalidation, uncached directories show provisional expansion
indicators until explicit expansion enumerates them and records whether they
have children. Model queries remain probe-free for the rest of that model's
lifetime; explicit expansion/context-menu refresh still performs its existing
directory work. This is tested with an attached offscreen Qt view and intercepted
filesystem probes, not a fully linked Library/sidebar runtime. Evidence is in
`deploy/recovery-20261109/gui-lazy-probes/receipt.json`; the preceding completion
fix is retained in `deploy/recovery-20261109/gui-refresh-fixes/receipt.json`.

### Read-only staged-image check

Use only an **explicit, unmounted, quiescent staged image directory**, never a
running host/Pi, card, mounted image, or directory another process can change:

```sh
python3 tools/performance/check-controlled-media.py --rootfs /explicit/staged/rootfs > qualification.json
```

The checker does not mount, extract, execute image code or mutate the rootfs.
Exit 1 means a concrete static failure; exit 2 means evidence remains unverified.
There is intentionally no successful whole-image qualification exit:
`actual_image_qualification` is always `UNVERIFIED`, `safe_to_eject` always false.
Per-file PASS means only that static check passed. A known-good fixture has no
static FAIL, not installed-image acceptance. Fixtures execute the existing stage
with synthetic chroot commands and root ownership, never real privilege changes.

Checks compare installed broker/inventory/CLI/unit/denial rule to current sources;
check capability files, code/config/socket parents, udisks mask, conditional
service enablement, aliases/drop-ins, pi primary/supplementary groups, shutdown-
only sudo drop-in, set-ID files, Linux capability/ACL xattr presence, statoverrides
and package path spellings, fstab, startup/automount hooks and namespace config.
Absolute symlinks resolve **inside** the staged root, including merged-/usr;
relative escapes, cycles, unreadable or special required files cannot pass.
Content reads refuse symlinked paths (including aliased parents) and multiply
linked policy files before reading or hashing their targets; these produce
UNVERIFIED evidence, not policy acceptance. Metadata-only helper checks still
resolve merged-/usr aliases inside the staged root. The checker does not request
shadow, private-key or runtime-token contents. Named capability probes, not a
directory listing, establish presence or confirmed absence. Missing, permission-
denied, unsafe, oversized and invalid-encoding evidence have distinct diagnostics.
This is not a race-safe live-filesystem boundary; quiescence is a prerequisite.

Additional units/aliases/drop-ins, polkit grants/defaults, sudo includes, startup
hooks and privileged helpers are concrete-path UNVERIFIED findings, not silently
allowed or edited. Real distributions will need review of these findings. The
polkit inventory orders rule basenames, `/etc` first on ties, but is not JavaScript
evaluation. Sudo is not parsed as a replacement for visudo/sudo. A resolved stripped
helper without the package's exact dpkg override spelling remains unverified for
future updates. No stage policy is silently changed to resolve these findings.

Optional `--build-receipt /external/build-receipt.json` compares `source_sha256`
(the exact emitted map) and `rootfs_evidence_sha256`, and requires `build_id` and
`image_sha256`. Mismatches report `STALE_OR_MISMATCHED`; absent evidence stays
UNVERIFIED. Matching is only `MATCHED_ATTESTATION_ONLY`, **not authenticated
provenance or a full image hash**. The fingerprint covers inventory metadata and
selected public code/policy reads, not secrets or all binary contents. Independently
verify archive digest, extraction lineage, owners/modes/xattrs and full linked
binary. Never manufacture provenance from a fixture report. macOS cannot qualify
Linux capability/ACL xattrs here; even Linux cannot prove earlier extraction
preserved absent attributes. Do not sudo/chown a lossy extraction to make it pass.

At this checkpoint there is no local `work/` tree or top-level `deploy/` image
archive. Retained packages/object receipts are not current image qualification.
`build.sh` uses `work/${IMG_NAME}/<stage>/rootfs` and export-stage rootfs directories;
CI uploads `deploy/*.zip` as `images-qemu`, separately from packages. No cloud
build or ARM compilation was started. Evidence is retained in
`deploy/recovery-20261109/offline-qualification/`.

### Finite remaining controlled-runtime qualification

Only after separate authorization in a disposable controlled Linux environment:

1. Verify full image/native package/source digests and extraction metadata on
   Linux; rerun offline checks and resolve every reported path. Independently
   review this checker and recovery proposal.
2. Use `systemctl cat`/`systemctl show` and loaded-state inventory to inspect the
   broker, all enabled privileged services, aliases/drop-ins, generators and
   transient units. Confirm ExecStart, root identity, both conditions, bounded
   capabilities, NoNewPrivileges and host-namespace settings. Audit D-Bus/udev,
   cron, automounters and custom services. Verify root/boot ancestry and absence
   of USB fstab/unmanaged mounts; arbitrary root code remains a trust assumption.
3. Validate sudo includes with `visudo -c` and effective `sudo -l -U pi`, plus
   `id pi`, Linux ACLs, `getcap -r`, set-ID helpers and exact package statoverrides.
   Verify updates preserve stripped modes. Do not print shadow hashes or keys.
4. Inspect loaded polkit rules/legacy grants in effective order; test udisks
   mount/unmount authorization as pi in active/inactive sessions on sacrificial
   identities. A preceding YES must not bypass denial; keywords are not evaluation.
5. Read effective `user.max_user_namespaces` and, where present,
   `kernel.unprivileged_userns_clone`; test namespace creation denial as pi.
   Compare PID1/broker/Mixxx/helper mount namespaces through restart/peer death.
   Verify `/run/mixpi-mount` and private user copy socket/lock ownership and inode
   continuity after boot/restart. Offline `/run` cannot establish runtime state.
6. Audit external writers/privileged administrators. Complete full-consumer native
   rebuild/link, GUI integration and separately authorized backed-up sacrificial-
   media tests: busy refusal, disconnect, cancellation cutoff, partial failure,
   quarantine and generation changes. Unknown outcomes never authorize removal.

### Proposed independent OFFLINE recovery — awaiting approval

This is a proposal, **not an established recovery route or execution approval**.
General pi sudo is removed, root locked and root SSH forbidden; normal SSH is
not independent administrative recovery. Do not activate the profile until the
user approves a feasible route and its prerequisites are verified. No new
privileged account, sudo grant, root SSH, password unlock or review gate is added.

Preferred proposal, aligned with SAME-CARD-UPGRADE's preservation gate:

1. Retain a verified known-good bootable recovery image on the Mac, with origin,
   digest, card-size compatibility and prior boot/recovery test evidence. An old
   package/source tree or checksum without bootability evidence is insufficient.
   This task establishes no such recovery image. Budget space for complete
   archives, the image and an optional full-card rollback copy.
2. Obtain a stop/backup window; quit Mixxx cleanly and confirm it and recording/
   copy jobs have exited. Preserve the complete `.mixxx` profile, SQLite plus
   WAL/SHM companions as a consistent stopped set, cues/playlists, mappings/
   settings, `~/Music`, `/media/SD-Backup`, both complete export trees and any
   additional recordings/music discovered. Preserve paths/symlinks; neither USB
   drive is a write target. Keep private configuration references outside Git.
3. Read back archives against source path/size/hash/symlink manifests and integrity-
   check a disposable copy of the backed-up SQLite database; verify cue/recording/
   settings coverage. Archive checksums alone are insufficient. Keep copies off
   the card; repeat final backups if work resumes. Never replace the existing
   verified backup with an unverified capture.
4. Only after explicit shutdown/handoff approval, power down cleanly and move the
   card to the Mac reader. Reidentify the physical card/capacity, never an old disk
   number. Keep both user USB drives detached from flashing. **No automatic erase
   or reflash.** A separate authorization must name the card, selected image,
   verified preservation evidence and irreversible write.
5. After that separately authorized write, boot the known-good image, verify
   identity/network/audio, keep Mixxx stopped and restore verified data at original
   paths. Preserve newly generated settings separately. Do not blindly restore
   old system policies/services/gates. Recheck hashes/SQLite integrity and obtain
   user verification of library, cues/playlists/settings/recordings before
   retiring any backup.

For in-place repair instead, first provide a tested Linux machine or Linux VM
with explicit reader passthrough, ext4 support and ownership/xattr-preserving
tools. **Do not assume native macOS ext4 access.** Initial inspection requires a
reviewed read-only/no-journal-replay strategy; filesystem repair/write needs
another authorization and verified backup. No mount/repair command is supplied
or executed here. Rehearse Linux/reader compatibility before relying on it.

If prerequisites cannot be met, the user choices are: approve preparation and
rehearsal of image-plus-data recovery; approve preparation of Linux/card-reader
in-place recovery; or defer controlled-profile activation. None is selected or
enacted automatically. Data archives are not bootable rollback; in-place repair
is not an independent backup.

Future reviewed-gate provisioning belongs to a **separate approved image-build
change**, bound to accepted source/image/recovery receipts. That change would
provision exact `v1\n` with root-owned non-writable parents, record independent
authorization provenance and undergo image/runtime qualification. This checker
does not create the gate; its shape alone never proves approval or safe eject.

This is implementation, not physical-eject acceptance. Do not install or enable
it on the running Pi. Independent security/safety review, a correctly rebuilt
and linked native binary, runtime checks, and explicitly authorized backed-up
sacrificial media are still required. Native EJECT now has a gated physical-disk
chooser and an application-owned asynchronous transaction coordinator. LOAD
offers controlled mounting followed by fresh manual volume selection. Dialog
closure retains pending operations; cancellation requires acknowledgement and
irreversible eject requires explicit commit plus `committing` acknowledgement.
Unknown/quarantined outcomes never permit removal. This code is not installed
in the running binary; no review gate or activation has been supplied.

## Fixed scope and trust

One fresh-image appliance account (`pi`), the host mount namespace, cooperative
same-UID programs, intact runtime directory/lock inodes, and trusted privileged
root administration. No hostile-root or general multi-namespace guarantee.
Only physical, non-system, non-stacked USB disks with partitions and kernel
vfat/exfat filesystems are mounted. The broker creates targets below
`/media/pi/mixpi-*`; labels never determine identity or paths. Internal library,
recording, backup, and settings locations are unchanged. Existing mounts are
never adopted. This is not a live migration of legacy label-based mountpoints.

Mount targets include a SHA-256 digest of the complete generation (including
boot identity) plus an atomically allocated unique suffix. Every attempt creates
a fresh root-owned directory; existing directories, symlinks and mounts are
never reused or adopted. Empty target directories are deliberately retained
after failure or unmount. Cleanup is offline administrator work only: verify
that a target is unmounted, root-owned and empty, then remove that directory
without recursive deletion. Retained directories cannot collide with a later
attempt, including after reboot.

The root-owned appliance profile, not an advisory lock, excludes competing
mount authorities. Its build recipe masks udisks2, denies its polkit actions,
disables the Sway/i3 udiskie launch, removes the appliance account's broad sudo
and disk-group access, and strips set-ID privileges from udevil, mount, umount,
fusermount, ntfs-3g and mount.cifs using persistent dpkg stat overrides. GVFS and
Nautilus receive no replacement mount grant. Unprivileged user namespaces are
disabled. Root services and administrators must not introduce another USB
lifecycle owner, grant file capabilities, change these policies or namespace
topology during operation. No other custom mount services/fstab USB entries
are supported. These are explicit reviewed-profile assumptions, not claims that
a scan proves exclusivity. Package/root policy changes require requalification.

## Source and future image wiring

`stage3/02-desktop/06-run.sh` installs the broker, service and CLI without
enabling anything by default. `MIXPI_CONTROLLED_MEDIA=1` builds the restricted
profile and enables the conditional unit in the image, but does **not** create
`/etc/mixpi/eject-reviewed`. Both capability files must be root-owned, unwritable
by other users and contain exactly `v1` followed by a newline. No tool here
creates the independent-review gate. Without it, the unit is skipped and the
CLI reports BLOCKED. Do not enable this image profile casually: it intentionally
removes general sudo and legacy automount convenience.

Separate pre-activation blocker: the profile removes `pi`'s broad sudo while
the root password is locked and root SSH is prohibited. An explicitly approved,
independent administrator/offline recovery procedure must exist before enabling
the profile. This change does not grant privileges, unlock root, create a review
gate or activate the profile.

The service deliberately stays in the initial host mount namespace. Its narrow
SOCK_SEQPACKET endpoint is `/run/mixpi-mount/control`; only the appliance UID is
admitted, with kernel SO_PEERCRED, SO_PEERPIDFD and matching namespace checks.
The server has bounded request sizes and connection counts, no caller paths,
commands, shell invocation, or arbitrary mount options. `list`, `mount`, `eject`,
`poll`, `commit`, and `cancel` operate on observed physical tokens. It serializes lifecycle
operations in one event loop. Normal kernel mount/unmount syscalls can block;
there is no forced timeout, signal-based unmount, lazy detach or kill fallback.

After future authorization, `mixpi-mount-control list` returns physical disk,
diskseq, token and volume descriptions. `mount TOKEN` explicitly mounts that
disk's partitions; there is no background auto-adoption or independent
automounter. `eject TOKEN` holds one authenticated connection while polling the
selected drain. Ctrl-C requests cancellation before the explicit commit cutoff;
only a `cancelled` reply acknowledges cancellation. A transport timeout is an
unknown outcome, not cancellation, and never interrupts a blocked kernel call. Native
LOAD remains a separate volume chooser with its existing duplicate-label
disambiguators. Labels are display data only.

## Transaction and failure behavior

The actual native CopyService now accepts root-only DRAIN, DRAIN_STATUS,
DRAIN_CANCEL and DRAIN_COMMIT messages. Non-root helpers retain the existing
BEGIN/CHECK/FINISH protocol unchanged. Root does not gain helper-copy admission
to a non-root native service. Broker/native peers are lifetime and namespace
bound. Native startup copy quarantine denies drains. Disconnect or broker death
retains drains; there is no timeout that silently reopens admission.

The non-root native service cannot stat a root peer's proc namespace link.
After kernel root credentials and the peer pidfd are validated, that trusted
root must send `NAMESPACE` with exactly one SCM_RIGHTS mount-namespace fd.
Native verifies nsfs namespace type and device/inode equality to its own mount
namespace, rechecks peer lifetime, closes the received fd and replies `OK`.
Missing, extra, truncated, wrong-type and different-namespace proofs fail closed;
all received descriptors are closed, including error paths. No drain is granted
before proof. Same-UID non-root BEGIN keeps the existing proc namespace check
and protocol. Mixxx remains non-root; root cannot use helper BEGIN against it.

The broker tracks only mounts it created in the current process. Before eject,
it validates the exact inventory token, physical generation and all relevant
mount IDs, partition devices, roots and paths. Unmanaged/duplicate/nested/bind
aliases, stacked devices, other-namespace USB mounts, resolved-path mismatch,
system ancestry ambiguity and stale/hotplug identity are refusals. Mount uses
a pinned block descriptor and BLKGETDISKSEQ to reject device-number reuse.

Drain closes admission for the physical generation while existing native/helper
leases finish. Unknown owners or target owners keep it busy. Before each normal
`umount2(target, 0)` it rechecks kernel topology, path identity, requester lifetime
and native idle. Completion requires every original mount to disappear, no
remaining partition mount, the same physical generation and native idle.
Only then does native COMMIT retire the generation. Retirement rejects known
old-generation admission but reopens unrelated unknown-operation admission.
The broker also bars remount of a retired generation. The completed active
transaction is removed, allowing unrelated disks to
mount while retirement tombstones and quarantined transactions remain intact.
The selection token is cleared
in the successful response; existing native identity checks invalidate stale
source/import resolutions. Native GUI success now requests Browse/Rekordbox
refresh without activating a source. Full linked model/import/cache behavior
remains unverified; synthetic coordinator/dialog tests do not establish it.

Preparation (`poll`) returns `busy` or `ready` without unmounting anything.
Cancellation queued during preparation can therefore be read and acknowledged
before any irreversible operation. The same authenticated connection must send
`commit` after `ready`; the broker returns `committing, cancellable=false` and
does no unmount in that request. That accepted commit is the cancellation cutoff.
Only a subsequent `poll` executes unmounts after fresh validation. Cancellation
after cutoff returns `too-late`, never reopens admission, and need not interrupt
an in-flight syscall. The CLI reads each outstanding reply before sending cancel,
prints the cutoff acknowledgement, and never labels a timeout as cancellation.

Pre-cutoff cancellation releases only an unchanged transaction belonging to the
same connection and exact token. Peer crash/disconnect, stale identity and native service loss retain
protection. Any attempted unmount failure, failed verification or partial
multi-partition completion is conservatively quarantined, with the exact
verified removed subset and `safe=false`; it cannot be cancelled into reopened
admission. A broker restart cannot adopt remaining mounts. Recovery is an
administrator-reviewed later operation, not automatic force-unmount/remount.

## Validation contract and remaining gates

`tests/test_media_broker.py` exercises production Broker methods with an explicit
FakeOS injection; all successful unmounts there are **synthetic**, never physical
acceptance. It separately checks the libc boundary uses only zero flags, actual
C++ registry retirement, real Linux root/non-root credential/pidfd transport,
broker death, and Python broker/native transport together with synthetic mounts.
Existing copy tests retain the admitted-recording move/drain regression.

Use the existing full host command with `MIXXX_TEST_SOURCE` and
`PIONEERED_TEST_SKIN`. Linux transport tests run only in dedicated `/home/pi`
scratch; the root variants exercise scratch sockets/processes, never the root
daemon or real mount/unmount. Evidence hashes bind the shipping patch and owned
files. The affected `library/library.cpp` object is generated from current
shipping patches and built with the established ARM flags/header overlays;
dependency hashes and the exact command are retained. No unchanged 22-unit
rebuild or full-link claim is made. Registry header consumers must all be
rebuilt consistently before final linking.

Remaining finite work: independent GUI review; approve and prepare independent
recovery; validate the complete fresh-image policy against its actual installed
services and privileges; full native consumer rebuild/link;
fresh-image runtime qualification including namespace/restart races; then a
separately authorized sacrificial-media physical test. Default-disabled UI alone
does not satisfy operational-eject acceptance. Audio, sampler and focus-loop
behavior are outside this change and remain untouched.
