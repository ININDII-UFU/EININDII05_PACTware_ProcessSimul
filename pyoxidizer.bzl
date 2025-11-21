load("pyoxidizer",
     "default_python_distribution",
     "default_target_triple",
     "PythonExecutable",
     "Resource",
     "FileManifest",
)

def make_exe():
    dist = default_python_distribution(python_version = "3.10")

    # Manifesto de arquivos para incluir a pasta db/
    manifest = FileManifest()
    manifest.add_directory("db", "db")

    exe = PythonExecutable(
        dist          = dist,
        name          = "ProcessSimul",
        module_path   = "main.py",
        icon_path     = "assets/app.ico",
        resources     = [
            Resource("db", manifest),
        ],
        target_triple = default_target_triple(),
    )

    return exe

def make_dist():
    exe = make_exe()
    return exe.to_dist()