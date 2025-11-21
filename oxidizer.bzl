def make_exe():
    dist = default_python_distribution()

    exe = dist.to_python_executable(
        name = "ProcessSimul",
        python_script = "main.py",
        windows_icon_path = "assets/app.ico",
    )

    # incluir pasta db inteira
    exe.add_resources("db/", "db")

    return exe

def make_dist():
    return make_exe().to_dist()
