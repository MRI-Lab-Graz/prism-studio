on run
    set scriptPath to POSIX path of (path to me)
    set scriptDir to do shell script "dirname " & quoted form of scriptPath
    set appPath to ""

    -- Try nearby candidates first, then Downloads (where release zips are usually extracted)
    try
        set appPath to do shell script "s=" & quoted form of scriptDir & "; cand1=\"$s/PrismStudio.app\"; if [ -d \"$cand1\" ]; then printf %s \"$cand1\"; exit 0; fi; parent=\"$(dirname \"$s\")\"; cand2=\"$parent/PrismStudio.app\"; if [ -d \"$cand2\" ]; then printf %s \"$cand2\"; exit 0; fi; dl=\"$HOME/Downloads\"; if [ -d \"$dl\" ]; then found=\"$(find \"$dl\" -maxdepth 4 -name 'PrismStudio.app' -type d 2>/dev/null | head -1)\"; if [ -n \"$found\" ]; then printf %s \"$found\"; exit 0; fi; fi; exit 1"
    on error
        set appPath to ""
    end try

    if appPath is "" then
        try
            set chosenApp to choose file of type {"app"} with prompt "PrismStudio.app was not auto-detected. Please select PrismStudio.app from the folder." default location (path to downloads folder)
            set appPath to POSIX path of chosenApp
        on error
            return
        end try
    end if

    try
        set quarantineState to do shell script "xattr -p com.apple.quarantine " & quoted form of appPath & " 2>/dev/null || true"
    on error
        set quarantineState to ""
    end try

    try
        if quarantineState is not "" then
            tell application "Terminal"
                activate
                do script "xattr -dr com.apple.quarantine " & quoted form of appPath & " ; open " & quoted form of appPath
            end tell
        else
            do shell script "open " & quoted form of appPath
        end if
    on error errMsg
        display dialog "Could not launch Prism Studio Installer: " & errMsg buttons {"OK"} default button "OK" with icon caution
    end try
end run
