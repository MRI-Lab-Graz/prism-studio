on run
    set scriptPath to POSIX path of (path to me)
    set releaseFolder to do shell script "dirname " & quoted form of scriptPath
    set appPath to releaseFolder & "/PrismStudio.app"
    set commandPath to releaseFolder & "/Open Prism Studio.command"

    try
        do shell script "test -f " & quoted form of commandPath
    on error
        display dialog "Open Prism Studio.command was not found next to this launcher app. Please keep both files in the same folder." buttons {"OK"} default button "OK" with icon caution
        return
    end try

    try
        do shell script "test -d " & quoted form of appPath
    on error
        display dialog "PrismStudio.app was not found next to this launcher app." buttons {"OK"} default button "OK" with icon caution
        return
    end try

    try
        set quarantineState to do shell script "xattr -p com.apple.quarantine " & quoted form of appPath & " 2>/dev/null || true"
    on error
        set quarantineState to ""
    end try

    try
        if quarantineState is not "" then
            do shell script "open -a Terminal " & quoted form of commandPath
        else
            do shell script "open " & quoted form of appPath
        end if
    on error errMsg
        display dialog "Could not open Terminal launcher: " & errMsg buttons {"OK"} default button "OK" with icon caution
    end try
end run
