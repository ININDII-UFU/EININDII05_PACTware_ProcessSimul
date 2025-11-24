!define APP_NAME "EININDII05_PACTware_ProcessSimul"
!define APP_VERSION "${APP_VER}"
!define COMPANY "UFU-ININDII"
!define INSTALL_DIR "$PROGRAMFILES32\${APP_NAME}"

Icon "installer/assets/icon.ico"
UninstallIcon "installer/assets/icon.ico"

OutFile "setup_${APP_NAME}_${APP_VERSION}.exe"
InstallDir "${INSTALL_DIR}"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install ${APP_NAME}"
    SetOutPath "${INSTALL_DIR}"

    ; Copiar apenas a pasta criada pelo Nuitka
    File /r "${DIST_DIR}\*.*"

    ; Atalho no Menu Iniciar
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "${INSTALL_DIR}\${APP_NAME}.exe"

    ; Atalho de desinstalação no Menu Iniciar
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\Desinstalar ${APP_NAME}.lnk" "${INSTALL_DIR}\Uninstall.exe"

    ; Opcional: Desktop
    ;CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "${INSTALL_DIR}\${APP_NAME}.exe"

    WriteUninstaller "${INSTALL_DIR}\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Desinstalar ${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "${INSTALL_DIR}"
SectionEnd
