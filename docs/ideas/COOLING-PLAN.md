# Cooling plan for the DJ box

Researched **2026-11-08**. Read-only: nothing on the Pi changed for cooling. The
model is [`tools/cooling-model/index.html`](../../tools/cooling-model/index.html);
open it in a browser. **Unconfirmed** marks anything not measured.

## Where things stand

- **Box, measured by the user:** 235 mm wide, 152 mm deep, 100 mm tall at the
  back (hinged, high) wall and 57 mm at the front. The two heights put the
  screen face at about 16°; the user's eyeball estimate was 20°. It is a
  cardboard glassware box ("6PCS DIAMONDS"). The Pi hangs under the slant near
  the back edge, with its components facing in. The USB hub lies on the floor.
  The only openings are a few cable holes. The Pi's position under the slant is
  estimated from a photo: centre about 65 mm from the back edge (**Unconfirmed**).
- **Fan 1:** 30 mm, 5 V, 2-wire, with a single 2-pin Dupont housing. It sits in
  a perforated Pi 4 case lid. Its current is **Unconfirmed**; typical is 0.1 A.
- **Fan 2:** 60 mm, 24 mm thick, labelled 12 V 0.22 A, 2-wire, with a white
  2-pin housing of unknown pitch. Its airflow and noise are **Unconfirmed**; the
  model uses typical 60 × 25 mm figures at that current.
- **Masking tape:** removed by the user on 2026-11-08. It had protected the
  board before the Pi went into the box.
- **Display power:** the display uses "the main two pins" of the header, taken
  here as pin 4 (5 V) and pin 6 (GND). Software can't see which header power
  pins a lead sits on, so which 5 V pin it uses is **Unconfirmed**.
- **Header:** every GPIO is free. There is no fan overlay in `config.txt`. The
  `gpio-fan` overlay is installed and takes `gpiopin`, `temp` and `hyst`.
  GPIO12 idles low with a pull-down.

## Measured temperatures and loads

| Time (2026-11-08) | State | SoC | CPU busy (four cores) |
| --- | --- | --- | --- |
| 13:02 | Box closed, idle, software GL, tape on | 66.2–67.6 °C | 7 % |
| about 13:10–13:35 | GPU tests, two decks from SD, 30–60 s each | software GL up to 69.1 °C, V3D up to 64.3 °C | software GL 34.5–41 %, V3D 12 %; idle with V3D 5.3 % |
| 13:37 and 14:06 | Idle, V3D, box state **Unconfirmed** | 61.8–63.3 °C | 4–6 % |
| 2026-09-22 | Two decks plus SSH backup, about 3 minutes, probably boxed | peak 76.4 °C | n/a |

The GPU test runs are in [`deploy/gpu-test-20261108/`](../../deploy/gpu-test-20261108/).
Since that test, the live Pi draws Mixxx on the V3D GPU (see
[`PERFORMANCE-PLAN.md`](PERFORMANCE-PLAN.md)). The image build still uses
software GL.

## What the model says

The model has three temperatures: chip, box air and room. It includes an
airflow solver for vent holes, leaks and fan curves. It is calibrated to the
13:02 reading: sealed box, software GL, tape on, room at 25 °C (the user's
default). Each range comes from 32 re-runs that spread every assumption and
re-calibrate each time. As a cross-check, 3 minutes of two decks plus a backup
on software GL comes to 74.8 °C in the model; September measured 76.4 °C.

The table gives the SoC temperature in °C with the room at 25 °C. The layouts
assume the tape is off and the hub is inside.

| Layout | Idle, V3D | Two decks, V3D | Two decks + copy, V3D | Two decks, software GL |
| --- | --- | --- | --- | --- |
| Sealed box (now) | 66 | 73 (72–77) | **80** (80–86) | 78 (77–80) |
| Passive vents: 10 × Ø12 mm low front and high back | 63 | 70 (68–74) | 76 (75–82) | 74 (72–78) |
| 30 mm fan on the heatsink, box still sealed | 57 | 62 (57–65) | 67 (62–71) | 65 (60–69) |
| 60 mm exhaust high on the back, holes low front | 46 | 50 (46–53) | 54 (50–58) | 52 (48–55) |
| Both fans: heatsink fan + 60 mm exhaust | 41 | 44 (41–47) | 47 (44–51) | 46 (43–48) |
| **Intake at the Pi:** 60 mm blowing in on 9 V, 30 mm fan as backup | 38 | **40** (38–43) | 43 (40–47) | 42 (39–45) |
| Same, 60 mm fan on 12 V | 37 | 39 (37–42) | 41 (39–45) | 41 (38–43) |
| Same, if the 60 mm fan stops | 51 | 55 (51–57) | 59 (55–63) | 57 (54–60) |
| Printed case: intake at the Pi, hub outside | 38 | 40 (38–43) | 43 (40–46) | 42 (39–44) |

A room at 30 °C adds about 5 K to every figure: the sealed box would reach
78 °C at two decks and 85 °C with a copy.

- **Since the GPU fix, the sealed box is marginal rather than broken.** Two
  decks sit near the 75 °C target. Two decks plus a copy, or a warm room, reach
  the 80 °C throttle point.
- **The still-air heatsink is the bottleneck.** Most of the rise sits between
  the heatsink and the box air, because the board faces downwards under the
  slant. Vent holes alone gain about 3 K.
- **A fan on the heatsink inside a sealed box is not a fix.** It cools the chip
  about 11 K. The box air still has to lose every watt through the cardboard, so
  it rises from 41 °C to 46 °C.
- **Moving air through the box brings the box air to within 1 K of the room.**
  Aiming the incoming jet at the Pi beats pulling air out beside it (40 °C
  against 50 °C). An exhaust only draws air from close to the fan, while an
  intake jet reaches the heatsink.
- **Aim matters.** The intake has to line up with the SoC heatsink; moving it
  30 mm sideways costs about 2 K.
- **Use 9 V, not 12 V.** At 9 V the 60 mm fan is about 1 K warmer, but it is
  about 7 dB quieter (30 against 37 dBA). It also draws 0.32 A from a hub port
  instead of 0.64 A, which is more than a USB 2 port gives.
- **The 30 mm fan adds under 1 K beside the aimed intake.** It is worth fitting
  as a backup: if the 60 mm fan stops, the model holds 55–59 °C instead of
  73–80 °C.
- **Idle may run hot in the model.** After the GPU fix and tape removal, the
  model expects about 66 °C at idle; 13:37 and 14:06 read 62–63 °C. If the box
  was closed then, the model runs about 4 K hot, so read it as conservative. A
  closed-box idle reading would settle this and allow re-calibration.

## Placement: the cardboard box now

1. **Mount the 60 mm fan as an intake on the outside of the back (hinged) wall,
   aimed at the SoC heatsink.**
   - Close the lid and mark where the SoC heatsink sits from left to right. Its
     centre should be about 67 mm above the floor; check the real height with
     the lid shut.
   - Cut a 57 mm round hole there and mount the fan on the **outside** of the
     wall. Mounted inside, its 24 mm frame would hit the slanted lid, which is
     only about 93 mm high that far in.
   - Put the **label towards the box**: air leaves the label side.
   - Bolt it through the 50 mm-spaced corner holes with M3 × 35 mm screws, nuts
     and washers, with a 60 mm wire finger guard on the outside.
   - Leave at least 5 cm free behind the box for the air to come in.
2. **Outlet:** about 20 cm² low on the front wall. That is two rows of six Ø15 mm
   holes with centres 15 mm and 35 mm above the floor, or one 100 × 20 mm slot
   10 mm up. The existing cable holes act as extra outlets.
3. **Fit the 30 mm fan on the SoC heatsink as the backup, with the case lid as a
   bracket.**
   - The Pi is screwed to the display on standoffs. Add M2.5 male-female
     standoffs on the Pi side, as long as the tallest heatsink plus a 5–10 mm
     gap plus the 7 mm fan (likely 20–25 mm). Screw the lid to them.
   - Point the fan at the heatsink and offset it about 5 mm so its hub doesn't
     shadow the SoC. It blows onto the heatsink, label towards the board.
   - If the lid's holes don't match the Pi's 58 × 49 mm pattern, take the fan
     out and fix it to two standoffs through its corner holes.
4. **Exhaust alternative:** the same 60 mm fan works blowing out, mounted the
   same way: 50 °C alone, 44 °C with the heatsink fan. It pulls less dust onto
   the Pi.
5. **The hub can stay inside** while the fan runs; it costs under 0.5 K.
6. **Check the hi-fi unit.** If the Sony unit under the box vents through its
   top, stand the box on 10 mm feet so both can breathe (**Unconfirmed**).

## Placement: the printed case (later)

- **Footprint:** keep 235 × 152 mm, 100 mm at the back and 57 mm at the front.
  This screen and slant already work.
- **Air path:** a 60 mm intake on the back wall, centred on the SoC heatsink,
  with a printed finger guard. An outlet grille low on the front with at least
  25 cm² of open area, so slots rather than holes. Put the fan on the outside, or
  give it a pocket, because a 25 mm fan inside hits the slant.
- **Pi mounting:** keep the heatsink side in the jet, with at least 10 mm
  between the heatsink tips and any wall. Keep the 30 mm fan on the heatsink as
  the backup; its screw holes are 24 mm apart.
- **Hub:** put it outside or in its own compartment. Bring cables through snug
  grommets, so the air leaves through the grille and not the cable gaps.
- **Material:** print in PETG or ASA. PLA softens at about 55–60 °C, which the
  area around the Pi reaches if a fan fails.
- **Model result:** 40 °C (38–43) for two decks on V3D, the same as the
  cardboard box with an aimed intake. A case doesn't cool better by itself; the
  air path does the work.

## Wiring

### Header pins (display assumed on 4 and 6)

```
            odd  │ even (board edge)
     3V3     1 ● │ ● 2   5V    ← fan 1 red
   GPIO2     3 ● │ ● 4   5V    ← display 5 V ("the main two pins")
   GPIO3     5 ● │ ● 6   GND   ← display GND
   GPIO4     7 ● │ ● 8   GPIO14
     GND     9 ● │ ● 10  GPIO15
  GPIO17    11 ● │ ● 12  GPIO18
  GPIO27    13 ● │ ● 14  GND   ← fan 1 black
     ...         │       ...
   GPIO6    31 ● │ ● 32  GPIO12 ← switch signal, through 1 kΩ (optional)
  GPIO13    33 ● │ ● 34  GND    ← switch emitter (optional)
```

Pin 1 has the square pad, at the end nearest the SD card. If the display is
actually on pins 2 and 6, swap: fan red goes to pin 4.

### 30 mm fan, always on (no soldering)

- Pins 4 and 6 are the only neighbouring 5 V/GND pair, and the display has
  them. Its leads are fixed (user, 2026-11-08). So push two
  **male-to-female jumpers** into the fan's 2-pin plug. Red goes to whichever
  of **pins 2 and 4** the display leaves free (5 V), and black to **pin 14**
  (GND); pin 9 also works.
- **Without jumpers:** de-pin only the **fan's** plug after disconnecting all
  power, including the powered hub. Identify the retention mechanism first:
  gently lift a plastic housing latch, or depress a metal contact tang, then
  withdraw the contact toward the wire. Do not force it. Prefer separate
  locking 1-pin housings; individually heat-shrunk contacts are temporary and
  need strain relief. Do not rely on tape alone for gig use. Leave the socket
  opening clear and cover all outer metal. Confirm the screen's actual pins
  before using the free 5 V pin and ground pin 14.
  The illustrated [build manual](../../tools/cooling-model/index.html#build)
  separates this wiring task from the later mounting changes.
- **Or:** cut the plug off and solder the fan to an old
  USB-A cable, red to red and black to black. Insulate the joints with
  heat-shrink or tape and plug it into a hub port. The fan then stays off the
  header and the Pi's supply.
- About 0.12 A. The Pi's 5 V supply then carries about 1.2 A at two decks:
  board, display (0.35 A, **Unconfirmed**) and fan.

### 30 mm fan, temperature-switched (optional)

```
 5 V (pin 2) ──────┬────────────┐
                   red          │
                  [FAN]        ─┴─  diode, band to +5 V
                   black       ─▲─  (1N4148, 1N400x or 1N5819)
                   ├────────────┘
                   │ C
 GPIO12 (pin 32) ─[1 kΩ]─ B  NPN: BC337, 2N2222 or S8050
                   │ E
 GND (pin 34) ─────┘
```

- **Build:** solder it on a small piece of perfboard with a 2-pin male header
  for the fan plug. Run three female jumper leads to pins 2, 32 and 34.
- **Config:** add `dtoverlay=gpio-fan,gpiopin=12,temp=60000,hyst=10000` under
  `[all]` in `/boot/firmware/config.txt`, then reboot. Ask before this is
  changed on the Pi.
- **Behaviour:** with the 60 mm intake running, the model never takes the SoC to
  60 °C, so the small fan stays silent. If the big fan stops, the small fan
  starts at 60 °C.
- **Safe at boot:** GPIO12 idles low, so the fan is off until the overlay loads.

### 60 mm fan (12 V, 0.22 A)

- Plug a **USB 5→9 V boost cable** into a **hub** port, using a 5.5 × 2.1 mm
  barrel plug. A **barrel-to-screw-terminal adapter** joins it to the fan.
- Cut the fan's white plug off, strip about 5 mm, and screw the wires in: red
  to +, black to −. That sidesteps the unknown plug pitch and needs no
  soldering.
- It draws about 0.32 A from the hub port and nothing from the Pi.
- A 12 V boost cable runs it 1 K cooler, but louder and at 0.64 A. Use a USB 3
  or charging port for that.
- On plain 5 V it rarely starts. The model then counts it as a 60 mm hole in
  the wall.

## Parts to order

The user has a soldering kit; everything else is needed.

| Part | Qty | For | Notes |
| --- | --- | --- | --- |
| USB-A 5 V → 9 V step-up cable, 5.5 × 2.1 mm plug, ≥ 0.5 A | 1 | 60 mm fan | A 12 V version works too: about 1 K cooler, louder |
| 5.5 × 2.1 mm female barrel to 2-pin screw terminal adapter | 1–2 | 60 mm fan | Check the cable's plug size matches |
| 60 mm wire fan guard | 1 | 60 mm fan | Outside the back wall |
| M3 × 35 mm screws, nuts and washers | 4 + spares | 60 mm fan | 24 mm fan + cardboard + guard |
| Dupont jumper wires, male-to-female and female-to-female, 10–20 cm | 1 pack each | 30 mm fan, switch board | |
| M2.5 standoff kit (male-female, 5–25 mm) with screws and nuts | 1 | Case lid over the heatsink | Brass or nylon |
| Heat-shrink assortment | 1 | Joints | Skip if the soldering kit has some |
| *Optional:* NPN transistors BC337, 2N2222 or S8050 | 5 | Switched backup | One is used |
| *Optional:* diodes 1N4148, 1N4001 or 1N5819 | 5 | Switched backup | |
| *Optional:* 1 kΩ resistors | 10 | Switched backup | |
| *Optional:* small perfboard and 2.54 mm male pin headers | 1 | Switched backup | |
| *Optional:* stick-on thermal pads | 1 pack | Heatsinks | Only if one came loose with the tape |

### Where to buy in Kenya (checked 2026-11-08)

Prices are online listing snapshots. Check stock before going.

- **Jumpers:** a mixed 20 cm pack (male-male, male-female, female-female)
  covers the 30 mm fan now and the switched board later.
  - [Nerokas](https://store.nerokas.co.ke/SKU-2908) has a 60-piece assorted
    pack; its 40-piece male-female set is KES 150, with stock shown
    inconsistently.
  - [Arduino Solutions Kenya](https://arduino.co.ke/product/dupont-line-10cm-20cm-30cm-male-to-malefemale-to-male-female-to-female-jumper-wire-dupont-cable-for-arduino-diy-kit/)
    lists mixed sets at KSh 100–300.
  - [Jumia](https://www.jumia.co.ke/generic-40pcs-20cm-male-to-female-jumper-wires-dupont-cable-for-arduino-58726189.html)
    lists 40 male-female jumpers at KSh 480, with CBD delivery from KSh 70.
  - Walk-in: component shops on Luthuli Avenue, such as Universaltech
    Electronics (Nyanza House, +254 701 059919). Their stock is **Unconfirmed**.
- **Boost cable:** Jumia lists a
  [USB 5/9/12 V boost cable](https://www.jumia.co.ke/generic-usb-to-5v-9v-or-12v-power-boost-cable-326528440.html)
  at KSh 950. Set it to 9 V and check that the plug is 5.5 × 2.1 mm. Kilimall's
  listing uses a 3.5 × 1.35 mm plug.

## Before/after test

Use the same two tracks, keylock on as at a gig, the box closed, and the room
within 1 °C of the first run. Note the room temperature from a thermometer next
to the box. The before run uses today's live setup: sealed box, V3D. The model
expects 73 °C (72–77).

1. **Idle check (no new parts needed):** close the box, leave Mixxx open and
   idle for 15 minutes, and read `vcgencmd measure_temp`. Enter it under
   **Calibration** in the model as a V3D, tape-off reading.
2. **Before (sealed):** start the logger and two-deck playback together:

   ```sh
   mkdir -p deploy/cooling-YYYYMMDD
   ssh -4 -o BatchMode=yes -i ~/.ssh/mixpi_ed25519 -o HostKeyAlias=mixxxpi.local \
     pi@192.168.68.56 'bash -s -- 1800 10' < tools/cooling-model/log-temps.sh \
     > deploy/cooling-YYYYMMDD/before-sealed.csv
   ```

   The logger samples `vcgencmd measure_temp`, `get_throttled`, the ARM clock,
   load and CPU use every 10 s for 30 minutes. It prints a summary at the end.
   Nothing is written on the Pi. If Wi-Fi drops, rerun rather than splice logs.
3. **Fit the fans** as above.
4. **After:** repeat with the same tracks into `after-intake.csv`. The model
   expects 40 °C (38–43).
5. **Optional:** flip the 60 mm fan and run a third test as an exhaust
   (`after-exhaust.csv`). The model expects about 10 K warmer.
6. **Compare:** drop the CSVs onto the model page's 30-minute chart to compare
   them with the prediction.
7. **Pass:** a peak under 75 °C, throttle flags `0x0` across every sample, and
   no dropouts heard.

### Where the results go

- **[`HARDWARE.md`](../setup/HARDWARE.md#cooling-test-log):** one row per run in
  the cooling test log, with date, layout, room temperature, peak, last-10-minute
  mean, throttle flags and the CSV path.
- **[`JOURNAL.md`](../JOURNAL.md):** a bullet under that day. Say what was
  fitted, give the before and after peaks with the room temperature, and link
  here. Mark anything inferred as **Unconfirmed**.
- **Master overview:** update it once the fans are in.

## Open questions

- A header photo, to settle which 5 V pin the display uses.
- The SoC heatsink's height above the box floor with the lid shut, and its
  left–right position. These fix the fan hole.
- A closed-box idle reading with V3D and the tape off.
