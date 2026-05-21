---
type: doc
font: Times Base 11p
page: Letter
top-margin: 2.5c
foot-margin: 2.5c
left-margin: 2.5c
right-margin: 2.5c
para-gap: 1.2v
para-indent: 0f
page-headers: None
---

<!--
  mdlout has no dedicated `type: letter` yet, so this file uses `type: doc`
  with raw-Lout passthrough for the letter-specific blocks. The structure
  mirrors a standard US business letter.
-->

```lout
@RightDisplay {
James Clements III
//
1742 Larkspur Lane
//
Portland, OR 97214
//
james.l.clements.iii "@" gmail.com
}
```

```lout
@LeftDisplay { 21 May 2026 }
```

```lout
@LeftDisplay {
Dr. Eleanor Whitcombe
//
Director of Engineering
//
Lyrebird Acoustics, Inc.
//
404 Resonance Drive
//
Cambridge, MA 02139
}
```

```lout
@LP
@B { Re: } Position of Senior Audio DSP Engineer, requisition LB-2026-073.
```

Dear Dr. Whitcombe,

I am writing to apply for the Senior Audio DSP Engineer position posted on
Lyrebird's careers page last week. My background in real-time signal
processing for low-latency music applications, together with seven years
of production C++ on embedded ARM targets, lines up unusually well with
the role's stated requirements, and I would welcome the chance to bring
that experience to your team.

For the last four years I have led the audio-engine work at Cantus Audio,
where I am responsible for a 96 kHz convolution-reverb pipeline that ships
on both desktop and a Cortex-A78 hardware unit. I redesigned the partitioned
convolution scheduler to bring worst-case block latency from 11 ms to under
3 ms, and I wrote the test harness our QA team still uses to catch regressions.
Prior to Cantus I spent three years at the Center for Computer Research in
Music and Acoustics at Stanford, contributing to the *faust2* DSL compiler
and publishing two papers on physically-modelled string synthesis.

What draws me to Lyrebird specifically is the company's stated commitment
to publishing measurement methodology, not just product specs. I have
followed your room-correction work since the original ICASSP 2023 paper,
and I would be delighted to contribute to the next generation of that
research. I can make myself available for an initial conversation any
afternoon next week, and I have attached a CV and three representative
code samples for your consideration.

Thank you for your time, and I look forward to hearing from you.

```lout
@LP
Yours sincerely,
@LP
@LP
@LP
James Clements III
```
