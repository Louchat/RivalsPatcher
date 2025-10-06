#!/usr/bin/env python3
import os
import sys
import subprocess
import time
from pathlib import Path

# ---------------------------
# Auto-install required pip packages if missing
# ---------------------------
REQUIRED_PACKAGES = [
    ("colorama", "colorama"),
    ("requests", "requests"),
    ("keyboard", "keyboard"),
    ("pywin32", "pywin32"),
]

def ensure_packages(packages):
    """
    packages: list of tuples (import_name, pip_name)
    """
    to_install = []
    for import_name, pip_name in packages:
        try:
            __import__(import_name)
        except Exception:
            to_install.append((import_name, pip_name))

    if not to_install:
        return True

    print(f"[+] Missing packages detected: {', '.join(p for _, p in to_install)}")
    print("[+] Installing missing packages via pip (this may require internet)...")

    for import_name, pip_name in to_install:
        try:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", pip_name]
            print(f"    -> Installing {pip_name} ...")
            subprocess.check_call(cmd)
            # try re-import
            __import__(import_name)
            print(f"    -> {pip_name} installed.")
        except Exception as e:
            print(f"    !! Failed to install {pip_name}: {e}")
            resp = input("Continue without this package? (y/n) ").strip().lower()
            if resp not in ("y", "yes"):
                print("Aborting due to missing dependency.")
                sys.exit(1)

    # pywin32 postinstall attempt (best-effort)
    try:
        import win32api  # noqa: F401
    except Exception:
        # if pywin32 was installed but postinstall not run, try to run it
        try:
            subprocess.check_call([sys.executable, "-m", "pywin32_postinstall", "-install"])
        except Exception:
            pass

    return True

# Ensure required packages before importing them
ensure_packages(REQUIRED_PACKAGES)

# ---------------------------
# Now import everything safely
# ---------------------------
import zipfile
import tempfile
from colorama import Fore, Style, init
import shutil
import getpass
import itertools
import ctypes

# initialize colorama
init(autoreset=True)

# --- Palette "hack" ---
NEON = Fore.LIGHTGREEN_EX + Style.BRIGHT
ACCENT = Fore.CYAN + Style.BRIGHT
WARN = Fore.YELLOW + Style.BRIGHT
ERR = Fore.RED + Style.BRIGHT
INFO = Fore.MAGENTA + Style.DIM
NORMAL = Fore.WHITE

# --- Helpers ---
def set_opacity(opacity):
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    alpha = int(255 * (opacity / 100))
    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, 0x00000002)

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def loading_animation(text="Searching for user", duration=2.5):
    spinner = itertools.cycle(["|", "/", "-", "\\"])
    end_time = time.time() + duration
    while time.time() < end_time:
        sys.stdout.write(NEON + f"\r{text} {next(spinner)} ")
        sys.stdout.flush()
        time.sleep(0.12)
    sys.stdout.write("\r" + " " * (len(text) + 4) + "\r")

# --- User verification (simple lock file) ---
def load_user():
    if os.path.exists("user.lock"):
        with open("user.lock", "r") as file:
            return file.read().strip()
    return None

def save_user(username):
    with open("user.lock", "w") as file:
        file.write(username)

def verify_user():
    saved_user = load_user()
    if saved_user:
        print(NEON + f"User verified: {saved_user}")
        time.sleep(0.6)
        return saved_user
    user = getpass.getuser()
    loading_animation()
    print(NEON + f"User found: {user}")
    time.sleep(0.25)
    print(ACCENT + "Is this correct?")
    print(NEON + "1) Yes — unlock automatically")
    print(ACCENT + "2) No  — enter manually")
    choice = input(NEON + "> ").strip()
    while choice not in ("1", "2"):
        choice = input(ERR + "Invalid. Enter 1 or 2: ").strip()
    if choice == "1":
        save_user(user)
        print(NEON + "Unlocked automatically.")
        return user
    else:
        manual = input(ACCENT + "Enter username: ").strip()
        save_user(manual)
        print(NEON + f"Manual unlock: {manual}")
        return manual

# --- File ops & backup ---
def backup_original_files(target_root: Path, files_to_replace, backup_root: Path):
    for src in files_to_replace:
        rel = src.relative_to(target_root)
        dest = backup_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

def copy_tree_over(src_root: Path, dst_root: Path):
    copied = 0
    overwritten = 0
    files_to_replace = []
    for root, _, files in os.walk(src_root):
        root_path = Path(root)
        for f in files:
            src_file = root_path / f
            rel = src_file.relative_to(src_root)
            dst_file = dst_root / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if dst_file.exists():
                files_to_replace.append(dst_file)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_root = dst_root.parent / 'backups' / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)
    if files_to_replace:
        print(WARN + f"💾 Backup for {len(files_to_replace)} files -> {backup_root}")
        backup_original_files(dst_root, files_to_replace, backup_root)
    for root, _, files in os.walk(src_root):
        root_path = Path(root)
        for f in files:
            src_file = root_path / f
            rel = src_file.relative_to(src_root)
            dst_file = dst_root / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if dst_file.exists():
                overwritten += 1
            shutil.copy2(src_file, dst_file)
            copied += 1
    return copied, overwritten, backup_root

# --- Bloxstrap helpers ---
def find_bloxstrap_versions(local_appdata: Path) -> Path:
    versions_path = local_appdata / 'Bloxstrap' / 'Versions'
    if not versions_path.exists():
        raise FileNotFoundError(f"{ERR}Bloxstrap Versions not found: {versions_path}")
    subdirs = [d for d in versions_path.iterdir() if d.is_dir()]
    if not subdirs:
        raise FileNotFoundError(f"{ERR}No versions in: {versions_path}")
    latest = max(subdirs, key=lambda p: p.stat().st_mtime)
    return latest

def find_zip_candidate() -> Path:
    default_zip = Path.home() / 'Documents' / 'rivalsPayload' / 'dark-textures-rivals.zip'
    if default_zip.exists():
        return default_zip
    search_dir = Path.home() / 'Documents' / 'rivalsPayload'
    if search_dir.exists():
        zips = list(search_dir.glob('*.zip'))
        if zips:
            for z in zips:
                name = z.name.lower()
                if 'dark' in name or 'texture' in name:
                    return z
            return zips[0]
    print(WARN + "\nNo texture zip found automatically.")
    user_input = input(ACCENT + 'Path to textures zip (leave empty to cancel): ').strip('"')
    if not user_input:
        raise FileNotFoundError("Cancelled by user.")
    z = Path(user_input).expanduser()
    if not z.exists():
        raise FileNotFoundError(f"{ERR}File not found: {z}")
    return z

# --- Sky patcher ---
def patch_custom_sky(target_version: Path):
    print(ACCENT + "\nDo you want to patch a custom sky now? (y/n)")
    choice = input(NEON + "> ").strip().lower()
    if choice not in ('y', 'yes'):
        print(WARN + "Skipping custom sky.")
        return

    sky_zip = Path.home() / 'Documents' / 'rivalsPayload' / 'skyboxes.zip'
    if not sky_zip.exists():
        print(ERR + f"Skyboxes not found: {sky_zip}")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with zipfile.ZipFile(sky_zip, 'r') as zf:
                print(NEON + "Extracting skyboxes...")
                zf.extractall(tmpdir_path)
        except zipfile.BadZipFile:
            print(ERR + "Invalid/corrupted sky zip.")
            return

        sky_dirs = [d for d in tmpdir_path.iterdir() if d.is_dir()]
        if not sky_dirs:
            print(ERR + "No skyboxes inside the zip.")
            return

        print(ACCENT + "\nAvailable skyboxes:")
        for i, d in enumerate(sky_dirs, start=1):
            imgs = len(list(d.rglob('*.*')))
            print(NEON + f"[{i}] {d.name} " + INFO + f"({imgs} files)")

        try:
            choice_num = int(input(NEON + "\nSelect a skybox number: ").strip())
            if not (1 <= choice_num <= len(sky_dirs)):
                print(ERR + "Invalid number.")
                return
        except ValueError:
            print(ERR + "Invalid input.")
            return

        selected = sky_dirs[choice_num - 1]
        target_sky_dir = target_version / 'PlatformContent' / 'pc' / 'textures' / 'sky'
        if target_sky_dir.exists():
            for child in target_sky_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    try:
                        child.unlink()
                    except:
                        pass
        else:
            target_sky_dir.mkdir(parents=True, exist_ok=True)

        print(NEON + f"Applying skybox: {selected.name}")
        copied, overwritten, backup_root = copy_tree_over(selected, target_sky_dir)
        print(NEON + f"Sky applied: {copied} files (overwritten: {overwritten})")
        print(WARN + f"Backup: {backup_root}")

# --- Main ---
def main():
    # ensure admin
    if not is_admin():
        print(ERR + "Restarting as admin...")
        params = ' '.join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit()

    # startup UI
    clear_console()
    set_opacity(72)
    user = verify_user()
    os.system('title [UNLOCKED] // WE LOVE CHEATING //')
    clear_console()
    print(NEON + "/// RIVALS PATCHER ///")
    print(ACCENT + "Developed by Louchatfluff")
    time.sleep(1.2)
    clear_console()

    print(ACCENT + "welcome to " + NEON + "rivalsPatcher" + NORMAL + " — patch bloxstrap files now? (y/n)")
    choice = input(NEON + "> ").strip().lower()

    # if user declines main patch, still offer sky
    if choice not in ('y', 'yes'):
        print(WARN + "Main patch skipped.")
        local_appdata = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        try:
            latest_version = find_bloxstrap_versions(local_appdata)
            patch_custom_sky(latest_version)
        except Exception as e:
            print(ERR + f"Cannot find Bloxstrap to patch sky: {e}")
        print(NEON + "\n✅ Done! Press any key to close...")
        os.system('pause >nul')
        return

    # else perform main patch
    try:
        local_appdata = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        latest_version = find_bloxstrap_versions(local_appdata)
        print(NEON + f"Using Bloxstrap version: {latest_version}")
        target_textures = latest_version / 'PlatformContent' / 'pc' / 'textures'
    except Exception as e:
        print(ERR + f"Error locating Bloxstrap: {e}")
        print(NEON + "\n✅ Done! Press any key to close...")
        os.system('pause >nul')
        return

    try:
        zip_path = find_zip_candidate()
        print(ACCENT + f"Found texture zip: {zip_path}")
    except Exception as e:
        print(ERR + f"Error: {e}")
        print(NEON + "\n✅ Done! Press any key to close...")
        os.system('pause >nul')
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                print(NEON + "Extracting textures...")
                zf.extractall(tmpdir_path)
        except zipfile.BadZipFile:
            print(ERR + "Invalid/corrupted texture zip.")
            print(NEON + "\n✅ Done! Press any key to close...")
            os.system('pause >nul')
            return

        entries = list(tmpdir_path.iterdir())
        src_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmpdir_path

        if not any(src_root.rglob('*')):
            print(ERR + "No valid files found inside texture zip.")
            print(NEON + "\n✅ Done! Press any key to close...")
            os.system('pause >nul')
            return

        try:
            copied, overwritten, backup_root = copy_tree_over(src_root, target_textures)
            print(NEON + f"Patch complete: {copied} files copied, {overwritten} overwritten.")
            print(WARN + f"Backup stored at: {backup_root}")
        except Exception as e:
            print(ERR + f"Error during copy: {e}")
            print(NEON + "\n✅ Done! Press any key to close...")
            os.system('pause >nul')
            return

    print(ACCENT + "\n✨ Patch applied successfully!")
    # offer custom sky
    patch_custom_sky(latest_version)

    # final message & pause
    print(NEON + "\n✅ Done! Press any key to close...")
    os.system('pause >nul')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(ERR + "\nInterrupted by user.")
        sys.exit(1)
