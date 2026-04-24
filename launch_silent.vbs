Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptPath = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "start_platform.py")

On Error Resume Next
shell.Run "pyw -3 """ & scriptPath & """", 0, False
If Err.Number <> 0 Then
	Err.Clear
	shell.Run "pythonw """ & scriptPath & """", 0, False
End If
On Error GoTo 0
