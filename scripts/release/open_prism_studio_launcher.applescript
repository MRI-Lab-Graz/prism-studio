on run
    set scriptPath to POSIX path of (path to me)
    
    -- Find the directory containing the installer app
    -- If running from inside the app bundle, extract parent; otherwise use current directory
    set releaseFolder to ""
    try
        set releaseFolder to do shell script "p=" & quoted form of scriptPath & "; while [[ \"$p\" == *.app* ]]; do p=\"$(dirname \"$p\")\"; done; echo \"$p\""
    on error
        set releaseFolder to ""
    end try
    
    if releaseFolder is "" then
        set releaseFolder to do shell script "dirname " & quoted form of scriptPath
    end if
    
    set appPath to releaseFolder & "/PrismStudio.app"

    -- Check if PrismStudio.app exists; if not, search in parent and common locations
    set appExists to false
    try
        do shell script "test -d " & quoted form of appPath
        set appExists to true
    on error
        -- Try to find PrismStudio.app nearby
        try
            set foundPaths to do shell script "find \"" & releaseFolder & "\" -maxdepth 2 -name 'PrismStudio.app' -type d 2>/dev/null | head -1"
            if foundPaths is not "" then
                set appPath to foundPaths
                set appExists to true
            end if
        on error
            set appExists to false
        end try
    end try

    if appExists is false then
        try
            set chosenApp to choose file with prompt "PrismStudio.app was not auto-detected. Please select PrismStudio.app from the folder." default location (path to downloads folder)
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
