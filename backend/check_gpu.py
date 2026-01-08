"""Quick GPU status check for EchoAI"""
import torch
import sys

print("=" * 50)
print("GPU Status Check for EchoAI")
print("=" * 50)

# PyTorch version
print(f"\n✓ PyTorch version: {torch.__version__}")

# CUDA availability
cuda_available = torch.cuda.is_available()
print(f"\n{'✓' if cuda_available else '✗'} CUDA available: {cuda_available}")

if cuda_available:
    # CUDA version
    print(f"✓ CUDA version: {torch.version.cuda}")
    
    # GPU device count
    gpu_count = torch.cuda.device_count()
    print(f"✓ GPU count: {gpu_count}")
    
    # GPU details
    for i in range(gpu_count):
        print(f"\n  GPU {i}: {torch.cuda.get_device_name(i)}")
        props = torch.cuda.get_device_properties(i)
        print(f"    Memory: {props.total_memory / 1024**3:.1f} GB")
        print(f"    Compute Capability: {props.major}.{props.minor}")
    
    # Current device
    print(f"\n✓ Current device: {torch.cuda.current_device()}")
    
    # Test GPU with a simple operation
    try:
        x = torch.randn(100, 100).cuda()
        y = torch.randn(100, 100).cuda()
        z = torch.mm(x, y)
        print(f"✓ GPU tensor operation: SUCCESS")
        print(f"  Result shape: {z.shape}")
        del x, y, z
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"✗ GPU tensor operation: FAILED - {e}")
else:
    print("\n⚠️  No CUDA GPU detected")
    print("   Running on CPU mode")
    
    # Check if cuDNN backend is available
    print(f"\n✓ cuDNN available: {torch.backends.cudnn.is_available()}")

print("\n" + "=" * 50)
print("Check complete!")
print("=" * 50)
