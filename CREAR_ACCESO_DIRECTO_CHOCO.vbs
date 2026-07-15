Option Explicit
Dim shell, fso, baseDir, desktop, shortcut, target, iconPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktop = shell.SpecialFolders("Desktop")
target = baseDir & "\ABRIR_CHOCO_CONTROL.bat"
iconPath = baseDir & "\iconos\choco_icon.ico"
Set shortcut = shell.CreateShortcut(desktop & "\Abrir Choco Control.lnk")
shortcut.TargetPath = target
shortcut.WorkingDirectory = baseDir
shortcut.WindowStyle = 1
shortcut.Description = "Abrir Choco Control - Up Base"
shortcut.IconLocation = iconPath & ",0"
shortcut.Save
MsgBox "Acceso directo creado en el escritorio con el icono de Choco Control.", 64, "Choco Control"
