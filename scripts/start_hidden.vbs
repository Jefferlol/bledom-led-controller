' ==============================================================================
' Script VBScript para iniciar el servidor BLEDOM en segundo plano (Ventana Oculta)
' Ideal para ejecutar al inicio de Windows mediante el Programador de Tareas
' o colocando un acceso directo en la carpeta shell:startup.
' ==============================================================================

Option Explicit

Dim WshShell, fso, scriptDir, batPath
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Obtener la ruta completa del script bat
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = scriptDir & "\run_server.bat"

' Ejecutar con ventana oculta (0) y sin esperar terminacion (False)
WshShell.Run """" & batPath & """", 0, False

Set WshShell = Nothing
Set fso = Nothing
