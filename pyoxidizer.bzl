load("pyoxidizer",
     "default_python_distribution",
     "default_target_triple",
     "PythonExecutable",
     "FileManifest",
     "Resource",
)

def make_exe():
    print("===== DEBUG PyOxidizer (Starlark Safe) =====")
    print("Verificando arquivos esperados...")

    print("Existe main.py? ->", project_path_exists("main.py"))
    print("Existe assets/app.ico? ->", project_path_exists("assets/app.ico"))
    print("Existe diretório db/? ->", project_path_exists("db"))

    dist = default_python_distribution(
        python_version = "3.10",
        flavor = "standalone_dynamic",
    )

    manifest = FileManifest()
    manifest.add_directory("db", "db")

    exe = PythonExecutable(
        dist = dist,
        name = "ProcessSimul",
        module_path = "main.py",
        target_triple = default_target_triple(),
        icon_path = "assets/app.ico",
        resources = [
            Resource("db", manifest),
        ],
        include_resources_in_executable = True,
    )

    return exe

def make_dist():
    print("Gerando distribuição final...")
    return make_exe().to_dist()