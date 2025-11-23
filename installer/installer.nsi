!define APP_NAME "ProcessSimul"
!define APP_VERSION "${APP_VER}"
!define COMPANY "UFU - ININDII"
!define INSTALL_DIR "$PROGRAMFILES32\${APP_NAME}"

OutFile "setup_${APP_NAME}_${APP_VERSION}.exe"
InstallDir "${INSTALL_DIR}"
RequestExecutionLevel admin

BrandingText "UFU / ININDII - ProcessSimul"

# --------------------------
# UI DEFINITIONS
# --------------------------
!include MUI2.nsh

!define MUI_ABORTWARNING

; Bem-vindo
!define MUI_WELCOMEPAGE_TITLE "Instalação do ${APP_NAME}"
!define MUI_WELCOMEPAGE_TEXT "Bem-vindo ao instalador do ${APP_NAME}!$r$n$r$nEste instalador irá configurar o programa no seu computador."
!define MUI_WELCOMEPAGE_BMP "assets\welcome.bmp"

; Banner do topo
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "assets\header.bmp"

; Ícone do instalador
Icon "assets\icon.ico"
UninstallIcon "assets\icon.ico"

; Página de licença
!define MUI_LICENSEPAGE_CHECKBOX
!define MUI_LICENSEPAGE_TEXT_BOTTOM "Leia os termos e marque a caixa para continuar."
!define MUI_LICENSEPAGE_BGCOLOR "FFFFFF"

; Diretório de instalação
!define MUI_DIRECTORYPAGE_VERIFYONLEAVE

; Página final personalizada
!define MUI_FINISHPAGE_TITLE "Instalação concluída!"
!define MUI_FINISHPAGE_TEXT "O ${APP_NAME} foi instalado com sucesso no seu computador."
!define MUI_FINISHPAGE_RUN "${INSTALL_DIR}\${APP_NAME}.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Executar agora"

; Página de desinstalação
!define MUI_UNWELCOMEPAGE_TEXT "Este assistente removerá o ${APP_NAME} do sistema."

# --------------------------
# Páginas do instalador
# --------------------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "assets\license.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

# --------------------------
# Páginas do desinstalador
# --------------------------
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

# --------------------------
# Linguagens
# --------------------------
!insertmacro MUI_LANGUAGE "PortugueseBR"


# ==============================================================
#   SEÇÃO DE INSTALAÇÃO
# ==============================================================

Section "Install ${APP_NAME}"
    SetOutPath "${INSTALL_DIR}"
    File /r "dist\main.dist\*.*"

    ; Atalho no Menu Iniciar
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "${INSTALL_DIR}\${APP_NAME}.exe" "" \
        "${INSTALL_DIR}\${APP_NAME}.exe" 0

    ; Atalho no Desktop (opcional)
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" \
        "${INSTALL_DIR}\${APP_NAME}.exe"

    WriteUninstaller "${INSTALL_DIR}\Uninstall.exe"
SectionEnd

# ==============================================================
#   SEÇÃO DE DESINSTALAÇÃO
# ==============================================================

Section "Uninstall"
    ; Remover atalhos
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"

    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; Remover diretório
    RMDir /r "${INSTALL_DIR}"
SectionEnd