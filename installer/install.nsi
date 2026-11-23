Unicode true
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "FileFunc.nsh"

!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "1.5.18.0"
!endif
!ifndef PRODUCT_VERSION_SHORT
  !define PRODUCT_VERSION_SHORT "1.5.18"
!endif

Name "文文"
Caption "文文 安装程序"
OutFile "文文_安装包_v${PRODUCT_VERSION_SHORT}.exe"
InstallDir "$LOCALAPPDATA\Programs\FileKeeper"
InstallDirRegKey HKCU "Software\FileKeeper" "InstallDir"
RequestExecutionLevel user
BrandingText "文文 · 文件和发票整理管家 · 注册版"

VIProductVersion "${PRODUCT_VERSION}"
VIAddVersionKey "ProductName" "文文"
VIAddVersionKey "CompanyName" "文文"
VIAddVersionKey "FileDescription" "文文安装程序"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "LegalCopyright" "Copyright (C) 2026"

!define MUI_ICON "filekeeper.ico"
!define MUI_UNICON "filekeeper.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "欢迎安装 文文"
!define MUI_WELCOMEPAGE_TEXT "文文帮你把发票、文档、图片自动识别并归档。$\r$\n$\r$\n安装后首次启动会自动生成机器码和注册码，并免费试用 24 小时；到期后扫码订阅（默认 9.9 元/30 天）。$\r$\n$\r$\n数据保存在本地，不会上传文件内容。"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\文件管家.exe"
!define MUI_FINISHPAGE_RUN_TEXT "立即启动文文（首次启动自动开通 24 小时试用）"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\注册说明.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "查看注册与订阅说明"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "安装" SecMain
  nsExec::ExecToLog 'taskkill /F /IM 文件管家.exe'
  SetOutPath "$INSTDIR"
  File /r "app\*"
  File "filekeeper.ico"
  File "注册说明.txt"

  WriteUninstaller "$INSTDIR\卸载文文.exe"

  ; 升级迁移：清理旧品牌快捷方式与旧卸载器
  Delete "$DESKTOP\文件管家.lnk"
  Delete "$SMPROGRAMS\文件管家\文件管家.lnk"
  Delete "$SMPROGRAMS\文件管家\卸载文件管家.lnk"
  RMDir "$SMPROGRAMS\文件管家"
  Delete "$INSTDIR\卸载文件管家.exe"

  CreateDirectory "$SMPROGRAMS\文文"
  CreateShortcut "$SMPROGRAMS\文文\文文.lnk" "$INSTDIR\文件管家.exe" "" "$INSTDIR\filekeeper.ico" 0
  CreateShortcut "$SMPROGRAMS\文文\卸载文文.lnk" "$INSTDIR\卸载文文.exe"
  CreateShortcut "$DESKTOP\文文.lnk" "$INSTDIR\文件管家.exe" "" "$INSTDIR\filekeeper.ico" 0

  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "DisplayName" "文文"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "Publisher" "文文"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "DisplayIcon" "$INSTDIR\filekeeper.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "UninstallString" '"$INSTDIR\卸载文文.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "NoRepair" 1

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper" "EstimatedSize" "$0"

  WriteRegStr HKCU "Software\FileKeeper" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\FileKeeper" "Version" "${PRODUCT_VERSION}"
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'taskkill /F /IM 文件管家.exe'
  Delete "$DESKTOP\文文.lnk"
  Delete "$SMPROGRAMS\文文\文文.lnk"
  Delete "$SMPROGRAMS\文文\卸载文文.lnk"
  RMDir "$SMPROGRAMS\文文"

  ; 兼容旧品牌快捷方式
  Delete "$DESKTOP\文件管家.lnk"
  Delete "$SMPROGRAMS\文件管家\文件管家.lnk"
  Delete "$SMPROGRAMS\文件管家\卸载文件管家.lnk"
  RMDir "$SMPROGRAMS\文件管家"

  Delete "$INSTDIR\文件管家.exe"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\filekeeper.ico"
  Delete "$INSTDIR\注册说明.txt"
  Delete "$INSTDIR\卸载文文.exe"
  Delete "$INSTDIR\卸载文件管家.exe"
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileKeeper"
  DeleteRegValue HKCU "Software\FileKeeper" "InstallDir"
  DeleteRegValue HKCU "Software\FileKeeper" "Version"
  DeleteRegKey /ifempty HKCU "Software\FileKeeper"

  ; 保留 %APPDATA%\FileKeeper 下的台账、方案与授权文件，卸载不丢数据
  IfSilent done_msg
  MessageBox MB_ICONINFORMATION|MB_OK "已卸载文文。$\r$\n$\r$\n你的归档记录、发票台账与授权信息保留在 %APPDATA%\FileKeeper，重新安装后可继续使用。"
done_msg:
SectionEnd







