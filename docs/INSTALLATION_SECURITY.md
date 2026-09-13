# Installing an Unsigned Build

PRISM Studio's prebuilt releases are not code-signed. Signing costs money
the project doesn't currently have — a Windows certificate runs
$200-500/year, and an Apple Developer Program membership is $99/year, paid
annually for as long as the software is distributed. This page explains
what that means in practice, exactly what you'll see, how to get past it,
how to check you downloaded the real thing, and an alternative if you'd
rather not click past a security warning at all.

## What "unsigned" means (and what it doesn't)

Code signing is a paid certificate a developer attaches to a build so the
operating system can show *"this came from a verified publisher"* instead
of *"this came from someone unknown."* It says nothing about whether the
software is safe — it only says who published it, in a way the OS can
check cryptographically.

An unsigned build is not a build the OS has flagged as malicious. It's a
build the OS has no publisher information for at all, so it defaults to
its most cautious warning — the same warning it would show for genuinely
unwanted software, because from the OS's point of view the two look
identical at this check. That's an unavoidable side effect of not paying
for signing, not a judgment about this specific software.

## What you'll see on macOS, and how to get past it

macOS's Gatekeeper blocks the app on first launch with a dialog saying it
"cannot be opened because the developer cannot be verified" (or "is
damaged and can't be opened" on some macOS versions — this wording is
Gatekeeper's, not a sign of a bad download). The release ZIP includes two
helpers to get past this without going through System Settings:

1. **`Prism Studio Installer.app`** — double-click it. It finds
   `PrismStudio.app` in the same folder and opens it. If macOS's App
   Translocation feature prevents that auto-detection, it asks you to
   select `PrismStudio.app` yourself, once.
2. **`Open Prism Studio.command`** — if the installer doesn't work, use
   this instead. It removes the quarantine flag macOS attaches to
   downloaded files and starts the app directly.

If neither is available or both fail, the manual route:

1. Right-click (or Control-click) `PrismStudio.app` in Finder.
2. Click **Open**.
3. Confirm **Open** in the dialog that appears.

This manual route only needs to happen once — after this first
right-click-Open, macOS remembers your choice and future launches work
normally. Apple's own guide covers the same steps with screenshots:
[Open a Mac app from an unidentified developer](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac).

## What you'll see on Windows, and how to get past it

Windows Defender SmartScreen shows a blue "Windows protected your PC"
screen the first time you run `PrismStudio.exe`, naming it an
unrecognized app. To proceed:

1. Click **More info** (a small link inside the SmartScreen dialog).
2. Click **Run anyway**.

This appears once per downloaded copy of the file, not once per computer
— if you re-download a new release later, expect to see it again.

If Windows Firewall separately prompts you to allow network access when
Studio first starts: PRISM Studio listens on `127.0.0.1` (your own machine
only) by default, so this prompt is unusual for a normal launch — but if
you do see it, **Allow** is safe; it does not expose the app to your
network.

## Verifying your download

PRISM Studio does not currently publish checksums for release assets, so
there is no independent value to check your download against yet. Until
that changes, the strongest thing you can do is make sure you're
downloading from the right place at all: get every release exclusively
from
[github.com/MRI-Lab-Graz/prism-studio/releases](https://github.com/MRI-Lab-Graz/prism-studio/releases),
never from a mirror, a forwarded link, or a search result claiming to host
the same file. GitHub serves release assets directly from the repository
you can inspect yourself.

## Would rather not click past a security warning?

That's a reasonable position, and PRISM Studio doesn't require the
prebuilt release — the [Source Install](INSTALLATION.md#source-install-advanced)
section runs the same application from a `git clone` of this repository
instead, with nothing unsigned to get past. It runs a short setup script
that installs Python packages into a `.venv` folder *inside* the cloned
repository only — it does not touch anything else on your system, install
anything system-wide, or need administrator/root access.

It does need a terminal (Terminal.app on macOS, PowerShell on Windows) and
Python 3.10 or newer ([python.org/downloads](https://www.python.org/downloads/)
if you don't already have it) — a bigger one-time step than double-clicking
a ZIP, but a terminal here is just a window you paste a handful of exact
commands into, one at a time, waiting for each to finish before the next.
The commands themselves are in [Installation](INSTALLATION.md#source-install-advanced).

## What's next

- [Installation](INSTALLATION.md) — the full install guide this page is
  linked from
- [Getting Started](TUTORIAL_BEGINNER.md) — the hands-on tutorial, Chapter 0
  covers this same ground for a first-time reader
