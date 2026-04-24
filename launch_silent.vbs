Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

rootDir    = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = fso.BuildPath(rootDir, "start_platform.py")
loadingPage = fso.BuildPath(rootDir, "loading.html")

' 1. Start Python server silently (no window)
On Error Resume Next
shell.Run "pyw -3 """ & scriptPath & """", 0, False
If Err.Number <> 0 Then
    Err.Clear
    shell.Run "pythonw """ & scriptPath & """", 0, False
End If
On Error GoTo 0

' 2. Open loading.html in the default browser immediately.
'    It will poll /health and redirect to http://127.0.0.1:8000 when ready.
shell.Run "explorer """ & loadingPage & """", 1, False
