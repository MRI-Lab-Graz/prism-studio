on run
    set scriptPath to POSIX path of (path to me)
    set releaseFolder to do shell script "p=" & quoted form of scriptPath & "; case \"$p\" in *.app/*) b=${p%%.app/*}.app ;; *.app/) b=${p%/} ;; *.app) b=$p ;; *) b=$(dirname \"$p\") ;; esac; if [ -d \"$b\" ]; then dirname \"$b\"; else dirname \"$p\"; fi"
    set appPath to releaseFolder & "/PrismStudio.app"

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
            tell application "Terminal"
                activate
                do script "xattr -dr com.apple.quarantine " & quoted form of appPath & " ; open " & quoted form of appPath
            end tell
        else
            do shell script "open " & quoted form of appPath
        end if
    on error errMsg
        display dialog "Could not launch Prism Studio: " & errMsg buttons {"OK"} default button "OK" with icon caution
    end try
end run
