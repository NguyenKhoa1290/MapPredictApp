"""
Chuyen doi file DWG sang DXF su dung ezdxf.addons.odafc (ODA File Converter).
Usage: dwg_to_dxf.py <input.dwg> <output.dxf>

Yeu cau: ODA File Converter phai duoc cai dat.
Download tai: https://www.opendesign.com/guestfiles/oda_file_converter
"""
import sys
import json
import os
import glob
import platform
import shutil


ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"


def _print_error(message, exit_code=1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(exit_code)


def _find_oda_converter():
    candidates = []

    path_from_env = os.environ.get("ODAFC_PATH") or os.environ.get("ODA_FILE_CONVERTER")
    if path_from_env:
        candidates.append(path_from_env)

    search_roots = []
    seen_roots = set()
    for root in [os.path.dirname(os.path.abspath(__file__)), os.getcwd()]:
        current = os.path.abspath(root)
        while current and current not in seen_roots:
            search_roots.append(current)
            seen_roots.add(current)
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

    for root in search_roots:
        candidates.append(os.path.join(root, "tools", "ODAFileConverter", "ODAFileConverter.exe"))

    executable = shutil.which("ODAFileConverter")
    if executable:
        candidates.append(executable)

    if platform.system() == "Windows":
        candidates += [
            r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
            r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
        ]
        candidates += glob.glob(r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe")
        candidates += glob.glob(r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe")

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)

    return None


def _configure_oda_path(odafc_path):
    import ezdxf

    section = "odafc-addon"
    key = "win_exec_path" if platform.system() == "Windows" else "unix_exec_path"
    ezdxf.options.set(section, key, odafc_path)

def main():
    if len(sys.argv) < 3:
        _print_error("Usage: dwg_to_dxf.py <input.dwg> <output.dxf>")

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.isfile(input_path):
        _print_error(f"Khong tim thay file DWG dau vao: {input_path}")

    if os.path.splitext(input_path)[1].lower() != ".dwg":
        _print_error("File dau vao phai co dinh dang .dwg")

    if os.path.splitext(output_path)[1].lower() != ".dxf":
        _print_error("File dau ra phai co dinh dang .dxf")

    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        from ezdxf.addons import odafc

        odafc_path = _find_oda_converter()
        if odafc_path:
            _configure_oda_path(odafc_path)

        if not odafc.is_installed():
            msg = (
                "ODA File Converter chua duoc cai dat. "
                f"Vui long tai tai: {ODA_DOWNLOAD_URL} "
                "va cai dat truoc khi su dung file DWG."
            )
            _print_error(msg, exit_code=2)

        # Thuc hien chuyen doi
        odafc.convert(input_path, output_path, version="R2010", audit=False, replace=True)

        if not os.path.isfile(output_path):
            raise RuntimeError("ODA da chay nhung khong tao ra file DXF dau ra.")

        print(json.dumps({"success": True, "output": output_path}, ensure_ascii=False))

    except SystemExit:
        raise
    except Exception as e:
        _print_error(str(e))

if __name__ == "__main__":
    main()
