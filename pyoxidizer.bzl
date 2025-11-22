load(
    "pyoxidizer",
    "default_python_distribution",
    "default_target_triple",
    "PythonExecutable",
    "FileContent",
)

def make_exe():
    # Distribuição mínima: só Python, nada de scan bizarro de projeto
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
        # agora usando o ícone do projeto
        icon_path = "assets/app.ico",
    )

    return exe

def make_dist():
    # ponto de partida: o que você já tinha antes
    dist = make_exe().to_dist()

    # adiciona o arquivo do banco de dados na pasta "db" ao lado do .exe
    # (isso garante que o caminho relativo "db/banco.db" continue funcionando)
    db_file = FileContent(path = "db/banco.db")
    dist.add_file(db_file, path = "db/banco.db")

    return dist