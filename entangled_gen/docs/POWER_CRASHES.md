# THE MACHINE HARD-POWERS-OFF UNDER GPU LOAD

Written 2026-08-10 after four crashes in one day, three of them during a
slicevote run. This is the debugging file — read it before spending time on
"why did the run die again".

**The one-line version: lock the GPU clocks before any long run. The lock does
not survive a reboot, so re-apply it every time.**

```
nvidia-smi -lgc 0,1500    # needs an ADMIN shell
```

⚠ **Use `-lgc`, not `-pl`.** The power-limit knob (`nvidia-smi -pl`) is
**OEM-locked on this machine** — it fails with "not supported in current
scope", verified 2026-08-06. Confusingly, `nvidia-smi -q -d POWER` still
reports a settable-looking range (min 5 W / max 175 W); that is the hardware's
range, not permission to write it. The clock lock is the knob that works here,
and capping clocks caps power indirectly.

---

## 1. THE SYMPTOM, AND HOW TO TELL IT APART FROM A NORMAL CRASH

The machine switches off instantly. No blue screen, no minidump, no shutdown
sound. It is a power loss, not a software fault.

How to confirm it was this and not something else:

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents 5 |
  ForEach-Object { "$($_.TimeCreated)  BugcheckCode=$($_.Properties[1].Value)" }
```

- `BugcheckCode=0` **and no file in `C:\WINDOWS\Minidump`** → this problem.
  The machine lost power mid-instruction and had no chance to write anything.
- `BugcheckCode` non-zero with a minidump → a *different* problem (a real
  driver/kernel fault). Do not apply this file's conclusions to that.

Both kinds happened on 2026-08-10, so check which one you have before assuming.

## 2. WHAT HAPPENED ON 2026-08-10

Four unclean shutdowns:

| Time | Kind | Notes |
|---|---|---|
| ~16:20 | bugcheck `0x19C` (power watchdog) | dump written — the odd one out |
| ~18:39 | power loss, `BugcheckCode=0` | no dump |
| ~21:37 | power loss, `BugcheckCode=0` | no dump |
| ~21:57 | power loss, `BugcheckCode=0` | killed the full vote run 2 min in |

The 21:57 one died mid-`[wslrender]` on `obj_010`, about two minutes into
`run r20260810-215503` (`run_kind=full`, 46 nodes). The pattern across the day
is: it dies during GPU work, not while idle.

## 3. WHAT WE MEASURED (rather than guessed)

### GPU power draw during an actual vote render

One-object run (`slicevote.py --scene living_marble --only obj_010`), 48
seconds, logged at 1 Hz:

| | |
|---|---|
| **Peak draw** | **139.99 W** |
| Mean draw | 26.7 W |
| Peak temperature | 71 °C |
| Peak utilisation | 80 % |
| Battery discharge during bursts | 0 (adapter carried it) |

The shape is the important part: **the workload is nearly idle on average and
spikes hard for a second at a time.** Mean 27 W, peak 140 W. It is the spikes
that kill the machine, not sustained heat — the card never got hot.

This is also why the clock lock costs almost nothing in wall-clock time. It
only bites during the handful of seconds that actually reach the ceiling; the
other 90 % of the run is nowhere near it.

### The power limit as shipped

```
Current Power Limit : 159.55 W     <- what was enforced, floating
Default Power Limit : 150.00 W
Max Power Limit     : 175.00 W
Min Power Limit     : 5.00 W
```

The enforced limit sits *above* the 150 W default and is a non-round number,
which is Dynamic Boost moving it around — a stock NVIDIA laptop feature that
shifts power budget between CPU and GPU. Nothing is overclocked or modified.
The feature is normal; this machine just can't sustain it any more.

### Battery health — the most suspicious finding

`powercfg /batteryreport`:

| | |
|---|---|
| Design capacity | 90,005 mWh |
| Full charge capacity | 69,260 mWh |
| **Health** | **77 %** |
| **Cycle count** | **78** |

**77 % health at 78 cycles is abnormal.** At that cycle count you would expect
95 %+. The pack has aged far beyond what its use explains.

Why it matters here: the CPU (Ryzen 9 7945HX) and GPU (RTX 4080 laptop, 175 W)
can together demand more than the adapter supplies for brief moments, and the
**battery is designed to cover that gap**. A degraded cell has higher internal
resistance and is worse at delivering a sudden burst. If it can't ramp fast
enough, the rail collapses and the machine drops instantly — which is exactly
the no-bugcheck, no-dump signature we see.

This is a hypothesis that fits all the evidence. It is **not confirmed**.

## 4. WHAT IS RULED OUT, AND WHAT ISN'T

**Not heat.** Peak 71 °C under the load that has been killing it. Nowhere near
throttling, let alone shutdown.

**Probably not the power strip / mains.** Windows logged **zero** Kernel-Power
105 events (AC↔battery transitions) in the 24 h covering all four crashes. If
the strip cut or sagged, the laptop would switch to battery, log the
transition, and *keep running*. It didn't switch and it didn't survive.

To check this yourself after a future crash:

```powershell
Get-WinEvent -FilterHashtable @{LogName='System';
  ProviderName='Microsoft-Windows-Kernel-Power'; Id=105;
  StartTime=(Get-Date).AddHours(-24)}
```

The strip is not fully cleared, though: a sag plus a battery that can't take
over could still produce an instant off with nothing logged. **Untested as of
writing — plug straight into a wall outlet and see.** It costs nothing.

**Still open:** the AC adapter itself. A weakening 330 W brick produces the
same symptom as a weak battery. Testing it needs a known-good spare.

## 5. THE MITIGATIONS, IN ORDER OF WORTH

### a) Lock the GPU clocks — do this before every long run

```
nvidia-smi -lgc 0,1500        # admin shell; nvidia-smi -rgc removes it
```

**This is the verified fix** (2026-08-06). Under the lock, a full 20-view
GroundingDINO+SAM batch that had been crashing ran clean: clocks pinned
≤1500 MHz, **peak 93.8 W against the ~190 W transients seen before**, busy
average 45 W, 65 °C max. Speed cost was negligible for that workload.

**Verifying it took is not obvious.** `nvidia-smi` does NOT report an applied
`-lgc` back in any plain field — `clocks.max.sm` and `-q -d CLOCK`'s "Max
Clocks" both keep reporting the hardware maximum (3105 MHz) whether the lock is
on or not. Do not read that as the lock having failed.

Two things that DO tell you:

1. The command's own output at apply time:
   `GPU clocks set to "(gpuClkMin 0, gpuClkMax 1500)"` — that is the receipt.
2. Empirically, under load: `clocks.sm` in `gpu_watch.csv` must stay ≤1500.
   Unlocked, a vote run hits 2280–2400 MHz. If the log shows clocks above
   1500 during a burst, the lock is NOT in force.

`nvidia-smi -pl 120` is the more obvious knob and **does not work on this
laptop** — OEM-locked, "not supported in current scope". Don't burn time on it.

**Windows has no persistence mode, so the lock is lost on reboot and can be
lost on a driver reload.** Since the failure *is* a reboot, a crash always
drops the lock — re-apply before every retry, or the retry runs unprotected.

A clock lock cannot damage anything. It only makes the card slower.

### b) Take the CPU out of Turbo

Armoury Crate → **Silent** or **Performance** (not Turbo). This reins in the
CPU, which `-pl` does not touch, and it *persists across reboots*. Since the
suspected cause is **combined** CPU+GPU burst overshooting supply, capping only
the GPU addresses half the problem.

### c) Log everything, always

`tools/watch_gpu.ps1` — see section 6.

### d) Caveat, so the lock isn't oversold

Our 1 Hz log undersamples: the true instantaneous peak is above the 139.99 W
recorded, and earlier diagnosis put transients near 190 W. Capping clocks caps
the *sustained* ceiling well, but a spike at the moment of a kernel launch can
still overshoot. Also note pacing alone (2 s between inferences) was tried and
**reduced but did not prevent** the crash — 2026-08-06 died anyway. The clock
lock is the strongest single measure we have, not a guarantee.

## 6. THE LOGGER

`scene-pipeline/entangled_gen/tools/watch_gpu.ps1`
→ `CS-8903-OVM/week7/entangled_gen/out/logs/gpu_watch.csv`

Start it detached so it outlives the shell (a plain background process dies
with the launching tool shell's job object):

```powershell
$s = 'D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen\tools\watch_gpu.ps1'
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$s`""
}
```

Columns:

```
timestamp, temp_C, power_W, sm_MHz, mem_MiB, util_pct, ac_online, batt_rate_mW, batt_pct
```

The first six match the older logs so old and new samples read together. The
last three are new and exist specifically for this problem: `batt_rate_mW` is
negative when draining, and **if it goes negative while on AC, the adapter was
not keeping up** — that would confirm the burst-demand theory outright.

Every line is opened, written and closed individually. That is deliberate: a
buffered stream loses its tail on a power cut, and **the tail is the only part
that matters**. After a crash, read the last few lines.

## 7. WHAT TO DO BEFORE A LONG RUN — ESPECIALLY THE 100-SCENE RUNS

A single scene's vote is 46 objects of bursty GPU work, and most renders on
living_marble are already cached. **A hundred fresh scenes means every render
is a cache miss** — hours of continuous burst, which is the exact condition
that has been killing the machine. Unprotected, a 100-scene run will not
finish.

Preflight, every time:

1. `nvidia-smi -lgc 0,1500` in an admin shell — **and confirm it took**,
   because a previous crash silently reverted it.
2. Armoury Crate out of Turbo.
3. Start `watch_gpu.ps1`.
4. Run the job with `python -u` so its own log is unbuffered and survives a cut.
5. Make sure the job can resume per-item. The vote stage already merges rather
   than overwrites (a `--only` run keeps the other 45 entries verbatim), and
   `.params.json` sidecars make matching renders reuse instead of re-render —
   so a crash costs the current item, not the run. **Verify any new long-running
   stage has the same property before trusting it overnight.**

**Not yet built:** an automatic preflight that refuses to start a long run when
the cap isn't in place. Given that a crash silently removes the cap and the
next retry then runs unprotected, this is the obvious next step. Proposed, not
implemented — it needs a decision about where it lives.

## 8. IF IT STILL CRASHES UNDER THE CLOCK LOCK WITH THE CPU REINED IN

That is a useful result, not a dead end. It means the problem is not the load —
it's the supply, i.e. the battery or the adapter. At that point software has
run out of moves and it becomes a hardware question: given 77 % health at 78
cycles, the battery is the first thing to replace, and ASUS warranty is worth
checking since the degradation is not consistent with the usage.

Check the last lines of `gpu_watch.csv` before concluding anything. If
`batt_rate_mW` went negative on AC in the final seconds, that is the answer.

## 9. THE BATTERY REPLACEMENT OPTION — PARKED 2026-08-10

User decision 2026-08-10: **not doing this now, no time.** Recorded here so it
can be picked up cold later. Warranty is already expired, so self-repair costs
nothing in coverage.

### Decide with the log before spending money

The `batt_rate_mW` column exists for exactly this call. Watch it while
`ac_online` is 1:

- **Goes negative during a burst** → the adapter could not keep up and the
  battery was being drawn on to cover the gap. With a 77 % pack that is the
  answer, and replacing it is the fix.
- **Stays 0 right up to the moment of death** → the battery was never asked to
  help. The problem is upstream — adapter or board — and a new pack would cost
  $100+ and change nothing.

This evidence comes out of any normal run for free. **Read it before ordering.**

### If it turns out to be the battery

The G733 is one of the easier laptop battery swaps: a large desktop-replacement
chassis, bottom panel off, battery is a screwed-in pack with a plug connector,
no adhesive. Roughly 20–30 minutes.

- Phillips #0/#1, plastic pry tool for the panel clips.
- Power off fully, unplug AC, **disconnect the battery connector first**.
- Discharge to ~30 % before starting; don't bend or puncture the pack.
- **Get the part number off the pack itself** (a `C41N…` style code) or from
  ASUS's G733PZ support page. Do not trust a number quoted from memory —
  confirm against the physical label before ordering.
- **Buy genuine or from a seller with a real return policy.** Cheap third-party
  packs often use cells that can't deliver high burst current — which would
  reproduce this exact failure and waste the repair.
- Do **not** run the machine with no battery installed. ROG laptops throttle
  hard without a pack, because the system relies on it to absorb transients.

Regardless of whether it is tonight's culprit: **77 % health at 78 cycles is
not normal wear**, so the pack is due eventually. The log evidence only decides
whether it is urgent.
