---
type: doc
title: Curriculum Vitae
font: Helvetica Base 9.5p
page: A4
top-margin: 1.2c
foot-margin: 1.2c
left-margin: 1.8c
right-margin: 1.8c
para-gap: 0.35v
para-indent: 0f
page-headers: None
---

```lout
@CentredDisplay { +8p } @Font @B { James Clements III }
@CentredDisplay {
Portland, Oregon "  -  " james.l.clements.iii "@" gmail.com "  -  " (503) 555-0142
//
github.com "/" clementsj "  -  " clementsj.dev
}
@LP
```

### Summary

Senior audio DSP engineer with seven years of shipped real-time C++
on embedded ARM and desktop platforms. Particular focus on partitioned
convolution reverberation, room correction, and low-latency scheduling.
Comfortable across the full audio stack from kernel-level driver glue
to plug-in UI in JUCE.

### Experience

**Cantus Audio, Portland OR**  ---  *Lead audio engineer*, 2022 -- present.

- Own the real-time engine in *Cantus Verb Pro*: a 96 kHz partitioned
  convolution reverb shipping on macOS, Windows, and an in-house ARM
  hardware unit (Cortex-A78).
- Brought worst-case 64-sample block latency from 11 ms to 2.8 ms
  by redesigning the FFT block scheduler around lock-free SPSC queues.
- Mentor three junior engineers and run the team's weekly DSP reading group.

**CCRMA, Stanford CA**  ---  *Research engineer*, 2019 -- 2022.

- Core contributor to the *faust2* compiler; landed the SSA-based
  delay-line optimiser used in versions 2.50 onward.
- Co-authored two ICASSP papers on physically modelled string synthesis.
- Built and maintained the lab's nightly regression suite (1300 tests).

**Smule, San Francisco CA**  ---  *Audio engineer intern*, summer 2018.

- Implemented the pitch-correction path for *Smule Sing!* on iOS,
  using a phase-vocoder front end and an autocorrelation-based pitch tracker.

### Education

**Stanford University**  ---  M.S., Music, Science & Technology
(CCRMA), 2019. Thesis: *Sparse Time-Varying Filters for
Physically-Modelled Strings.*

**Oberlin Conservatory + College**  ---  B.A. Computer Science,
B.Mus. Harp Performance (dual-degree program), 2016. *Magna cum laude.*

### Technical skills

**Languages**  ---  C, C++17 (daily), Python 3 (daily), TypeScript, Rust, Faust.

**DSP**  ---  Partitioned convolution, FFT-based filtering, phase vocoders,
FDN reverb, physical modelling, room correction, psychoacoustic masking.

**Audio frameworks**  ---  JUCE, CoreAudio, ASIO, ALSA, VST3, AU, AAX, WebAudio.

**Tooling**  ---  CMake, Bazel, perf, Tracy, ASan, TSan, UBSan, Ableton Live, Pro Tools.

**Other**  ---  Concert-level pedal harp; conversational French; amateur radio (KC7QHK).

### Selected publications & projects

- Clements, J. *"Sparse, Time-Varying All-Pole Models for Plucked
  Strings,"* ICASSP 2022.
- Clements, J. and Smith III, J. O. *"A Lazy Scheduler for Faust
  Block Diagrams,"* ICASSP 2021.
- **abcjsharp**  ---  fork of `abcjs` with proper harp grand-staff
  rendering. github.com/clementsj/abcjsharp.
- **mdlout**  ---  the Markdown-to-PDF pipeline used to build this CV.
  *References available on request.*
