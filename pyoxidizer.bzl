load(
    "pyoxidizer",
    "default_python_distribution",
    "default_target_triple",
    "PythonExecutable",
    "FileContent",
)

def make_exe():
    # Distribuição padrão do PyOxidizer com Python 3.10,
    # flavor dinâmico (suporta tkinter em Windows).
    dist = default_python_distribution(
        python_version = "3.10",
        flavor = "standalone_dynamic",
        raw_python_only = True,
    )

    exe = PythonExecutable(
        dist = dist,
        name = "ProcessSimul",
        module_path = "main.py",
        target_triple = default_target_triple(),
        icon_path = "assets/app.ico",   # ícone do seu projeto
    )

    # Ativa suporte ao tkinter: instala os arquivos tcl
    # na pasta "tcl" ao lado do executável e configura
    # automaticamente TCL_LIBRARY em runtime.
    # (conforme docs oficiais do PyOxidizer para tkinter)
    exe.tcl_files_path = "tcl"

    return exe


def make_dist():
    # Constrói a distribuição a partir do executável configurado
    dist = make_exe().to_dist()

    # Garante que o arquivo do banco de dados esteja presente
    # em "db/banco.db" na pasta final de distribuição,
    # igual ao layout do seu repositório.
    dist.add_file(
        FileContent(path = "db/banco.db"),
        path = "db/banco.db",
    )

    return dist
