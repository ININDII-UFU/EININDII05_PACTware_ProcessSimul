load(
    "pyoxidizer",
    "default_python_distribution",
    "default_target_triple",
    "PythonExecutable",
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
        # testa sem ícone para eliminar mais uma variável
        icon_path = None,
    )

    return exe

def make_dist():
    return make_exe().to_dist()
