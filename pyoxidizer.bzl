load(
    "pyoxidizer",
    "default_python_distribution",
    "default_target_triple",
    "PythonExecutable",
    "FileManifest",
    "FileContent",
)

def make_exe():
    # Distribuição mínima: só Python, sem scan automático de projeto
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
        # agora usando o ícone real do projeto
        icon_path = "assets/app.ico",
    )

    return exe


def make_dist():
    # Executável embutindo o Python
    exe = make_exe()

    # Layout final de arquivos ao lado do .exe
    files = FileManifest()

    # Coloca o executável na raiz do diretório de build
    # (nome e path são gerenciados pelo PyOxidizer)
    files.add_python_resource(".", exe)

    # Adiciona o arquivo de banco de dados em "db/banco.db"
    # ao lado do executável (mesma estrutura do seu repo)
    files.add_file(
        FileContent(path = "db/banco.db"),
        path = "db/banco.db",
    )

    # Se no futuro quiser levar mais coisas (ex.: toda a pasta db_files),
    # é só adicionar novos FileContent/add_file aqui.

    return files
