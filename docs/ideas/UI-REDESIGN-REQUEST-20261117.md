# MixPi UI redesign: owner request, 2026-11-17

Status: request recorded. A new thread makes the prototype and the plan, using the process at the end of this file. Nothing here is designed or approved yet.

The owner took photos of the test card (build 2 plus the round-1 repairs that were not yet built) and commented on each. The photos are in [ui-redesign-20261117/](ui-redesign-20261117/). The photos are rotated 90°, because the screen is 800×480 landscape.

## Owner comments (verbatim)

### Eject and media control: `IMG_0316-eject-controlled-dialog.jpg`
> Eject and the media controls need a revisit. I wanted it to work like a pioneer dj where you choose when the program can access the files and choose when to eject and keep the last playong/loaded song in storage for handover (get's cleaned out after transition out)

### Load / Eject dialog: `IMG_0315-load-eject-dialog.jpg`
> revisit and redesign the load and eject put some refrences (https://grasp.study/courses/5ae77ebf-30c9-46ad-b8c7-b01fa3608a3b/modules/5325369d-de2c-40a6-9a0d-32d7807e7e03/lessons/f9c54154-52eb-49a6-82a1-ccdbe59fb65c - load is usually automatic actually - eject is what is done safely)

### Tracks with LOAD TO pads: `IMG_0314-tracks-load-to-pads.jpg`
> The samples need to have a full length menu you can cover the song tracks,also let's have a single load button that then goes into a choose pad

### Computer source and sampler loading: `IMG_0313-computer-sources-sampler.jpg`
> same sample is nearly impossible to select, let's redesign that to be more useable (not eveything needs to be seen when putting in samples, Im down to go back to a similar to the OG sampler that had eight just slightly larger then the load opens a browse menu where you select from library and load to a deck, a separate component from the browse list but similar)

### Sources menu: `IMG_0311-sources-menu.jpg`
> I think we need to completley revisit the design of this as well, Make it better and easier to navigate, when in these bigger menus we can cover the whole screen because its deeper context not just quick and easy. Also the action menu button on tracks should just be a pen icon and the the show should be a hamburger menu that turns into an x when it's open

### Library scan bar: `IMG_0310-scan-bar.jpg`
> The scan bar can be improved it was messy and it covered the quick actions, let's just show the final file / in the filename instead of the entire path, in the list then have a hide and cancel. With the hide it is okay that it covers but if it is hidden save that setting and put a USB icon with the % of it loading that is done.

### Overall direction
> Similar to what we did in this thread mcp:launch:fcb4ac5beff2279fbedea5dbf90c58f874bbe0f9671f40ad282f4010e633472c please update the design in an artifact with a full re-creation of the UI in that, have Fable 5.2 review the code the current screenshots and the comments then write a plan, have opus 5.5 xhigh orchestrate then have upto 3 builders in opus 5.5 med then the counsel with the Opus and Fable and Sol reivewers. Get us to a 9. This is your codebase, lets modernize while keeping the inspiration from the work we have already done. ++ here are some exsisting pro DJ screenshots, I like our layout but see how in a modernized and clean way we can take inspo from them (Just remeber most things should still work with touch and at least the starlight) https://downloads.support.alphatheta.com/manuals/all-in-one-dj-systems/XDJ-AZ/XDJ-AZ_DRI1936C_manual_EN.pdf this is a similar single screen system but has much more controls than we have now around the screen so account for that fact.

> Commit this then do this in a new thread. Once the plan is done, give me a list of all the questions clear and consise in the chat (please include annotated screenshots to direct me better)

### Saving settings
On "pulling the power cable can never save anything, because Mixxx saves settings only on quit":
> We control the codebase, why can't we just save on settings change?

Orchestrator answer: yes. A patch can save `mixxx.cfg` and the sampler bank shortly after each change (debounced, written atomically). A power pull then loses at most the last second. This is now a requirement of the redesign: see C-3.

## References
- AlphaTheta XDJ-AZ manual: https://downloads.support.alphatheta.com/manuals/all-in-one-dj-systems/XDJ-AZ/XDJ-AZ_DRI1936C_manual_EN.pdf. It is a single-screen system like MixPi, but it has many more hardware controls around the screen. MixPi has only the touch screen and a Hercules DJControl Starlight, so the screen has to carry more.
- grasp.study lesson on load and eject, linked above. It may need a login. If it cannot be read, use the XDJ-AZ manual's media sections and ask the owner.
- Prior process: the DiggaOS redesign. Its prototype artifact, Fable plan and climb thread are linked from thread mcp:launch:fcb4ac5beff2279fbedea5dbf90c58f874bbe0f9671f40ad282f4010e633472c.

## Carried in from the field-fix climb (tuner record `mixpi-field-fixes-20261116`)
State at hand-over: branch `feat/pi-performance-target`. The test card runs build 2 (`ac18cb2`), installed in place. Build 3 was not run.

- **C-1. Round-1 repairs, committed but not yet built (`053c618`, `mixxx-council-fixes.patch`):**
  - F-10: plain wording with a drive selected;
  - F-6: a drag cancels the tap;
  - F-5: a saved "both times" mode shows elapsed;
  - F-9: a row tap toggles, and a checked box shows a tick.
  - Native gate 128/128. Evidence: `deploy/recovery-20261116-fixes/build3-fixes/`.
- **C-2. Held owner options:** local branch `prep/owner-options-20261117` (not pushed). Two commits, each can be cherry-picked alone.
  - `a8a86fa` clean quit on SIGTERM (`mixxx-clean-quit.patch`, plus service stop timeouts).
  - `72e98c4` `udiskie --no-notify`.
  - Native gate 135/135. Evidence: `deploy/recovery-20261116-fixes/owner-options/`.
  - The owner has not decided on the pop-ups yet. The redesign's USB icon with a % may replace them.
- **C-3. Save on change** (owner request above). Save the config and the sampler bank on change, so a power pull keeps them. This sits beside C-2's clean quit. A reboot or power-off also has to stop Mixxx before the session ends: today the session closes first.
- **C-4. Council round 1** (Opus 8, Fable 8, Sol 6). Reports: `deploy/recovery-20261116-fixes/council/round1-*.md`. Still open:
  - F-10 on the Pi with a drive. The owner's photos `IMG_0315`/`IMG_0316` now show it on build 2. The controlled dialog shows a "Prepare selected disk" button: check what it does with controlled media OFF.
  - A tracked results file (F-15 step 8).
  - A one-time sway crash after a USB storm.
- **C-5. Owner checks:**
  - The card's saved routing is mono, with Master on ch 1 and Headphones on ch 2. EOS used Master 1–2 and Headphones 3–4.
  - MANTACORE has a loose USB connection.
  - DJ-003, writing Pi cues, loops and history back to Rekordbox, is in the backlog (`docs/ideas/DJ-LIBRARY-TOOLS.md`).
  - USB drives stay read-write (owner decision).

## Process the owner asked for
1. Make a full re-creation of the current MixPi UI at 800×480 as an interactive HTML artifact, then the redesigned version. Modern and clean, keeping the current layout's spirit, touch-first, and working with the Starlight.
2. Claude Fable 5.2 reviews the code, the current screenshots, these comments and the references, then writes the plan. Bigger, sweeping changes come first.
3. The orchestrator (Claude Opus 5.5 xhigh) gives the owner one clear, short list of questions in chat, with annotated screenshots. Then it waits for answers.
4. After the owner says go: up to 3 builders (Claude Opus 5.5 medium) at once, with no overlapping files. Then the council: Claude Opus 5.5 xhigh, Claude Fable 5.2 high, GPT-6.1 Sol xhigh. Target: all three at 9 or more.
