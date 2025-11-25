!define APP_NAME "ProcessSimul"
!define APP_VERSION "${APP_VER}"
!define COMPANY "UFU-ININDII"
!define INSTALL_DIR "$PROGRAMFILES32\${APP_NAME}"
!define DIST_DIR "${DIST_DIR}"

OutFile "setup_${APP_NAME}_${APP_VERSION}.exe"
InstallDir "${INSTALL_DIR}"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install ${APP_NAME}"
    SetOutPath "${INSTALL_DIR}"
    File /r "${DIST_DIR}\*.*"

    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "${INSTALL_DIR}\${APP_NAME}.exe"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\Desinstalar ${APP_NAME}.lnk" "${INSTALL_DIR}\Uninstall.exe"

    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "${INSTALL_DIR}\${APP_NAME}.exe"

    WriteUninstaller "${INSTALL_DIR}\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Desinstalar ${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "${INSTALL_DIR}"
SectionEnd
