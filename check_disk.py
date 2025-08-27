import psutil
disk = psutil.disk_usage('/')
print(f"Free space: {disk.free / (1024**3):.2f} GB")