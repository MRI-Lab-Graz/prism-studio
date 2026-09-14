# Chapter 0: Install and First Launch

Chapter 0 of [Getting Started — Your First PRISM Project](TUTORIAL_BEGINNER.md).
Everything from here on assumes PRISM Studio is already open in your
browser — this chapter is what gets you there from nothing installed at
all. If Studio is already running for you, skip straight to
[Chapter 1](TUTORIAL_BEGINNER_1_NEW_PROJECT.md).

**Time:** ~10 minutes. **Outcome:** PRISM Studio open at
`http://localhost:5001`, ready for Chapter 1.

```{mermaid}
flowchart LR
    A["Download the ZIP<br/>for your OS"] --> B["Extract it"]
    B --> C["Start the app<br/>(OS may block it once)"]
    C --> D["Studio opens at<br/>localhost:5001"]
```

## 1. Download

Go to the
[latest release page](https://github.com/MRI-Lab-Graz/prism-studio/releases/latest)
and download the ZIP for your operating system:

| Your computer | Download |
|---|---|
| Mac with Apple Silicon (M1/M2/M3/M4) | `prism-studio-macOS-AppleSilicon.zip` |
| Mac with an Intel chip | `prism-studio-macOS-AppleIntel.zip` |
| Windows | `prism-studio-Windows.zip` |
| Linux | `prism-studio-Linux.zip` |

Not sure which Mac chip you have? Apple menu → **About This Mac** — anything
saying "Apple M..." is Apple Silicon, "Intel" is Intel.

## 2. Extract it

Extract the ZIP to a folder you'll remember — your Desktop or Documents is
fine. You'll start PRISM Studio from inside this extracted folder every
time, so it's worth keeping it somewhere you won't accidentally delete.

## 3. Start it — and get past the security warning

Open the extracted folder and start the app. The first time, your
operating system will very likely show a warning, because this build isn't
code-signed (that costs money the project doesn't have yet — see
[Installing an Unsigned Build](INSTALLATION_SECURITY.md) for the full
explanation if you're curious). This is expected, not a sign anything is
wrong.

**On macOS**, double-click `Prism Studio Installer.app` in the extracted
folder — it finds and opens the app for you. If that doesn't work, try
`Open Prism Studio.command` instead. If neither is present, right-click
`PrismStudio.app` → **Open** → confirm **Open** in the dialog.

**On Windows**, double-click `PrismStudio.exe`. When SmartScreen shows
"Windows protected your PC," click **More info**, then **Run anyway**.

**On Linux**, run the extracted app from a terminal.

This warning only appears on first launch. Once you've gotten past it,
starting PRISM Studio again later is a normal double-click.

## 4. What you're looking at

A browser window opens automatically at `http://localhost:5001` — that's
PRISM Studio itself, running as a small local web server on your own
machine (nothing here is uploaded anywhere). If the browser doesn't open by
itself, open that address manually.

![PRISM Studio landing page](_static/screenshots/prism-studio-landing-create.png)

This is the **Home** screen — every session starts here. From here,
Chapter 1 begins with **Create or Open a Project**.

```{note}
Closing the browser tab does not stop PRISM Studio — it keeps running as a
local server until you close the terminal window it launched (or, on
macOS/Windows, quit the app itself). If you don't see this terminal/console
window, look for it in your taskbar or Dock — some launch paths minimize it.
```

## What's next

[Chapter 1: Create a Project](TUTORIAL_BEGINNER_1_NEW_PROJECT.md) —
everything from here uses the app you just opened.
