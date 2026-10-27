; Added by electron-builder to the installer (see "nsis.include" in package.json).
; The installed app starts with Windows for the user who installed it: a per-user Run entry, removed again on uninstall.
; The portable build installs nothing, so it does not register this entry.

!macro customInstall
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Xbox Mode" "$\"$INSTDIR\${APP_EXECUTABLE_FILENAME}$\""
!macroend

!macro customUnInstall
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Xbox Mode"
!macroend
