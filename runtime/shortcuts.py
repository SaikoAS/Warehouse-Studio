"""Install or remove the current user's optional Start menu shortcut."""

import argparse
from contextlib import contextmanager
import ctypes as ct
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4


class GUID(ct.Structure):
    _fields_ = [("data1", wintypes.DWORD), ("data2", wintypes.WORD),
                ("data3", wintypes.WORD), ("data4", ct.c_ubyte * 8)]


def guid(value):
    return GUID.from_buffer_copy(UUID(value).bytes_le)


PROGRAMS = "A77F5D77-2E2B-44C3-A6A2-ABA601054A51"
SHELL_LINK = "00021401-0000-0000-C000-000000000046"
I_SHELL_LINK_W = "000214F9-0000-0000-C000-000000000046"
I_PERSIST_FILE = "0000010B-0000-0000-C000-000000000046"


def check(status):
    if status < 0:
        raise OSError(f"Windows Shell reported error 0x{status & 0xFFFFFFFF:08X}.")


def programs_folder():
    path = ct.c_void_p()
    check(ct.windll.shell32.SHGetKnownFolderPath(ct.byref(guid(PROGRAMS)), 0, None, ct.byref(path)))
    try:
        return Path(ct.wstring_at(path))
    finally:
        ct.windll.ole32.CoTaskMemFree(path)


def com_method(interface, slot, *types, result=ct.c_long):
    vtable = ct.cast(interface, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
    return ct.WINFUNCTYPE(result, ct.c_void_p, *types)(vtable[slot])


@contextmanager
def shell_link():
    ole = ct.windll.ole32
    check(ole.CoInitializeEx(None, 2))  # COINIT_APARTMENTTHREADED
    link, persist = ct.c_void_p(), ct.c_void_p()
    try:
        check(ole.CoCreateInstance(ct.byref(guid(SHELL_LINK)), None, 1,
                                   ct.byref(guid(I_SHELL_LINK_W)), ct.byref(link)))
        query_interface = com_method(link, 0, ct.POINTER(GUID), ct.POINTER(ct.c_void_p))
        check(query_interface(link, ct.byref(guid(I_PERSIST_FILE)), ct.byref(persist)))
        yield link, persist
    finally:
        for interface in (persist, link):
            if interface:
                com_method(interface, 2, result=wintypes.ULONG)(interface)
        ole.CoUninitialize()


def shortcut_target(path):
    with shell_link() as (link, persist):
        load = com_method(persist, 5, ct.c_wchar_p, wintypes.DWORD)
        check(load(persist, str(path), 0))
        buffer = ct.create_unicode_buffer(32768)
        get_path = com_method(link, 3, ct.c_wchar_p, ct.c_int, ct.c_void_p, wintypes.DWORD)
        check(get_path(link, buffer, len(buffer), None, 4))  # SLGP_RAWPATH
        return buffer.value


def save_shortcut(path, target):
    with shell_link() as (link, persist):
        set_path = com_method(link, 20, ct.c_wchar_p)
        set_working_directory = com_method(link, 9, ct.c_wchar_p)
        save = com_method(persist, 6, ct.c_wchar_p, wintypes.BOOL)
        check(set_path(link, str(target)))
        check(set_working_directory(link, str(target.parent)))
        check(save(persist, str(path), True))


def run_file_commands(commands, **paths):
    # Store Python redirects AppData writes. The system command processor runs
    # outside that package. Delayed expansion passes paths without parsing them
    # as command syntax, including paths containing %, !, or &.
    system = Path(os.environ["SystemRoot"]) / "System32"
    cmd = system / "cmd.exe"
    env = {**os.environ, "WS_COMPARE": str(system / "fc.exe")}
    env.update({name: str(path) for name, path in paths.items()})
    return subprocess.run(
        [cmd, "/d", "/e:on", "/v:on", "/q"], env=env,
        input=("\r\n".join(commands) + "\r\n").encode("ascii"),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode


def read_installed_shortcut(path, snapshot):
    status = run_file_commands([
        'if exist "!WS_LINK!\\" exit /b 3',
        'dir /a:l /b "!WS_LINK!" && exit /b 3',
        'if not exist "!WS_LINK!" exit /b 2',
        'copy /b /y "!WS_LINK!" "!WS_SNAPSHOT!"',
        'if errorlevel 1 exit /b 1',
        'exit /b 0',
    ], WS_LINK=path, WS_SNAPSHOT=snapshot)
    if status == 3:
        raise ValueError("The Start menu entry is a folder or a reparse point. Review it in File Explorer.")
    if status == 2:
        return None
    if status != 0:
        raise OSError("Cannot read the shortcut in your Start menu.")
    return shortcut_target(snapshot)


def install_shortcut(path, source):
    # Stage the file next to the destination so the final rename is atomic and
    # fails if another copy has already created the entry.
    pending = path.with_name(f".warehouse-studio-{uuid4().hex}.tmp")
    status = run_file_commands([
        'copy /b /y "!WS_SOURCE!" "!WS_PENDING!" && ren "!WS_PENDING!" "!WS_NAME!" && exit /b 0',
        'if exist "!WS_PENDING!" del /q /a:-d "!WS_PENDING!"',
        'exit /b 1',
    ], WS_SOURCE=source, WS_PENDING=pending, WS_NAME=path.name)
    if status != 0:
        raise OSError("Cannot create the shortcut in your Start menu. Check access and try again.")


def remove_shortcut(path, snapshot):
    status = run_file_commands([
        'if exist "!WS_LINK!\\" exit /b 1',
        'dir /a:l /b "!WS_LINK!" && exit /b 1',
        '"!WS_COMPARE!" /b "!WS_LINK!" "!WS_SNAPSHOT!" || exit /b 1',
        'del /q /a:-d "!WS_LINK!"',
        'if exist "!WS_LINK!" exit /b 1',
        'exit /b 0',
    ], WS_LINK=path, WS_SNAPSHOT=snapshot)
    if status != 0:
        raise OSError("Cannot remove the shortcut in your Start menu. Check access and try again.")


def update_shortcut(action, path, target):
    with TemporaryDirectory() as scratch:
        # Resolve any package redirection so the native process sees our scratch files.
        snapshot = Path(scratch).resolve(strict=True) / path.name
        installed_target = read_installed_shortcut(path, snapshot)
        if installed_target is not None:
            if os.path.normcase(installed_target) != os.path.normcase(str(target)):
                raise ValueError("The Start menu entry belongs to another location. Review it in File Explorer.")
            if action == "create":
                return "The Start menu shortcut already points to this copy."
            remove_shortcut(path, snapshot)
            return "Removed the Warehouse Studio shortcut from your Start menu."
        if action == "remove":
            return "There is no Warehouse Studio shortcut in your Start menu."
        if not target.is_file():
            raise ValueError("Extract the complete ZIP and keep the start script with the application files.")
        save_shortcut(snapshot, target)
        install_shortcut(path, snapshot)
        return "Created the Warehouse Studio shortcut in your Start menu."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "remove"))
    args = parser.parse_args()
    if os.name != "nt":
        parser.exit(1, "Warehouse Studio shortcut: run this helper on Windows.\n")
    try:
        target = Path(__file__).resolve().parents[1] / "Start Warehouse Studio.cmd"
        result = update_shortcut(args.action, programs_folder() / "Warehouse Studio.lnk", target)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Warehouse Studio shortcut: {error}\n")
    print(result)


if __name__ == "__main__":
    main()
