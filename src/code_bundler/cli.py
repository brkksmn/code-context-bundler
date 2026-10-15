import argparse
import os
import re
from pathlib import Path

IGNORED_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", 
    ".cache", "__pycache__", ".venv", "venv", "coverage", 
    ".turbo", ".idea", ".vscode"
}

IGNORED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", 
    ".DS_Store", "Thumbs.db"
}

DEFAULT_IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".map"
}

def is_secret_file(filename: str) -> bool:
    return filename.startswith(".env")

def should_include_file(file_path: Path, allowed_exts: set[str] | None, output_file: str) -> bool:
    if file_path.name == output_file or file_path.name in IGNORED_FILES:
        return False
    if is_secret_file(file_path.name):
        return False
    
    ext = file_path.suffix.lower()
    if allowed_exts:
        return ext in allowed_exts
    return ext not in DEFAULT_IGNORED_EXTENSIONS

def minify_code(content: str, ext: str) -> str:
    c_style_exts = {".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".c", ".cpp", ".rs", ".css", ".scss", ".php"}
    hash_style_exts = {".py", ".sh", ".bash", ".yaml", ".yml", ".rb", ".dockerfile"}
    sql_exts = {".sql"}
    html_exts = {".html", ".xml", ".svg", ".vue"}

    if ext in c_style_exts:
        pattern = r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)|(/\*[\s\S]*?\*/|//.*?$)'
        content = re.sub(pattern, lambda m: m.group(1) if m.group(1) else "", content, flags=re.MULTILINE)
    elif ext in hash_style_exts:
        pattern = r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(#.*?$)'
        content = re.sub(pattern, lambda m: m.group(1) if m.group(1) else "", content, flags=re.MULTILINE)
    elif ext in sql_exts:
        pattern = r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(/\*[\s\S]*?\*/|--.*?$)'
        content = re.sub(pattern, lambda m: m.group(1) if m.group(1) else "", content, flags=re.MULTILINE)
    elif ext in html_exts:
        content = re.sub(r'<!--[\s\S]*?-->', '', content)

    cleaned_lines = [line.rstrip() for line in content.splitlines()]
    return "\n".join(line for line in cleaned_lines if line.strip())

def generate_tree(dir_path: Path, allowed_exts: set[str] | None, output_file: str, prefix: str = "") -> list[str]:
    lines = []
    try:
        entries = sorted(
            [e for e in dir_path.iterdir() if e.name not in IGNORED_DIRS],
            key=lambda s: (s.is_file(), s.name.lower())
        )
    except PermissionError:
        return lines

    filtered_entries = []
    for entry in entries:
        if entry.is_dir():
            filtered_entries.append(entry)
        elif should_include_file(entry, allowed_exts, output_file):
            filtered_entries.append(entry)

    total = len(filtered_entries)
    for i, entry in enumerate(filtered_entries):
        is_last = (i == total - 1)
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            lines.extend(generate_tree(entry, allowed_exts, output_file, prefix + extension))
            
    return lines

def bundle_project(
    root_dir: str = ".", 
    output_file: str = "project_bundle.md", 
    allowed_exts: set[str] | None = None,
    minify: bool = False
):
    root = Path(root_dir).resolve()
    
    filter_msg = f" (Filtre: {', '.join(sorted(allowed_exts))})" if allowed_exts else " (Tüm kaynak kodlar)"
    minify_msg = " [Minify Aktif]" if minify else ""
    print(f"📦 Tarama başlatıldı: {root}{filter_msg}{minify_msg}")
    
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("# Proje Kaynak Kodu Özeti\n\n")
        out.write(f"- **Kök Dizin:** `{root.name}`\n")
        if allowed_exts:
            out.write(f"- **Dahil Edilen Uzantılar:** `{', '.join(sorted(allowed_exts))}`\n")
        out.write(f"- **Minify Durumu:** `{'Aktif' if minify else 'Pasif'}`\n\n")
        
        out.write("## 1. Dizin ve Dosya Yapısı\n\n```text\n")
        out.write(f"{root.name}/\n")
        tree_lines = generate_tree(root, allowed_exts, output_file)
        out.write("\n".join(tree_lines))
        out.write("\n```\n\n---\n\n")
        
        out.write("## 2. Dosya İçerikleri\n\n")
        file_count = 0
        
        for current_root, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            
            for file in sorted(files):
                file_path = Path(current_root) / file
                
                if not should_include_file(file_path, allowed_exts, output_file):
                    continue
                
                relative_path = file_path.relative_to(root)
                ext = file_path.suffix.lower()
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    if minify:
                        content = minify_code(content, ext)
                    
                    ext_tag = ext.lstrip(".") or "text"
                    out.write(f"### `{relative_path}`\n\n")
                    out.write(f"```{ext_tag}\n")
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
                    out.write("```\n\n")
                    file_count += 1
                except (UnicodeDecodeError, PermissionError):
                    continue

    print(f"✅ Tamamlandı! Toplam {file_count} dosya '{output_file}' içine aktarıldı.")

def main():
    parser = argparse.ArgumentParser(
        prog="bundler",
        description="Projeyi tek bir Markdown dosyasında toplayan ve token tasarrufu sağlayan CLI aracı."
    )
    parser.add_argument(
        "dir", 
        nargs="?", 
        default=".", 
        help="Taranacak dizin (Varsayılan: mevcut dizin)"
    )
    parser.add_argument(
        "-e", "--extensions", 
        nargs="+", 
        help="Yalnızca dahil edilecek uzantılar (örn: -e ts tsx go)"
    )
    parser.add_argument(
        "-o", "--output", 
        default="project_bundle.md", 
        help="Çıktı Markdown dosyasının adı (Varsayılan: project_bundle.md)"
    )
    parser.add_argument(
        "-m", "--minify", 
        action="store_true", 
        help="Yorum satırlarını ve gereksiz boşlukları ayıklayarak token tasarrufu sağlar."
    )
    
    args = parser.parse_args()
    
    formatted_exts = None
    if args.extensions:
        formatted_exts = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions}
        formatted_exts = {ext.lower() for ext in formatted_exts}

    bundle_project(
        root_dir=args.dir, 
        output_file=args.output, 
        allowed_exts=formatted_exts,
        minify=args.minify
    )

if __name__ == "__main__":
    main()