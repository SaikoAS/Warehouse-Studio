"""Install or remove the current user's optional Start menu shortcut."""

import argparse
from contextlib import contextmanager
import ctypes as ct
from ctypes import wintypes
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID


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


def update_shortcut(action, path, target):
    if path.is_symlink():
        raise ValueError("The Start menu entry is a symbolic link. Review it in File Explorer.")
    if path.exists():
        if os.path.normcase(shortcut_target(path)) != os.path.normcase(str(target)):
            raise ValueError("The Start menu entry belongs to another location. Review it in File Explorer.")
        if action == "create":
            return "The Start menu shortcut already points to this copy."
        path.unlink()
        return "Removed the Warehouse Studio shortcut from your Start menu."
    if action == "remove":
        return "There is no Warehouse Studio shortcut in your Start menu."
    if not target.is_file():
        raise ValueError("Extract the complete ZIP and keep the start script with the application files.")
    with TemporaryDirectory(dir=path.parent) as scratch:
        temporary_link = Path(scratch) / path.name
        save_shortcut(temporary_link, target)
        temporary_link.rename(path)
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
