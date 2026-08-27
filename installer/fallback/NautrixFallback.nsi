Unicode true
RequestExecutionLevel user
SetCompressor /SOLID lzma

!ifndef PAYLOAD_DIR
  !error "PAYLOAD_DIR is required"
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE is required"
!endif
!ifndef VERSION
  !define VERSION "0.0.0.0"
!endif

Name "Nautrix Fallback"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Nautrix\Application"
InstallDirRegKey HKCU "Software\Nautrix" "InstallDir"
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "${VERSION}"
VIAddVersionKey "ProductName" "Nautrix Fallback"
VIAddVersionKey "CompanyName" "Nautrix"
VIAddVersionKey "FileDescription" "Nautrix Windows fallback installer"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Nautrix" SEC_MAIN
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD_DIR}\*.*"

  WriteRegStr HKCU "Software\Nautrix" "InstallDir" "$INSTDIR"

  WriteRegStr HKCU "Software\Classes\NautrixHTM" "" "Nautrix HTML Document"
  WriteRegStr HKCU "Software\Classes\NautrixHTM\DefaultIcon" "" '"$INSTDIR\chrome.exe",0'
  WriteRegStr HKCU "Software\Classes\NautrixHTM\shell\open\command" "" '"$INSTDIR\NautrixLauncher.exe" --single-argument "%1"'

  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix" "" "Nautrix"
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\DefaultIcon" "" '"$INSTDIR\chrome.exe",0'
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\shell\open\command" "" '"$INSTDIR\NautrixLauncher.exe"'
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\Capabilities" "ApplicationName" "Nautrix"
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\Capabilities" "ApplicationDescription" "Nautrix low-latency Chromium browser (fallback build)"
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\Capabilities" "ApplicationIcon" '"$INSTDIR\chrome.exe",0'
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\Capabilities\URLAssociations" "http" "NautrixHTM"
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\Capabilities\URLAssociations" "https" "NautrixHTM"
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\Capabilities\FileAssociations" ".htm" "NautrixHTM"
  WriteRegStr HKCU "Software\Clients\StartMenuInternet\Nautrix\Capabilities\FileAssociations" ".html" "NautrixHTM"
  WriteRegStr HKCU "Software\RegisteredApplications" "Nautrix" "Software\Clients\StartMenuInternet\Nautrix\Capabilities"

  CreateDirectory "$SMPROGRAMS\Nautrix"
  SetOutPath "$INSTDIR"
  CreateShortCut "$SMPROGRAMS\Nautrix\Nautrix.lnk" "$INSTDIR\NautrixLauncher.exe" "" "$INSTDIR\chrome.exe" 0
  CreateShortCut "$SMPROGRAMS\Nautrix\Network Settings.lnk" "$INSTDIR\NautrixNetworkSettings.exe" "" "$INSTDIR\NautrixNetworkSettings.exe" 0
  CreateShortCut "$DESKTOP\Nautrix.lnk" "$INSTDIR\NautrixLauncher.exe" "" "$INSTDIR\chrome.exe" 0

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback" "DisplayName" "Nautrix Fallback"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback" "DisplayIcon" "$INSTDIR\chrome.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\Nautrix.lnk"
  Delete "$SMPROGRAMS\Nautrix\Nautrix.lnk"
  Delete "$SMPROGRAMS\Nautrix\Network Settings.lnk"
  RMDir "$SMPROGRAMS\Nautrix"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback"
  DeleteRegValue HKCU "Software\RegisteredApplications" "Nautrix"
  DeleteRegKey HKCU "Software\Clients\StartMenuInternet\Nautrix"
  DeleteRegKey HKCU "Software\Classes\NautrixHTM"
  DeleteRegKey HKCU "Software\Nautrix"

  RMDir /r "$INSTDIR"
SectionEnd
