load("pyoxidizer",
     "default_python_distribution",
     "default_target_triple",
     "PythonExecutable",
     "FileManifest",
     "Resource",
)

def make_exe():
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
    return make_exe().to_dist()