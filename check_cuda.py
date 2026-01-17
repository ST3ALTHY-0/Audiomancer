import torch

print("=" * 60)
print("CUDA CHECK")
print("=" * 60)
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"cuDNN version: {torch.backends.cudnn.version()}")
    print(f"Device count: {torch.cuda.device_count()}")
    print(f"Current device: {torch.cuda.get_device_name(0)}")
    print(f"Device capability: {torch.cuda.get_device_capability(0)}")
else:
    print("CUDA NOT AVAILABLE - PyTorch is CPU-only")
    print(f"CUDA version in build: {torch.version.cuda}")
    print("\nTo enable GPU:")
    print("pip install torch==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124 --force-reinstall --no-deps")
print("=" * 60)
