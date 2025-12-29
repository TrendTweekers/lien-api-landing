import os

# Configuration
THRESHOLDS = {
    '.js': 200 * 1024,      # 200KB
    '.css': 100 * 1024,     # 100KB
    '.png': 500 * 1024,     # 500KB
    '.jpg': 500 * 1024,
    '.jpeg': 500 * 1024,
    '.gif': 500 * 1024,
    '.webp': 500 * 1024,
    '.svg': 500 * 1024
}

IGNORE_DIRS = {'.git', 'node_modules', 'venv', '__pycache__', 'api', 'database', 'scripts'}

def check_file_sizes(start_dir):
    print(f"Scanning {start_dir} for large files...")
    large_files = []
    
    for root, dirs, files in os.walk(start_dir):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in THRESHOLDS:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                limit = THRESHOLDS[ext]
                
                if size > limit:
                    large_files.append((file_path, size, limit))
                    
    if large_files:
        print("\nFound large files exceeding thresholds:")
        for path, size, limit in large_files:
            size_kb = size / 1024
            limit_kb = limit / 1024
            print(f" - {path}: {size_kb:.2f}KB (Limit: {limit_kb:.0f}KB)")
    else:
        print("\nNo large files found.")

if __name__ == "__main__":
    # Check current directory (root) and public
    check_file_sizes(".")
