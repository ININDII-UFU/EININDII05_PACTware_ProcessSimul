load("pyoxidizer",
     "default_python_distribution",
     "default_target_triple",
     "PythonExecutable",
     "FileManifest",
     "Resource",
)

def check_file(path):
    try:
        open(path)
        print(f"[OK] Arquivo encontrado: {path}")
        return True
    except Exception as e:
        print(f"[ERRO] Arquivo NÃO encontrado: {path}")
        print(f"Motivo: {e}")
        return False

def check_dir(path):
    import os
    if os.path.isdir(path):
        print(f"[OK] Diretório encontrado: {path}")
        print(f"Conteúdo:")
        for root, dirs, files in os.walk(path):
            for f in files:
                print(" -", os.path.join(root, f))
        return True
    else:
        print(f"[ERRO] Diretório NÃO encontrado: {path}")
        return False

def make_exe():
    print("===== DEBUG PyOxidizer =====")
    import os
    print("Diretório atual:", os.getcwd())
    print("Conteúdo raiz:")
    for x in os.listdir("."):
        print(" -", x)
    print("============================")

    # -------------------------------------------
    # Checagem explícita dos arquivos críticos
    # -------------------------------------------
    check_file("main.py")
    check_file("assets/app.ico")
    check_dir("db")

    dist = default_python_distribution(
        python_version = "3.10",
        flavor = "standalone_dynamic",
    )

    manifest = FileManifest()
    try:
        manifest.add_directory("db", "db")
        print("[OK] Manifesto da pasta 'db' adicionado.")
    except Exception as e:
        print("[ERRO] Falha ao adicionar pasta 'db':", e)

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

    print("[OK] PythonExecutable criado com sucesso.")
    return exe

def make_dist():
    print("Gerando distribuição final...")
    return make_exe().to_dist()